import os
import sys
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Добавляем папку src в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fastapi.staticfiles import StaticFiles

from mentor_pipeline import MentorPipeline

app = FastAPI(title="Frodo Mentor API & Visual Inspector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение фронтенда студента по маршруту /chat
CLIENT_DIR = os.path.join(os.path.dirname(BASE_DIR), "client")
if os.path.exists(CLIENT_DIR):
    app.mount("/chat", StaticFiles(directory=CLIENT_DIR, html=True), name="client")

pipeline = MentorPipeline(
    db_path=os.path.join(BASE_DIR, "data", "frodo_knowledge.db"),
    embedder_url="http://localhost:8085/v1/embeddings",
    relevance_threshold=0.45
)

class QueryRequest(BaseModel):
    question: str

@app.get("/", response_class=HTMLResponse)
def index_page():
    """Отдает главную страницу наглядного визуального инспектора поиска и ответов."""
    web_file = os.path.join(BASE_DIR, "web", "index.html")
    if os.path.exists(web_file):
        with open(web_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frodo Visual Inspector: backend/web/index.html not found</h1>"

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "embedder": "EmbeddingGemma 2 (port 8085)",
        "storage": "SQLite FTS5 + Vector",
        "docs_dir": os.path.join(BASE_DIR, "data", "docs")
    }

@app.get("/api/benchmark")
def get_benchmark():
    """Возвращает список контрольных вопросов с эталонами."""
    bench_file = os.path.join(BASE_DIR, "benchmark", "questions.json")
    if os.path.exists(bench_file):
        with open(bench_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.post("/api/query")
def query(req: QueryRequest):
    """Выполняет гибридный поиск, проверку Guardrail и генерацию ответа."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")
    res = pipeline.query(req.question)
    return res

@app.post("/api/reindex")
def reindex():
    docs_dir = os.path.join(BASE_DIR, "data", "docs")
    count = pipeline.index_course_materials(docs_dir)
    return {"status": "success", "indexed_chunks": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
