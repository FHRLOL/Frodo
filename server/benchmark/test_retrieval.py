import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append("src")

from embedder import LocalEmbedder
from storage import HybridKnowledgeStore

store = HybridKnowledgeStore()
emb = LocalEmbedder()
questions = json.load(open("benchmark/questions.json", encoding="utf-8"))

print(f"{'ID':<8} | {'Score':<6} | {'Doc':<20} | {'Lines':<10} | {'Expected':<8} | Breadcrumbs")
print("-" * 80)
for q in questions:
    res = store.search_hybrid(q["question"], emb, limit=2)
    top = res[0] if res else None
    score = round(top["score"], 3) if top else 0.0
    doc = top["doc_name"] if top else "-"
    lines = f"{top['line_start']}-{top['line_end']}" if top else "-"
    crumbs = top["breadcrumbs"] if top else "-"
    print(f"{q['id']:<8} | {score:<6} | {doc:<20} | {lines:<10} | {str(q['expected_in_docs']):<8} | {crumbs}")
