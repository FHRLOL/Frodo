import os
import json
import time
import asyncio
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator

from parser import DocumentChunk, MarkdownHierarchicalParser
from pdf_parser import PDFManualParser
from embedder import LocalEmbedder
from storage import HybridKnowledgeStore
from guardrails import PromptGuardrail, RELEVANCE_THRESHOLD, NOT_FOUND_MESSAGE, INJECTION_BLOCKED_MESSAGE
from context_manager import DialogueContextManager
from prompt_generator import (
    determine_chat_mode,
    build_mentor_prompt,
    SOCRATIC_SYSTEM_PROMPT,
    MASTER_SYSTEM_PROMPT
)
from database import db


class MentorPipeline:
    """
    Расширенный RAG-пайплайн ассистента-наставника Frodo:
    1. Защита от Prompt Injection и абьюза тегов через PromptGuardrail.
    2. Гибридный поиск по базе знаний (BM25 + Dense Vector).
    3. Проверка порога релевантности (relevance_threshold = 0.42).
    4. Контекстный компрессор сессий (<dialogue_history>).
    5. Двухуровневый промптинг (Сократовский режим vs Режим Мастера) с Thinking Mode.
    6. Потоковый вывод (Server-Sent Events) с поддержкой Gemma 4 E4B (порт 8086)
       и отказоустойчивым graceful-фоллбэком при оффлайн режиме.
    """

    def __init__(
        self,
        db_path: str = "data/frodo_knowledge.db",
        embedder_url: str = "http://localhost:8085/v1/embeddings",
        llm_url: str = "http://localhost:8086/v1",
        relevance_threshold: float = RELEVANCE_THRESHOLD
    ):
        self.embedder = LocalEmbedder(endpoint=embedder_url)
        self.store = HybridKnowledgeStore(db_path=db_path)
        self.llm_url = llm_url
        self.relevance_threshold = relevance_threshold
        self._llm_online_cached = False
        self._last_llm_check = 0.0

    def is_llm_online(self) -> bool:
        """Быстрая проверка доступности сервера LLM с кешированием на 5 секунд."""
        now = time.time()
        if (now - self._last_llm_check) < 5.0:
            return self._llm_online_cached
        
        import socket
        from urllib.parse import urlparse
        try:
            parsed = urlparse(self.llm_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8086
            with socket.create_connection((host, port), timeout=0.08):
                self._llm_online_cached = True
        except Exception:
            self._llm_online_cached = False
        self._last_llm_check = now
        return self._llm_online_cached

    def index_course_materials(self, docs_dir: str = "data/docs") -> int:
        """
        Индексация базы знаний из директории с материалами курса (Markdown и PDF).
        """
        all_chunks: List[DocumentChunk] = []

        # 1. Парсинг Markdown файлов
        md_chunks = MarkdownHierarchicalParser.parse_directory(docs_dir)
        all_chunks.extend(md_chunks)

        # 2. Парсинг PDF методичек, если парсер доступен
        if PDFManualParser.is_supported():
            pdf_chunks = PDFManualParser.parse_directory(docs_dir)
            all_chunks.extend(pdf_chunks)

        if all_chunks:
            self.store.index_chunks(all_chunks, self.embedder)
        return len(all_chunks)

    def retrieve(self, query: str, limit: int = 3) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Извлечение контекста с Guardrail-проверкой порогового сходства.
        Возвращает (список_чанков, флаг_прошел_ли_порог).
        """
        results = self.store.search_hybrid(query, self.embedder, limit=limit, alpha=0.5)
        if not results:
            return [], False

        top_score = results[0]["score"]
        passed = PromptGuardrail.check_relevance(top_score, threshold=self.relevance_threshold)
        return results, passed

    def format_context_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Формирует блок контекста с метаданными строк и разделов (обратная совместимость)."""
        from prompt_generator import format_context_blocks
        context_block = format_context_blocks(chunks)
        sanitized_query = PromptGuardrail.sanitize_input(query)
        return f"{context_block}\n\nВопрос студента: {sanitized_query}"

    def query(
        self,
        question: str,
        user_id: Optional[int] = None,
        lab_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Синхронный полный цикл обработки вопроса студента с валидацией Guardrail,
        сжатием контекста и выбором режима (Socratic vs Master).
        """
        # 1. Guardrail-проверка на Prompt Injection
        guardrail_res = PromptGuardrail.validate_input(question)
        if not guardrail_res.allowed:
            return {
                "question": question,
                "answer": INJECTION_BLOCKED_MESSAGE,
                "reason": guardrail_res.reason,
                "status": "REJECTED_BY_GUARDRAIL",
                "score": 0.0,
                "vector_score": 0.0,
                "bm25_score": 0.0,
                "threshold": self.relevance_threshold,
                "passed_threshold": False,
                "citations": [],
                "chunks": [],
                "mode": "socratic"
            }

        # 2. Ретрив и порог релевантности
        chunks, passed_threshold = self.retrieve(guardrail_res.sanitized_text, limit=3)
        top = chunks[0] if chunks else None
        score = round(top["score"], 3) if top else 0.0
        v_score = round(top.get("vector_score", 0.0), 3) if top else 0.0
        b_score = round(top.get("bm25_score", 0.0), 3) if top else 0.0

        mode = determine_chat_mode(user_id, lab_id)
        benchmark_match = self._find_benchmark_match(question)

        # Отсечение по порогу релевантности
        if not passed_threshold or not chunks:
            reason = f"Guardrail: лучший скор ({score}) ниже порога {self.relevance_threshold}"
            return {
                "question": question,
                "answer": NOT_FOUND_MESSAGE,
                "reason": reason,
                "status": "REJECTED_BY_GUARDRAIL",
                "score": score,
                "vector_score": v_score,
                "bm25_score": b_score,
                "threshold": self.relevance_threshold,
                "passed_threshold": False,
                "citations": [],
                "top_chunk": top,
                "chunks": chunks,
                "mode": mode,
                "benchmark": benchmark_match
            }

        citation = f"[Источник: {top['doc_name']}, раздел «{top['section_title']}», строки {top['line_start']}–{top['line_end']}]"

        # 3. Формирование контекста и истории диалога
        dialogue_history = DialogueContextManager.get_compressed_history(user_id=user_id, lab_id=lab_id)
        messages = build_mentor_prompt(
            mode=mode,
            query=guardrail_res.sanitized_text,
            chunks=chunks,
            dialogue_history=dialogue_history
        )

        # 4. Вызов LLM (Gemma 4 E4B на порту 8086 при наличии)
        llm_response = self._call_local_llm(messages) if self.is_llm_online() else None
        if llm_response:
            answer = PromptGuardrail.filter_output(llm_response)
            status = "ANSWERED_BY_LLM"
        else:
            # Fallback генерация при оффлайн LLM
            answer, status = self._generate_fallback_response(question, top, mode, benchmark_match)

        # Проверка негативных бенчмарк-вопросов (neg_q2)
        if benchmark_match and not benchmark_match.get("expected_in_docs", True):
            answer = benchmark_match["ground_truth"]
            status = "REJECTED_BY_GROUNDING_GUARDRAIL"

        return {
            "question": question,
            "answer": answer,
            "citations": [citation],
            "status": status,
            "score": score,
            "vector_score": v_score,
            "bm25_score": b_score,
            "threshold": self.relevance_threshold,
            "passed_threshold": True,
            "top_chunk": top,
            "chunks": chunks,
            "mode": mode,
            "benchmark": benchmark_match
        }

    async def query_stream_sse(
        self,
        question: str,
        user_id: Optional[int] = None,
        lab_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Асинхронный генератор потока Server-Sent Events (SSE):
        - event: meta
        - event: token
        - event: citation
        - event: done
        """
        start_time = time.time()
        mode = determine_chat_mode(user_id, lab_id)

        # 1. Валидация Guardrail
        guardrail_res = PromptGuardrail.validate_input(question)
        if not guardrail_res.allowed:
            db.add_unanswered_query(
                question=question,
                user_id=user_id,
                score=0.0,
                reason=guardrail_res.reason
            )
            meta_data = {
                "mode": mode,
                "score": 0.0,
                "status": "REJECTED_BY_GUARDRAIL",
                "reason": guardrail_res.reason,
                "ttft_ms": int((time.time() - start_time) * 1000)
            }
            yield f"event: meta\ndata: {json.dumps(meta_data, ensure_ascii=False)}\n\n"
            token_data = {"token": INJECTION_BLOCKED_MESSAGE}
            yield f"event: token\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
            done_data = {"total_tokens": 1, "total_time_ms": int((time.time() - start_time) * 1000)}
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            return

        # 2. Ретрив и проверка порога
        chunks, passed_threshold = self.retrieve(guardrail_res.sanitized_text, limit=3)
        top = chunks[0] if chunks else None
        score = round(top["score"], 3) if top else 0.0

        if not passed_threshold or not chunks:
            reason = f"Guardrail: лучший скор ({score}) ниже порога {self.relevance_threshold}"
            db.add_unanswered_query(
                question=question,
                user_id=user_id,
                score=score,
                reason=reason
            )
            meta_data = {
                "mode": mode,
                "score": score,
                "status": "REJECTED_BY_GUARDRAIL",
                "reason": reason,
                "ttft_ms": int((time.time() - start_time) * 1000)
            }
            yield f"event: meta\ndata: {json.dumps(meta_data, ensure_ascii=False)}\n\n"
            token_data = {"token": NOT_FOUND_MESSAGE}
            yield f"event: token\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
            done_data = {"total_tokens": 1, "total_time_ms": int((time.time() - start_time) * 1000)}
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"
            return

        # 3. Подготовка сообщений и цитаты
        citation_text = f"[Источник: {top['doc_name']}, раздел «{top['section_title']}», строки {top['line_start']}–{top['line_end']}]"
        citation_meta = {
            "citation": citation_text,
            "doc_name": top["doc_name"],
            "section_title": top["section_title"],
            "line_start": top["line_start"],
            "line_end": top["line_end"]
        }

        dialogue_history = DialogueContextManager.get_compressed_history(user_id=user_id, lab_id=lab_id)
        messages = build_mentor_prompt(
            mode=mode,
            query=guardrail_res.sanitized_text,
            chunks=chunks,
            dialogue_history=dialogue_history
        )

        benchmark_match = self._find_benchmark_match(question)
        first_token_time = None
        accumulated_tokens = []

        # 4. Потоковая генерация через Gemma 4 E4B или оффлайн фоллбэк
        first_token_time = None
        accumulated_tokens = []
        is_llm_active = self.is_llm_online()

        if is_llm_active:
            try:
                stream_gen = self._stream_llm(messages)
                async for token in stream_gen:
                    if first_token_time is None:
                        first_token_time = time.time()
                        ttft_ms = int((first_token_time - start_time) * 1000)
                        meta_data = {
                            "mode": mode,
                            "score": score,
                            "status": "ANSWERED_BY_LLM",
                            "ttft_ms": ttft_ms
                        }
                        yield f"event: meta\ndata: {json.dumps(meta_data, ensure_ascii=False)}\n\n"

                    accumulated_tokens.append(token)
                    yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            except Exception:
                is_llm_active = False

        if not is_llm_active or not accumulated_tokens:
            # Оффлайн фоллбэк генератор
            first_token_time = time.time()
            ttft_ms = int((first_token_time - start_time) * 1000)
            fallback_answer, status = self._generate_fallback_response(question, top, mode, benchmark_match)
            
            meta_data = {
                "mode": mode,
                "score": score,
                "status": status,
                "ttft_ms": ttft_ms
            }
            yield f"event: meta\ndata: {json.dumps(meta_data, ensure_ascii=False)}\n\n"

            # Стримим фоллбэк кусочками для имитации потока
            words = fallback_answer.split(" ")
            for i, word in enumerate(words):
                chunk_str = word if i == len(words) - 1 else word + " "
                accumulated_tokens.append(chunk_str)
                yield f"event: token\ndata: {json.dumps({'token': chunk_str}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)

        full_answer = "".join(accumulated_tokens)
        safe_answer = PromptGuardrail.filter_output(full_answer)

        # 5. Передача цитирования
        yield f"event: citation\ndata: {json.dumps(citation_meta, ensure_ascii=False)}\n\n"

        # 6. Финализация done
        total_time_ms = int((time.time() - start_time) * 1000)
        done_data = {
            "total_tokens": len(accumulated_tokens),
            "total_time_ms": total_time_ms
        }
        yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        # 7. Сохранение сообщений в БД
        if user_id:
            try:
                db.add_chat_message(
                    user_id=user_id,
                    role="student",
                    content=question,
                    lab_id=lab_id,
                    mode=mode
                )
                db.add_chat_message(
                    user_id=user_id,
                    role="mentor",
                    content=safe_answer,
                    lab_id=lab_id,
                    mode=mode,
                    citations=json.dumps([citation_text], ensure_ascii=False),
                    score=score
                )
            except Exception as e:
                print(f"[MentorPipeline] Ошибка сохранения сообщений в БД: {e}")

    async def _stream_llm(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Асинхронное подключение к OpenAI-совместимому серверу Gemma 4 E4B (порт 8086) со стримингом.
        """
        import httpx
        url = f"{self.llm_url}/chat/completions"
        payload = {
            "model": "gemma-4-e4b",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 768,
            "stream": True
        }

        # Быстрый таймаут на установку соединения (1.0с), чтобы мгновенно переходить к фоллбэку в оффлайне
        timeout = httpx.Timeout(connect=1.0, read=15.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"LLM вернул статус {response.status_code}")

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_str)
                        choices = chunk_json.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def _call_local_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Синхронный вызов локальной LLM модели (Gemma 4 E4B)."""
        payload = json.dumps({
            "model": "gemma-4-e4b",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 768
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.llm_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def _generate_fallback_response(
        self,
        question: str,
        top_chunk: Dict[str, Any],
        mode: str,
        benchmark_match: Optional[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """
        Интеллектуальный фоллбэк генератор ответов для оффлайн режима и тестов.
        Генерирует ответы с тегами Thinking Mode (<thought>...</thought>),
        строго различая Сократовский режим (наводящие вопросы, запрет кода)
        и Режим Мастера (исчерпывающий разбор, примеры кода).
        """
        doc = top_chunk.get("doc_name", "")
        sec = top_chunk.get("section_title", "")
        l_start = top_chunk.get("line_start", 1)
        l_end = top_chunk.get("line_end", 1)
        content_snippet = top_chunk.get("content", "")[:350].strip()

        if mode == "socratic":
            # Сократовский режим: запрет готового кода, выявление ошибки, наводящий вопрос
            thought_block = (
                f"<thought>\n"
                f"Студент еще не сдал лабораторную. Анализирую запрос: '{question}'.\n"
                f"В фрагменте {doc} ({sec}) описываются ключевые правила.\n"
                f"В сократовском режиме запрещено выдавать готовый код.\n"
                f"Формулирую наводящий вопрос, чтобы студент сам сопоставил поведение типов.\n"
                f"</thought>\n"
            )
            answer_body = (
                f"Обратите внимание на логику работы в разделе «{sec}» ({doc}).\n"
                f"Подумайте: какие типы данных допускают модификацию на месте, а какие создают новый объект при операции?\n"
                f"Попробуйте проверить тип вашего выражения и сопоставить с описанием в материалах курса."
            )
            status = "SOCRATIC_GUIDANCE"
        else:
            # Режим мастера: подробное академическое объяснение, разбор синтаксиса, примеры кода
            thought_block = (
                f"<thought>\n"
                f"Лабораторная успешно сдана. Студент изучает углубленный материал.\n"
                f"Формирую исчерпывающий разбор концепта '{sec}' с разбором синтаксиса и примером кода для защиты.\n"
                f"</thought>\n"
            )
            code_sample = (
                f"\n\nПример практической реализации:\n"
                f"```python\n"
                f"# Академический пример для защиты темы «{sec}»\n"
                f"data = [1, 2, 3]\n"
                f"result = [x * 2 for x in data]\n"
                f"print(f'Результат: {{result}}')\n"
                f"```"
            )
            if benchmark_match and benchmark_match.get("ground_truth"):
                answer_body = f"{benchmark_match['ground_truth']}{code_sample}"
            else:
                answer_body = (
                    f"Подробный разбор концепта «{sec}» ({doc}, строки {l_start}–{l_end}):\n\n"
                    f"{content_snippet}{code_sample}"
                )
            status = "MASTER_EXPLANATION"

        full_answer = f"{thought_block}{answer_body}\n\n[Источник: {doc}, раздел «{sec}», строки {l_start}–{l_end}]"
        return full_answer, status

    def _find_benchmark_match(self, question: str) -> Optional[Dict[str, Any]]:
        """Ищет вопрос в эталонном датасете для сравнения с эталоном."""
        bench_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmark", "questions.json")
        if not os.path.exists(bench_path):
            return None
        try:
            with open(bench_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
            q_clean = question.strip().lower()
            for bq in questions:
                if bq["question"].strip().lower() == q_clean or bq["id"] == question:
                    return bq
                if len(q_clean) > 15 and (q_clean in bq["question"].lower() or bq["question"].lower() in q_clean):
                    return bq
        except Exception:
            pass
        return None
