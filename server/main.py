import os
import sys
import json
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

# Добавляем папку src в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fastapi.staticfiles import StaticFiles

from mentor_pipeline import MentorPipeline
from database import db
from lti.router import router as lti_router
from api_routes import router as api_router, get_optional_current_user
from lti.service import decode_access_token

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация и первичное наполнение базы данных
    db.init_db()
    db.seed_db()
    yield

app = FastAPI(
    title="Frodo Mentor API & Visual Inspector",
    description="API ИИ-наставника по курсу Python с LTI 1.1 модулем и контролем сдачи лабораторных",
    version="0.3.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение модулей LTI 1.1 и API успеваемости
app.include_router(lti_router)
app.include_router(api_router)

# Подключение фронтенда студента по маршруту /chat
CLIENT_DIR = os.path.join(os.path.dirname(BASE_DIR), "client")
if os.path.exists(CLIENT_DIR):
    app.mount("/chat", StaticFiles(directory=CLIENT_DIR, html=True), name="client")

pipeline = MentorPipeline(
    db_path=os.path.join(BASE_DIR, "data", "frodo_knowledge.db"),
    embedder_url="http://localhost:8085/v1/embeddings",
    llm_url="http://localhost:8086/v1",
    relevance_threshold=0.42
)

class QueryRequest(BaseModel):
    question: str
    lab_id: Optional[int] = None
    token: Optional[str] = None

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
        "llm": "Gemma 4 E4B (port 8086)",
        "storage": "SQLite FTS5 + Vector",
        "app_db": "SQLite frodo_app.db",
        "relevance_threshold": pipeline.relevance_threshold,
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
async def query(req: QueryRequest, current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)):
    """
    Выполняет гибридный поиск, проверку Guardrail и генерацию ответа.
    Фиксирует сообщения в истории и направляет отклоненные вопросы в Gap Analysis.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    # Резолвим пользователя из заголовка/cookie либо из поля токена запроса
    if not current_user and req.token:
        payload = decode_access_token(req.token)
        if payload and payload.get("sub"):
            current_user = db.get_user_by_id(int(payload["sub"]))

    user_id = current_user["id"] if current_user else None

    res = pipeline.query(req.question, user_id=user_id, lab_id=req.lab_id)

    # Если запрос отсечен Guardrail или не найден в материалах — регистрируем в неотвеченных
    is_rejected = (
        res.get("status") == "REJECTED_BY_GUARDRAIL" or
        "В предоставленных материалах этого нет" in res.get("answer", "") or
        "Запрос отклонен" in res.get("answer", "")
    )
    if is_rejected:
        db.add_unanswered_query(
            question=req.question,
            user_id=user_id,
            score=res.get("score"),
            reason=res.get("reason", "Guardrail rejection")
        )

    # Сохраняем в историю чата, если известен пользователь
    if user_id:
        citations_str = json.dumps(res.get("citations", []), ensure_ascii=False) if res.get("citations") else None
        mode = res.get("mode", "socratic")

        db.add_chat_message(
            user_id=user_id,
            role="student",
            content=req.question,
            lab_id=req.lab_id,
            mode=mode
        )
        db.add_chat_message(
            user_id=user_id,
            role="mentor",
            content=res.get("answer", ""),
            lab_id=req.lab_id,
            mode=mode,
            citations=citations_str,
            score=res.get("score")
        )

    return res

@app.post("/api/query/stream")
async def query_stream_endpoint(
    req: QueryRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)
):
    """
    Потоковый эндпоинт генерации ответов ИИ-наставника (Server-Sent Events).
    Отдает поток событий:
    - event: meta (режим: socratic/master, скор релевантности, статус, ttft_ms)
    - event: token (порции текста)
    - event: citation (метаданные источника с номерами строк)
    - event: done (статистика генерации)
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    # Резолвим пользователя из заголовка/cookie либо из токена в теле
    if not current_user and req.token:
        payload = decode_access_token(req.token)
        if payload and payload.get("sub"):
            current_user = db.get_user_by_id(int(payload["sub"]))

    user_id = current_user["id"] if current_user else None

    return StreamingResponse(
        pipeline.query_stream_sse(
            question=req.question,
            user_id=user_id,
            lab_id=req.lab_id
        ),
        media_type="text/event-stream"
    )

@app.post("/api/reindex")
def reindex():
    docs_dir = os.path.join(BASE_DIR, "data", "docs")
    count = pipeline.index_course_materials(docs_dir)
    return {"status": "success", "indexed_chunks": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
