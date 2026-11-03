import sqlite3
import json
import os
from typing import List, Dict, Any, Tuple
from parser import DocumentChunk
from embedder import LocalEmbedder

class HybridKnowledgeStore:
    """
    Гибридное хранилище базы знаний на базе SQLite + FTS5:
    - Слой 1: Полнотекстовый поиск BM25 (FTS5) для точных совпадений синтаксиса и операторов.
    - Слой 2: Векторный индекс на эмбеддингах EmbeddingGemma 2 для смыслового поиска.
    - Слой 3: Метаданные (название документа, раздел, хлебные крошки, строки L_start..L_end).
    """

    def __init__(self, db_path: str = "data/frodo_knowledge.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_name TEXT,
                    section_title TEXT,
                    breadcrumbs TEXT,
                    line_start INTEGER,
                    line_end INTEGER,
                    content TEXT,
                    raw_text TEXT,
                    embedding_json TEXT
                )
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                    chunk_id UNINDEXED,
                    doc_name,
                    section_title,
                    breadcrumbs,
                    content,
                    tokenize = 'porter unicode61'
                )
            """)

    def index_chunks(self, chunks: List[DocumentChunk], embedder: LocalEmbedder):
        """Индексирует все чанки в реляционную таблицу, FTS5 и векторное хранилище."""
        with self.conn:
            self.conn.execute("DELETE FROM chunks")
            self.conn.execute("DELETE FROM fts_chunks")

            for c in chunks:
                emb = embedder.get_embedding(c.content)
                emb_str = json.dumps(emb)
                self.conn.execute("""
                    INSERT INTO chunks (chunk_id, doc_name, section_title, breadcrumbs, line_start, line_end, content, raw_text, embedding_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (c.chunk_id, c.doc_name, c.section_title, c.breadcrumbs, c.line_start, c.line_end, c.content, c.raw_text, emb_str))

                self.conn.execute("""
                    INSERT INTO fts_chunks (chunk_id, doc_name, section_title, breadcrumbs, content)
                    VALUES (?, ?, ?, ?, ?)
                """, (c.chunk_id, c.doc_name, c.section_title, c.breadcrumbs, c.content))

    def search_bm25(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Полнотекстовый поиск BM25 через SQLite FTS5."""
        # Очищаем запрос для безопасного FTS5 синтаксиса
        clean_tokens = [w for w in query.replace('"', ' ').replace("'", " ").replace("-", " ").split() if len(w) > 1]
        if not clean_tokens:
            return []
        
        fts_query = " OR ".join([f'"{tok}"*' for tok in clean_tokens[:8]])
        results = []
        try:
            cursor = self.conn.execute("""
                SELECT c.chunk_id, c.doc_name, c.section_title, c.breadcrumbs, c.line_start, c.line_end, c.content,
                       bm25(fts_chunks) AS bm25_rank
                FROM fts_chunks f
                JOIN chunks c ON f.chunk_id = c.chunk_id
                WHERE fts_chunks MATCH ?
                ORDER BY bm25_rank
                LIMIT ?
            """, (fts_query, limit))
            for row in cursor.fetchall():
                # bm25 в sqlite fts5 возвращает отрицательные значения (меньше = лучше)
                norm_score = max(0.0, 1.0 / (1.0 + abs(row["bm25_rank"])))
                results.append({
                    "chunk_id": row["chunk_id"],
                    "doc_name": row["doc_name"],
                    "section_title": row["section_title"],
                    "breadcrumbs": row["breadcrumbs"],
                    "line_start": row["line_start"],
                    "line_end": row["line_end"],
                    "content": row["content"],
                    "score": norm_score,
                    "type": "bm25"
                })
        except Exception:
            pass
        return results

    def search_vector(self, query_emb: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Векторный поиск по косинусному сходству."""
        cursor = self.conn.execute("SELECT chunk_id, doc_name, section_title, breadcrumbs, line_start, line_end, content, embedding_json FROM chunks")
        scored = []
        for row in cursor.fetchall():
            emb = json.loads(row["embedding_json"])
            sim = LocalEmbedder.cosine_similarity(query_emb, emb)
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, row in scored[:limit]:
            results.append({
                "chunk_id": row["chunk_id"],
                "doc_name": row["doc_name"],
                "section_title": row["section_title"],
                "breadcrumbs": row["breadcrumbs"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "content": row["content"],
                "score": sim,
                "type": "vector"
            })
        return results

    def search_hybrid(self, query: str, embedder: LocalEmbedder, limit: int = 4, alpha: float = 0.5) -> List[Dict[str, Any]]:
        """
        Гибридный поиск с комбинированием рангов:
        Score = alpha * Vector_Score + (1 - alpha) * BM25_Score
        """
        query_emb = embedder.get_embedding(query)
        v_results = self.search_vector(query_emb, limit=limit * 2)
        b_results = self.search_bm25(query, limit=limit * 2)

        # Объединяем чанки
        merged: Dict[str, Dict[str, Any]] = {}

        for vr in v_results:
            cid = vr["chunk_id"]
            merged[cid] = dict(vr)
            merged[cid]["vector_score"] = vr["score"]
            merged[cid]["bm25_score"] = 0.0

        for br in b_results:
            cid = br["chunk_id"]
            if cid in merged:
                merged[cid]["bm25_score"] = br["score"]
            else:
                merged[cid] = dict(br)
                merged[cid]["vector_score"] = 0.0
                merged[cid]["bm25_score"] = br["score"]

        # Рассчитываем итоговый гибридный скор
        final_list = []
        for cid, item in merged.items():
            final_score = alpha * item["vector_score"] + (1 - alpha) * item["bm25_score"]
            item["score"] = final_score
            final_list.append(item)

        final_list.sort(key=lambda x: x["score"], reverse=True)
        return final_list[:limit]
