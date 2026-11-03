import os
from fastapi import APIRouter, Request, HTTPException, Form, Response, status
from fastapi.responses import RedirectResponse, Response as PlainResponse
from typing import Optional, Dict, Any

from database import db
from lti.service import verify_lti_request, extract_user_from_lti, create_access_token

router = APIRouter(prefix="/lti", tags=["LTI 1.1"])

@router.post("/launch")
@router.post("")
async def lti_launch(request: Request):
    """
    Основной LTI 1.1 Launch эндпоинт:
    1. Принимает POST form-data от LMS (Moodle, Canvas, etc.).
    2. Верифицирует OAuth 1.0 HMAC-SHA1 подпись.
    3. Создает или обновляет пользователя в БД.
    4. Инициализирует прогресс по лабам для студента.
    5. Генерирует JWT сессионный токен.
    6. Выполняет 303 Redirect на интерфейс студента (/chat?token=...) или возвращает JSON.
    """
    form_data = await request.form()
    params: Dict[str, Any] = {k: v for k, v in form_data.items()}

    # Проверка цифровой подписи OAuth 1.0
    request_url = str(request.url)
    # Обработка возможного X-Forwarded заголовка за обратным прокси
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        request_url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"

    valid, err_msg = verify_lti_request(
        method=request.method,
        url=request_url,
        params=params
    )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"LTI Launch Verification Failed: {err_msg}"
        )

    # Извлечение и нормализация данных пользователя
    user_data = extract_user_from_lti(params)
    user = db.create_or_update_user(
        moodle_user_id=user_data["moodle_user_id"],
        name=user_data["name"],
        email=user_data["email"],
        role=user_data["role"]
    )

    # Если студент — гарантируем прогресс по лабораторным
    if user["role"] == "student":
        db.ensure_student_progress_records(user["id"])

    # Генерация JWT сессии
    token = create_access_token(user)

    # Проверяем формат ответа (JSON или редирект в браузер)
    accept_header = request.headers.get("accept", "")
    wants_json = "application/json" in accept_header or params.get("format") == "json"

    redirect_target = f"/chat?token={token}"

    if wants_json:
        return {
            "status": "success",
            "token": token,
            "user": user,
            "redirect_url": redirect_target
        }

    # Редирект в веб-интерфейс чата с кукой и токеном в параметре
    redirect_resp = RedirectResponse(url=redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.set_cookie(
        key="frodo_token",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    return redirect_resp

@router.get("/config.xml")
def lti_config_xml(request: Request):
    """
    Отдает XML-конфигурацию LTI 1.1 Tool Provider для быстрой интеграции в Moodle/Canvas.
    """
    host = request.headers.get("host", "127.0.0.1:8000")
    scheme = "https" if request.url.is_secure else "http"
    launch_url = f"{scheme}://{host}/lti/launch"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<cartridge_basiclti_link xmlns="http://www.imsglobal.org/xsd/imslticc_v1p0"
    xmlns:blti="http://www.imsglobal.org/xsd/imsbasiclti_v1p0"
    xmlns:lticm="http://www.imsglobal.org/xsd/imslticm_v1p0"
    xmlns:lticp="http://www.imsglobal.org/xsd/imslticp_v1p0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imslticc_v1p0 http://www.imsglobal.org/xsd/lti/ltiv1p0/imslticc_v1p0.xsd">
    <blti:title>Frodo AI Mentor</blti:title>
    <blti:description>Интеллектуальный наставник по курсу Python с контролем сдачи лабораторных работ</blti:description>
    <blti:launch_url>{launch_url}</blti:launch_url>
    <blti:icon></blti:icon>
    <blti:extensions platform="canvas.instructure.com">
        <lticm:property name="privacy_level">public</lticm:property>
    </blti:extensions>
</cartridge_basiclti_link>
"""
    return PlainResponse(content=xml_content, media_type="application/xml")
