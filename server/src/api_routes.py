from fastapi import APIRouter, Depends, HTTPException, Query, Header, Cookie, Request, status
from typing import Optional, List, Dict, Any

from database import db
from models import (
    UserProfile,
    LabItem,
    LabProgressItem,
    ProgressUpdateRequest,
    UnansweredQueryItem,
    StudentMatrixItem,
    LabStatus
)
from lti.service import decode_access_token

router = APIRouter(prefix="/api", tags=["API Успеваемости и Авторизации"])

# ----------------- Зависимости Авторизации -----------------

async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    frodo_token: Optional[str] = Cookie(None)
) -> Dict[str, Any]:
    """
    Извлекает сессионного пользователя из:
    1. Заголовка Authorization: Bearer <token>
    2. Query параметра ?token=<token>
    3. Cookie frodo_token
    """
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    elif token:
        raw_token = token.strip()
    elif frodo_token:
        raw_token = frodo_token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация (отсутствует JWT токен)",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(raw_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший JWT токен",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная структура токена"
        )

    user = db.get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден в базе данных"
        )

    return user

async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    frodo_token: Optional[str] = Cookie(None)
) -> Optional[Dict[str, Any]]:
    """Опциональное получение пользователя без генерации 401 ошибки."""
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    elif token:
        raw_token = token.strip()
    elif frodo_token:
        raw_token = frodo_token.strip()

    if not raw_token:
        return None

    payload = decode_access_token(raw_token)
    if not payload or not payload.get("sub"):
        return None

    return db.get_user_by_id(int(payload["sub"]))

def require_instructor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Проверка прав преподавателя (RBAC)."""
    if user["role"] != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен: действие разрешено только преподавателям (instructor)"
        )
    return user

# ----------------- Эндпоинты Авторизации и Профиля -----------------

@router.get("/auth/me", response_model=UserProfile)
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Получение профиля текущего авторизованного пользователя."""
    return user

# ----------------- Эндпоинты Лабораторных Работ -----------------

@router.get("/labs", response_model=List[LabItem])
def get_labs():
    """Получение каталога всех лабораторных работ курса."""
    return db.get_all_labs()

# ----------------- Эндпоинты Прогресса Студента -----------------

@router.get("/student/progress", response_model=List[LabProgressItem])
def get_student_progress(
    user_id: Optional[int] = Query(None, description="ID студента (доступно только преподавателям)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Получение прогресса по лабораторным работам.
    - Студент получает собственный прогресс.
    - Преподаватель может запросить прогресс любого студента по user_id.
    """
    target_user_id = current_user["id"]

    if user_id is not None:
        if current_user["role"] != "instructor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Просмотр прогресса других студентов разрешен только преподавателям"
            )
        target_user = db.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Студент не найден")
        target_user_id = user_id

    return db.get_student_progress(target_user_id)

# ----------------- Эндпоинты Преподавателя (Admin / Instructor) -----------------

@router.get("/admin/students", response_model=List[StudentMatrixItem])
def get_admin_students(instructor: Dict[str, Any] = Depends(require_instructor)):
    """
    Сводная матрица успеваемости всех студентов по всем лабораторным работам.
    Доступна только преподавателям.
    """
    return db.get_all_students_progress_matrix()

@router.post("/admin/student/progress", response_model=LabProgressItem)
def update_student_progress(
    req: ProgressUpdateRequest,
    instructor: Dict[str, Any] = Depends(require_instructor)
):
    """
    Обновление статуса сдачи лабы ('not_started' | 'in_progress' | 'passed') и оценки.
    Доступно только преподавателям.
    """
    # Проверяем существование студента
    student = db.get_user_by_id(req.user_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Студент не найден")

    # Проверяем существование лабораторной
    lab = db.get_lab_by_id(req.lab_id)
    if not lab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Лабораторная работа не найдена")

    # Обновляем прогресс
    updated = db.update_student_lab_progress(
        user_id=req.user_id,
        lab_id=req.lab_id,
        status=req.status.value,
        grade=req.grade
    )
    return updated

@router.get("/admin/unanswered", response_model=List[UnansweredQueryItem])
def get_admin_unanswered(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    instructor: Dict[str, Any] = Depends(require_instructor)
):
    """
    Получение списка неотвеченных запросов студентов (Gap Analysis).
    Используется преподавателем для выявления тем, отсутствующих в базе знаний курса.
    """
    return db.get_unanswered_queries(limit=limit, offset=offset)
