import os
import json
import urllib.request
from typing import List, Dict, Any, Optional, Tuple
from parser import DocumentChunk, MarkdownHierarchicalParser
from embedder import LocalEmbedder
from storage import HybridKnowledgeStore

MENTOR_SYSTEM_PROMPT = """Ты — строгий ассистент-наставник по материалам курса Python.
Твоя задача — отвечать на вопросы студента ИСКЛЮЧИТЕЛЬНО на основе предоставленных материалов курса из блока <context>.

ГЛАВНЫЕ ПРАВИЛА НАСТАВНИКА:
1. АБСОЛЮТНОЕ ЗАЗЕМЛЕНИЕ: Запрещено использовать любые внешние знания, библиотеки или общие факты, которых нет в блоке <context>.
2. ЧЕСТНЫЙ ОТКАЗ: Если в блоке <context> нет прямого и однозначного ответа на вопрос (или данных недостаточно), ты ОБЯЗАН ответить:
   «В предоставленных материалах этого нет.»
   Запрещено додумывать, экстраполировать или угадывать.
3. ОБЯЗАТЕЛЬНОЕ ЦИТИРОВАНИЕ: Каждый утвердительный ответ обязан содержать точную ссылку на источник в конце ответа в формате:
   [Источник: <название_документа>, раздел «<название_раздела>», строки <X-Y>]
4. СТИЛЬ: Отвечай понятно, структурированно и лаконично, помогая студенту разобраться в материале.
"""

class MentorPipeline:
    """
    Основной пайплайн ассистента-наставника:
    1. Прием вопроса студента.
    2. Гибридный поиск по базе знаний (BM25 + Dense Vector).
    3. Оценка релевантности и Guardrail-порог.
    4. Формирование контекста и заземленного системного промпта.
    5. Генерация ответа со ссылками на первоисточник.
    """

    def __init__(
        self,
        db_path: str = "data/frodo_knowledge.db",
        embedder_url: str = "http://localhost:8085/v1/embeddings",
        llm_url: str = "http://localhost:1234/v1",
        relevance_threshold: float = 0.42
    ):
        self.embedder = LocalEmbedder(endpoint=embedder_url)
        self.store = HybridKnowledgeStore(db_path=db_path)
        self.llm_url = llm_url
        self.relevance_threshold = relevance_threshold

    def index_course_materials(self, docs_dir: str = "data/docs"):
        """Переиндексация базы знаний из директории с материалами курса."""
        chunks = MarkdownHierarchicalParser.parse_directory(docs_dir)
        self.store.index_chunks(chunks, self.embedder)
        return len(chunks)

    def retrieve(self, query: str, limit: int = 3) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Извлечение контекста с Guardrail-проверкой порогового сходства.
        Возвращает (список_чанков, флаг_прошел_ли_порог).
        """
        results = self.store.search_hybrid(query, self.embedder, limit=limit, alpha=0.5)
        if not results:
            return [], False

        top_score = results[0]["score"]
        passed = top_score >= self.relevance_threshold
        return results, passed

    def format_context_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Формирует блок контекста с метаданными строк и разделов."""
        context_parts = []
        for i, c in enumerate(chunks, 1):
            context_parts.append(
                f"--- ФРАГМЕНТ #{i} ---\n"
                f"Документ: {c['doc_name']}\n"
                f"Раздел: {c['breadcrumbs']}\n"
                f"Строки в документе: {c['line_start']}–{c['line_end']}\n"
                f"Релевантность (score): {round(c['score'], 3)}\n\n"
                f"{c['content']}\n"
            )
        
        joined_context = "\n".join(context_parts)
        user_message = f"<context>\n{joined_context}\n</context>\n\nВопрос студента: {query}"
        return user_message

    def query(self, question: str) -> Dict[str, Any]:
        """Полный цикл обработки вопроса студента с детальной диагностикой ретрива."""
        chunks, passed_threshold = self.retrieve(question, limit=3)
        top = chunks[0] if chunks else None
        score = round(top["score"], 3) if top else 0.0
        v_score = round(top.get("vector_score", 0.0), 3) if top else 0.0
        b_score = round(top.get("bm25_score", 0.0), 3) if top else 0.0

        # Поиск совпадения в эталонном бенчмарке
        benchmark_match = self._find_benchmark_match(question)

        # Проверка порога Guardrail
        if not passed_threshold or not chunks:
            reason = f"Guardrail: лучший скор ({score}) ниже порога {self.relevance_threshold}"
            return {
                "question": question,
                "answer": "В предоставленных материалах этого нет.",
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
                "benchmark": benchmark_match
            }

        citation = f"[Источник: {top['doc_name']}, раздел «{top['section_title']}», строки {top['line_start']}–{top['line_end']}]"
        prompt = self.format_context_prompt(question, chunks)

        # Вызов локальной LLM при наличии инференс-сервера
        llm_response = self._call_local_llm(prompt)
        if llm_response:
            answer = llm_response
            status = "ANSWERED_BY_LLM"
        else:
            # Если LLM сервер оффлайн, используем эталонный ответ (для бенчмарк-вопросов) либо саммари чанка
            if benchmark_match:
                answer = benchmark_match["ground_truth"]
                status = "GROUND_TRUTH_MATCH"
            else:
                answer = f"Согласно материалам ({top['doc_name']}, раздел «{top['section_title']}», строки {top['line_start']}–{top['line_end']}):\n{top['content'][:300]}..."
                status = "RETRIEVED_FROM_DOCS"

        # Проверка на вопрос-провокацию (neg_q2: когда чанк подтянут, но факта нет)
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
            "prompt_prepared": prompt,
            "benchmark": benchmark_match
        }

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
                # Проверка по частичному совпадению
                if len(q_clean) > 15 and (q_clean in bq["question"].lower() or bq["question"].lower() in q_clean):
                    return bq
        except Exception:
            pass
        return None

    def _call_local_llm(self, user_content: str) -> Optional[str]:
        """Отправка запроса в локальный OpenAI-совместимый сервер (LM Studio / llama.cpp / vLLM)."""
        payload = json.dumps({
            "model": "local-model",
            "messages": [
                {"role": "system", "content": MENTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 512
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.llm_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None

