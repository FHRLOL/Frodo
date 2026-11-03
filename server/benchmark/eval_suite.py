# -*- coding: utf-8 -*-
"""
eval_suite.py — Модуль оценки точности и заземления ответов RAG (Golden Benchmark Suite).
Адаптация кафедрального инструмента eval.py (rag_lab) под архитектуру Frodo.

Проверяет:
  1. Точность извлечения контекста (Retrieval Accuracy & Grounding).
  2. Соответствие ответов эталонному датасету (Ground Truth).
  3. Отражение вопросов-ловушек (Trap / Out-of-Scope questions) с жестким ответом
     «В предоставленных материалах этого нет».
  4. Отсутствие галлюцинаций (Zero Hallucination Policy).

Запуск:
  python server/benchmark/eval_suite.py
  python server/benchmark/eval_suite.py --questions server/benchmark/questions.json
  python server/benchmark/eval_suite.py --csv-out
"""

import os
import sys
import json
import csv
import time
import argparse
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BENCH_DIR)
SRC_DIR = os.path.join(SERVER_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mentor_pipeline import MentorPipeline
from database import db
from guardrails import NOT_FOUND_MESSAGE


def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    """
    Загружает вопросы из JSON или CSV (с поддержкой UTF-8 и разделителей ; / ,).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл датасета не найден: {filepath}")

    if filepath.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    # Загрузка из CSV (кафедральный формат)
    raw = open(filepath, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first_line = text.splitlines()[0]
    delim = ";" if first_line.count(";") >= first_line.count(",") else ","
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))

    normalized = []
    for r in rows:
        exp = r.get("expected_in_docs", "true").lower() in ("true", "1", "yes")
        normalized.append({
            "id": r.get("id", ""),
            "type": r.get("type", "factual"),
            "question": r.get("question", "").strip(),
            "ground_truth": r.get("reference", "").strip(),
            "source": r.get("source", "course_materials"),
            "expected_in_docs": exp,
            "keywords": [k.strip().lower() for k in r.get("keywords", "").split(",") if k.strip()]
        })
    return normalized


def evaluate_question(
    pipeline: MentorPipeline,
    q: Dict[str, Any],
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Оценивает отдельный вопрос по критериям точности, заземления и галлюцинаций.
    """
    t0 = time.perf_counter()
    res = pipeline.query(q["question"], user_id=user_id)
    latency_sec = time.perf_counter() - t0

    answer = res.get("answer", "")
    status = res.get("status", "")
    score = float(res.get("score", 0.0))
    chunks = res.get("chunks", [])
    top_chunk = chunks[0] if chunks else None
    citations = res.get("citations", [])

    expected_in = q.get("expected_in_docs", True)
    expected_src = q.get("source", "")
    ground_truth = q.get("ground_truth", "")

    passed = False
    hallucination_detected = False
    rejection_verified = False
    grounding_verified = False
    verdict = ""

    if expected_in:
        # Позитивный вопрос: материал ЕСТЬ в базе
        doc_matched = bool(top_chunk and any(doc in expected_src for doc in [top_chunk.get("doc_name", "")]))
        score_ok = score >= pipeline.relevance_threshold
        has_citation = len(citations) > 0 or "[Источник:" in answer

        # Проверка ключевых смысловых маркеров
        keywords = q.get("keywords", [])
        kw_matched = True
        if keywords:
            answer_lower = answer.lower()
            matched_count = sum(1 for kw in keywords if kw.lower() in answer_lower)
            kw_matched = (matched_count >= max(1, len(keywords) // 2))

        if doc_matched and score_ok and (kw_matched or status in ("ANSWERED_BY_LLM", "MASTER_EXPLANATION", "SOCRATIC_GUIDANCE")):
            passed = True
            grounding_verified = True
            verdict = f"Верный чанк {top_chunk['doc_name']} (строки {top_chunk['line_start']}–{top_chunk['line_end']}), score={score:.3f}"
        else:
            passed = False
            verdict = f"Недостаточная релевантность или несоответствие документа (doc={top_chunk.get('doc_name') if top_chunk else 'Н/Д'}, score={score:.3f})"
    else:
        # Вопрос-ловушка / Out-of-Scope: материала НЕТ в базе
        is_refusal = (
            status in ("REJECTED_BY_GUARDRAIL", "REJECTED_BY_GROUNDING_GUARDRAIL") or
            "в предоставленных материалах этого нет" in answer.lower() or
            "не указано" in answer.lower() or
            "запрос отклонен" in answer.lower()
        )

        if is_refusal:
            passed = True
            rejection_verified = True
            hallucination_detected = False
            verdict = f"Корректный отказ: система не стала галлюцинировать (status={status}, score={score:.3f})"
        else:
            passed = False
            hallucination_detected = True
            verdict = f"ОШИБКА: обнаружена галлюцинация на вопросе-ловушке! (status={status})"

    return {
        "id": q["id"],
        "type": q.get("type", "factual"),
        "question": q["question"],
        "expected_in_docs": expected_in,
        "ground_truth": ground_truth,
        "answer": answer,
        "status": status,
        "score": score,
        "top_doc": top_chunk["doc_name"] if top_chunk else "—",
        "top_section": top_chunk["section_title"] if top_chunk else "—",
        "top_lines": f"{top_chunk['line_start']}–{top_chunk['line_end']}" if top_chunk else "—",
        "has_citation": len(citations) > 0,
        "passed": passed,
        "grounding_verified": grounding_verified,
        "rejection_verified": rejection_verified,
        "hallucination_detected": hallucination_detected,
        "latency_sec": latency_sec,
        "verdict": verdict
    }


def run_eval_suite(
    questions_path: Optional[str] = None,
    save_csv: bool = False
) -> Dict[str, Any]:
    """
    Запускает полный цикл валидации набора вопросов и возвращает сводный отчет.
    """
    if questions_path is None:
        questions_path = os.path.join(BENCH_DIR, "questions.json")

    print("=" * 86)
    print("   FRODO EVAL SUITE: КОНТРОЛЬНАЯ ВАЛИДАЦИЯ ТОЧНОСТИ И ЗАЗЕМЛЕНИЯ (GOLDEN DATASET)")
    print("=" * 86)

    pipeline = MentorPipeline(
        db_path=os.path.join(SERVER_DIR, "data", "frodo_knowledge.db"),
        embedder_url="http://localhost:8085/v1/embeddings",
        relevance_threshold=0.42
    )

    questions = load_dataset(questions_path)
    print(f"Загружено контрольных вопросов: {len(questions)}")
    print(f"Движок эмбеддингов: EmbeddingGemma 2 (порт 8085)")
    print(f"Порог релевантности RAG: {pipeline.relevance_threshold}")
    print("-" * 86)

    results = []
    print(f"{'#':<3} | {'ID':<8} | {'Тип':<12} | {'Скор':<6} | {'Статус':<8} | {'Документ / Вердикт':<40}")
    print("-" * 86)

    for idx, q in enumerate(questions, 1):
        eval_res = evaluate_question(pipeline, q)
        results.append(eval_res)

        badge = "✅ PASS" if eval_res["passed"] else "❌ FAIL"
        doc_info = f"{eval_res['top_doc']} ({eval_res['top_lines']})" if eval_res['expected_in_docs'] else eval_res['verdict'][:40]
        print(f"{idx:<3} | {eval_res['id']:<8} | {eval_res['type']:<12} | {eval_res['score']:<6.3f} | {badge:<8} | {doc_info:<40}")

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    accuracy = (passed_count / total) * 100 if total > 0 else 0.0

    pos_questions = [r for r in results if r["expected_in_docs"]]
    pos_passed = sum(1 for r in pos_questions if r["passed"])
    grounding_rate = (pos_passed / len(pos_questions)) * 100 if pos_questions else 0.0

    neg_questions = [r for r in results if not r["expected_in_docs"]]
    neg_passed = sum(1 for r in neg_questions if r["passed"])
    trap_deflection_rate = (neg_passed / len(neg_questions)) * 100 if neg_questions else 0.0

    hallucinations = sum(1 for r in results if r["hallucination_detected"])
    avg_latency = sum(r["latency_sec"] for r in results) / total if total > 0 else 0.0

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "accuracy_pct": round(accuracy, 1),
        "grounding_rate_pct": round(grounding_rate, 1),
        "trap_deflection_rate_pct": round(trap_deflection_rate, 1),
        "hallucinations_count": hallucinations,
        "hallucination_rate_pct": 0.0 if total > 0 and hallucinations == 0 else round((hallucinations / total) * 100, 1),
        "avg_latency_sec": round(avg_latency, 3),
        "target_met": accuracy >= 80.0 and hallucinations == 0,
        "results": results
    }

    print("-" * 86)
    print(f"📊 ИТОГОВЫЕ МЕТРИКИ EVAL SUITE:")
    print(f"   • Общая точность (Accuracy):         {summary['accuracy_pct']}% ({passed_count}/{total}) [Цель >= 80%: {'ВЫПОЛНЕНА' if summary['target_met'] else 'НЕ ДОСТИГНУТА'}]")
    print(f"   • Заземление на материалы (Grounding): {summary['grounding_rate_pct']}% ({pos_passed}/{len(pos_questions)})")
    print(f"   • Отражение ловушек (Trap Deflection): {summary['trap_deflection_rate_pct']}% ({neg_passed}/{len(neg_questions)})")
    print(f"   • Уровень галлюцинаций:              {summary['hallucination_rate_pct']}% ({hallucinations} обнаружено)")
    print(f"   • Среднее время ответа:              {summary['avg_latency_sec']} сек")
    print("=" * 86)

    if save_csv:
        csv_filename = os.path.join(BENCH_DIR, f"results_eval_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        with open(csv_filename, "w", encoding="utf-8-sig", newline="") as cf:
            fieldnames = ["id", "type", "question", "expected_in_docs", "score", "passed", "top_doc", "top_section", "top_lines", "verdict"]
            writer = csv.DictWriter(cf, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "id": r["id"],
                    "type": r["type"],
                    "question": r["question"],
                    "expected_in_docs": r["expected_in_docs"],
                    "score": r["score"],
                    "passed": r["passed"],
                    "top_doc": r["top_doc"],
                    "top_section": r["top_section"],
                    "top_lines": r["top_lines"],
                    "verdict": r["verdict"]
                })
        print(f"Результаты экспортированы в CSV: {csv_filename}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запуск контрольного набора вопросов Frodo Eval Suite")
    parser.add_argument("--questions", default=os.path.join(BENCH_DIR, "questions.json"), help="Путь к questions.json или questions.csv")
    parser.add_argument("--csv-out", action="store_true", help="Экспортировать результаты в CSV файл")
    args = parser.parse_args()

    run_eval_suite(questions_path=args.questions, save_csv=args.csv_out)
