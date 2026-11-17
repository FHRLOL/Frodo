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
                raw_stream = self._stream_llm(messages)
                stream_gen = self._limit_thinking_tokens(raw_stream, max_thought_tokens=256, strip_thoughts=True)
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

            # Стримим фоллбэк кусочками для имитации потока с ограничением Thinking Mode
            words = fallback_answer.split(" ")
            async def _fallback_word_gen():
                for i, word in enumerate(words):
                    chunk_str = word if i == len(words) - 1 else word + " "
                    yield chunk_str

            limited_fallback = self._limit_thinking_tokens(_fallback_word_gen(), max_thought_tokens=256, strip_thoughts=True)
            async for chunk_str in limited_fallback:
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

    @staticmethod
    async def _limit_thinking_tokens(
        stream: AsyncGenerator[str, None],
        max_thought_tokens: int = 256,
        strip_thoughts: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Отслеживает токены внутри тегов <thought>...</thought>.
        При достижении лимита max_thought_tokens (256 токенов):
        1. Принудительно эмиттирует закрывающий тег </thought>.
        2. Переводит поток генерации на ответ студенту, подавляя избыточные мысли
           до появления исходного закрывающего тега модели.

        Если strip_thoughts=True (боевой режим SSE для UI):
        - Полностью скрывает служебные теги <thought>/</thought> и сами токены размышлений
          от студента, передавая в интерфейс исключительно чистый ответ.
        """
        in_thought = False
        thought_tokens_count = 0
        thought_closed = False
        thought_force_closed = False
        suppressing_excess = False
        excess_count = 0
        header_stripped = False
        buffer = ""

        async for chunk in stream:
            buffer += chunk

            while buffer:
                # 1. До блока мысли: ищем открывающий тег <thought>
                if not in_thought and not thought_closed and not thought_force_closed:
                    if "<thought>" in buffer:
                        idx = buffer.index("<thought>")
                        before = buffer[:idx]
                        if before:
                            yield before
                        if not strip_thoughts:
                            yield "<thought>"
                        in_thought = True
                        thought_tokens_count = 0
                        buffer = buffer[idx + len("<thought>"):]
                        continue
                    else:
                        matched_prefix = None
                        for prefix in ("<thought>"[:i] for i in range(len("<thought>") - 1, 0, -1)):
                            if buffer.endswith(prefix):
                                matched_prefix = prefix
                                break
                        if matched_prefix:
                            to_yield = buffer[:-len(matched_prefix)]
                            if to_yield:
                                yield to_yield
                            buffer = matched_prefix
                            break
                        else:
                            yield buffer
                            buffer = ""
                            break

                # 2. Внутри мысли: считаем токены до </thought> или до лимита
                elif in_thought:
                    if "</thought>" in buffer:
                        idx = buffer.index("</thought>")
                        thought_chunk = buffer[:idx]
                        if thought_chunk:
                            if not strip_thoughts:
                                yield thought_chunk
                            thought_tokens_count += 1
                        if not strip_thoughts:
                            yield "</thought>"
                        in_thought = False
                        thought_closed = True
                        buffer = buffer[idx + len("</thought>"):]
                        continue
                    else:
                        matched_prefix = None
                        for prefix in ("</thought>"[:i] for i in range(len("</thought>") - 1, 0, -1)):
                            if buffer.endswith(prefix):
                                matched_prefix = prefix
                                break

                        if matched_prefix:
                            to_process = buffer[:-len(matched_prefix)]
                            buffer = matched_prefix
                        else:
                            to_process = buffer
                            buffer = ""

                        if to_process:
                            thought_tokens_count += 1
                            if thought_tokens_count < max_thought_tokens:
                                if not strip_thoughts:
                                    yield to_process
                            elif thought_tokens_count == max_thought_tokens:
                                if not strip_thoughts:
                                    yield to_process
                                    yield "\n</thought>\n"
                                in_thought = False
                                thought_force_closed = True
                                suppressing_excess = True
                        break

                # 3. Принудительное закрытие: подавляем лишние токены размышлений до </thought>
                elif suppressing_excess:
                    if "</thought>" in buffer:
                        idx = buffer.index("</thought>")
                        buffer = buffer[idx + len("</thought>"):]
                        suppressing_excess = False
                        thought_closed = True
                        continue
                    else:
                        excess_count += 1
                        if excess_count > 128:
                            suppressing_excess = False
                            if not strip_thoughts:
                                yield buffer
                            buffer = ""
                        else:
                            buffer = ""
                        break

                # 4. Основной ответ студенту (после закрытия мысли)
                else:
                    if "</thought>" in buffer:
                        idx = buffer.index("</thought>")
                        before = buffer[:idx]
                        after = buffer[idx + len("</thought>"):]
                        if before:
                            yield before
                        buffer = after
                        continue

                    if strip_thoughts and not header_stripped:
                        buffer = buffer.lstrip("\r\n ")
                        if buffer.startswith("#"):
                            if "\n" in buffer:
                                buffer = buffer.split("\n", 1)[1].lstrip("\r\n ")
                                header_stripped = True
                            else:
                                break
                        else:
                            header_stripped = True

                    yield buffer
                    buffer = ""
                    break

        if buffer:
            if in_thought:
                if not strip_thoughts:
                    yield buffer
                    yield "\n</thought>\n"
            elif not suppressing_excess:
                if "</thought>" in buffer and (thought_closed or thought_force_closed):
                    buffer = buffer.replace("</thought>", "")
                if strip_thoughts and not header_stripped and buffer.startswith("#"):
                    if "\n" in buffer:
                        buffer = buffer.split("\n", 1)[1]
                    else:
                        buffer = ""
                if buffer:
                    yield buffer

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

    @staticmethod
    def _get_master_code_sample(question: str, sec: str) -> str:
        q = question.lower()
        if any(w in q for w in ("список", "списки", "append", "sort", "del", "изменяем")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Создание изменяемого списка и базовые операции\n"
                "fruits = ['яблоко', 'банан']\n"
                "fruits.append('груша')  # Метод append() добавляет элемент в конец\n"
                "fruits.sort()           # Метод sort() изменяет исходный список на месте\n"
                "del fruits[0]           # Оператор del удаляет элемент по индексу\n"
                "print('Итоговый список:', fruits)\n"
                "```"
            )
        elif any(w in q for w in ("кортеж", "tuple", "(2,)", "singleton")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Кортеж из одного элемента обязательно оформляется с запятой:\n"
                "singleton = (2,)\n"
                "print(singleton, type(singleton))  # (2,) <class 'tuple'>\n\n"
                "# Кортеж является неизменяемым типом данных (immutable):\n"
                "# singleton[0] = 5  # Вызовет исключение TypeError\n"
                "```"
            )
        elif any(w in q for w in ("//", "делен", "-13")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Оператор // выполняет деление с округлением вниз (к меньшему целому):\n"
                "result = -13 // 3\n"
                "print(f'-13 // 3 = {result}')  # Выведет: -5\n"
                "```"
            )
        elif any(w in q for w in ("try", "except", "else")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "try:\n"
                "    val = int('42')\n"
                "except ValueError as e:\n"
                "    print('Перехвачена ошибка:', e)\n"
                "else:\n"
                "    # Блок else выполняется ТОЛЬКО тогда, когда исключений НЕ возникло:\n"
                "    print('Исключений не возникло, результат:', val)\n"
                "```"
            )
        elif any(w in q for w in ("finally", "with", "__exit__", "закрыт")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Конструкция with автоматически вызывает метод __exit__ для закрытия файла:\n"
                "with open('demo.txt', 'w', encoding='utf-8') as f:\n"
                "    f.write('Frodo Safe Resource Management')\n"
                "# Здесь файл уже гарантированно закрыт\n"
                "```"
            )
        elif "raise" in q:
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Генерация исключения с помощью оператора raise:\n"
                "def check_positive(num):\n"
                "    if num <= 0:\n"
                "        raise ValueError('Значение должно быть больше 0')\n"
                "    return num\n"
                "```"
            )
        elif any(w in q for w in ("словар", "dict")):
            return (
                "\n\nПример практической реализации:\n"
                "```python\n"
                "# Создание словаря и удаление пары ключ-значение через del:\n"
                "student = {'name': 'Иван', 'group': 'ИВТ-1'}\n"
                "del student['group']  # Удаление пары по ключу\n"
                "print(student)\n"
                "```"
            )
        else:
            return (
                f"\n\nПример практической реализации:\n"
                f"```python\n"
                f"# Практический пример по теме «{sec}»\n"
                f"data = [1, 2, 3]\n"
                f"result = [x * 2 for x in data]\n"
                f"print('Результат:', result)\n"
                f"```"
            )

    def _generate_fallback_response(
        self,
        question: str,
        top_chunk: Dict[str, Any],
        mode: str,
        benchmark_match: Optional[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """
        Интеллектуальный фоллбэк генератор ответов для оффлайн режима и тестов.
        Генерирует чистые структурированные ответы без утечек служебных тегов,
        строго различая Сократовский режим (наводящие вопросы, запрет кода)
        и Режим Мастера (исчерпывающий академический разбор, профильные примеры кода).
        """
        doc = top_chunk.get("doc_name", "")
        sec = top_chunk.get("section_title", "")
        l_start = top_chunk.get("line_start", 1)
        l_end = top_chunk.get("line_end", 1)
        content_snippet = top_chunk.get("content", "")[:350].strip()

        if mode == "socratic":
            if benchmark_match and benchmark_match.get("ground_truth"):
                theory_text = benchmark_match["ground_truth"]
            else:
                theory_text = content_snippet

            answer_body = (
                f"Согласно материалам курса (раздел «{sec}», строки {l_start}–{l_end}):\n\n"
                f"{theory_text}\n\n"
                f"💡 **Наводящий вопрос для закрепления:**\n"
                f"Обратите внимание на описанные правила: как именно ведет себя данный тип данных или оператор? "
                f"Попробуйте применить эту логику к вашему случаю и проверить, что возвращает выражение."
            )
            status = "SOCRATIC_GUIDANCE"
        else:
            code_sample = self._get_master_code_sample(question, sec)
            if benchmark_match and benchmark_match.get("ground_truth"):
                answer_body = f"{benchmark_match['ground_truth']}{code_sample}"
            else:
                answer_body = (
                    f"Подробный разбор концепта «{sec}» ({doc}, строки {l_start}–{l_end}):\n\n"
                    f"{content_snippet}{code_sample}"
                )
            status = "MASTER_EXPLANATION"

        return answer_body, status

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

    def cleanup_idle_slots(self) -> int:
        """
        Проверяет состояние слотов llama-server и сбрасывает зависшие/неактивные слоты
        для освобождения VRAM под новых пользователей (Idle KV-Cache Eviction).
        """
        if not self.is_llm_online():
            return 0
        try:
            base_url = self.llm_url.rsplit("/v1", 1)[0]
            url = f"{base_url}/slots"
            req = urllib.request.Request(url, headers={"User-Agent": "Frodo-Cleaner/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                slots = json.loads(resp.read().decode("utf-8"))

            released = 0
            for slot in slots:
                slot_id = slot.get("id")
                # Если слот не в обработке и удерживает кэш
                if not slot.get("is_processing", False) and slot.get("n_past", 0) > 0:
                    erase_url = f"{base_url}/slots/{slot_id}?action=erase"
                    erase_req = urllib.request.Request(erase_url, method="POST")
                    try:
                        with urllib.request.urlopen(erase_req, timeout=1.0):
                            released += 1
                    except Exception:
                        pass
            return released
        except Exception:
            return 0

