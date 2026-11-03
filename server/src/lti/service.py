import os
import hmac
import hashlib
import base64
import time
from urllib.parse import quote, urlparse, urlunparse
from typing import Dict, Any, Optional, Tuple, List
import jwt
from datetime import datetime, timedelta, timezone

# Секреты для LTI Consumer (по умолчанию frodo_lti_key / frodo_lti_secret)
DEFAULT_CONSUMER_KEY = os.getenv("LTI_CONSUMER_KEY", "frodo_lti_key")
DEFAULT_CONSUMER_SECRET = os.getenv("LTI_CONSUMER_SECRET", "frodo_lti_secret")

LTI_CONSUMERS: Dict[str, str] = {
    DEFAULT_CONSUMER_KEY: DEFAULT_CONSUMER_SECRET,
    "moodle_frodo": "frodo_secret_2026",
    "schedule_dev": "frodo_lti_secret"
}

JWT_SECRET = os.getenv("JWT_SECRET", "frodo-jwt-secret-key-deepmind-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 суток действия сессионного токена

def rfc3986_quote(val: Any) -> str:
    """
    Кодирование параметров в соответствии с RFC 5849 / RFC 3986:
    Символы [A-Za-z0-9-._~] не экранируются.
    """
    return quote(str(val), safe="~")

def normalize_url(url: str) -> str:
    """
    Нормализует базовый URL согласно RFC 5849 Section 3.4.1.2:
    - Схема и хост приводятся к нижнему регистру.
    - Стандартные порты (80 для http, 443 для https) исключаются.
    - Query-параметры и фрагменты удаляются.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Очистка стандартных портов
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))

def build_normalized_param_string(params: Dict[str, Any]) -> str:
    """
    Нормализует параметры согласно RFC 5849 Section 3.4.1.3.2:
    - Исключает oauth_signature.
    - Экранирует ключ и значение.
    - Сортирует лексикографически по ключу, затем по значению.
    - Соединяет в строку вида k1=v1&k2=v2.
    """
    items: List[Tuple[str, str]] = []
    for k, v in params.items():
        if k == "oauth_signature":
            continue
        encoded_k = rfc3986_quote(k)
        encoded_v = rfc3986_quote(v if v is not None else "")
        items.append((encoded_k, encoded_v))

    # Сортировка по кодированному ключу, затем значению
    items.sort(key=lambda x: (x[0], x[1]))
    return "&".join(f"{k}={v}" for k, v in items)

def build_signature_base_string(method: str, url: str, params: Dict[str, Any]) -> str:
    """
    Строит Signature Base String:
    HTTP_METHOD & normalized_url & normalized_parameters
    """
    norm_method = method.upper()
    norm_url = normalize_url(url)
    norm_params = build_normalized_param_string(params)

    return f"{rfc3986_quote(norm_method)}&{rfc3986_quote(norm_url)}&{rfc3986_quote(norm_params)}"

def compute_oauth1_signature(method: str, url: str, params: Dict[str, Any], consumer_secret: str) -> str:
    """
    Вычисляет OAuth 1.0 HMAC-SHA1 подпись.
    В LTI 1.1 token_secret отсутствует, поэтому ключ: quote(consumer_secret) + "&".
    """
    base_string = build_signature_base_string(method, url, params)
    signing_key = f"{rfc3986_quote(consumer_secret)}&"

    hashed = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1
    )
    return base64.b64encode(hashed.digest()).decode("utf-8")

def verify_lti_request(
    method: str,
    url: str,
    params: Dict[str, Any],
    fallback_consumer_secret: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет OAuth 1.0 HMAC-SHA1 подпись LTI 1.1 запроса.
    Возвращает (успех: bool, сообщение_об_ошибке: Optional[str]).
    """
    consumer_key = params.get("oauth_consumer_key")
    if not consumer_key:
        return False, "Отсутствует параметр 'oauth_consumer_key'"

    secret = LTI_CONSUMERS.get(consumer_key, fallback_consumer_secret or DEFAULT_CONSUMER_SECRET)
    if not secret:
        return False, f"Неизвестный consumer key: {consumer_key}"

    sig_method = params.get("oauth_signature_method")
    if sig_method != "HMAC-SHA1":
        return False, f"Неподдерживаемый метод подписи: {sig_method}. Требуется HMAC-SHA1"

    received_sig = params.get("oauth_signature")
    if not received_sig:
        return False, "Отсутствует параметр 'oauth_signature'"

    # Проверка метки времени (допустимый лаг 15 минут)
    timestamp = params.get("oauth_timestamp")
    if timestamp:
        try:
            req_time = int(timestamp)
            now = int(time.time())
            if abs(now - req_time) > 900:  # 15 минут
                return False, f"Истек oauth_timestamp (разница {abs(now - req_time)} сек)"
        except ValueError:
            return False, "Неверный формат oauth_timestamp"

    # Формируем кандидатов URL (на случай проксирования / 127.0.0.1 / localhost)
    candidate_urls = [url]
    parsed = urlparse(url)
    
    # Вариант с заменой 127.0.0.1 на localhost или наоборот
    if "127.0.0.1" in parsed.netloc:
        candidate_urls.append(url.replace("127.0.0.1", "localhost"))
    elif "localhost" in parsed.netloc:
        candidate_urls.append(url.replace("localhost", "127.0.0.1"))

    # Вариант без порта / с портом
    for candidate in candidate_urls:
        expected_sig = compute_oauth1_signature(method, candidate, params, secret)
        if hmac.compare_digest(expected_sig, received_sig):
            return True, None

    return False, "Неверная цифровая подпись HMAC-SHA1"

def parse_lti_roles(roles_str: str) -> str:
    """
    Определяет роль пользователя ('instructor' или 'student')
    на основе параметров roles LTI 1.1 / IMS LIS.
    """
    if not roles_str:
        return "student"

    instructor_keywords = {
        "instructor", "teacher", "administrator", "admin", "staff",
        "urn:lti:role:ims/lis/instructor",
        "urn:lti:role:ims/lis/teachingassistant",
        "urn:lti:sysrole:ims/lis/administrator"
    }

    raw_tokens = [t.strip().lower() for t in roles_str.replace(";", ",").split(",") if t.strip()]
    for token in raw_tokens:
        for kw in instructor_keywords:
            if kw in token:
                return "instructor"

    return "student"

def extract_user_from_lti(params: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает и нормализует профиль пользователя из параметров LTI launch."""
    moodle_user_id = (
        params.get("user_id") or
        params.get("lis_person_sourcedid") or
        params.get("ext_user_username") or
        "student_unknown"
    )

    full_name = params.get("lis_person_name_full")
    if not full_name:
        given = params.get("lis_person_name_given", "").strip()
        family = params.get("lis_person_name_family", "").strip()
        full_name = f"{given} {family}".strip()

    if not full_name:
        full_name = f"Пользователь {moodle_user_id}"

    email = params.get("lis_person_contact_email_primary")
    roles_raw = params.get("roles", "")
    role = parse_lti_roles(roles_raw)

    return {
        "moodle_user_id": moodle_user_id,
        "name": full_name,
        "email": email,
        "role": role
    }

# ----------------- JWT Сессии -----------------

def create_access_token(user: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создает сессионный JWT токен для пользователя."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "sub": str(user["id"]),
        "moodle_user_id": user["moodle_user_id"],
        "name": user["name"],
        "email": user.get("email"),
        "role": user["role"],
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp())
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Декодирует и верифицирует сессионный JWT токен."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None
