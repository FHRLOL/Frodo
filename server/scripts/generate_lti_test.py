#!/usr/bin/env python3
"""
Эмулятор отправки LTI 1.1 Launch формы (тестирование ролей student и instructor).
Формирует корректную OAuth 1.0 HMAC-SHA1 подпись и отправляет запрос на сервер Frodo.
"""

import sys
import os
import time
import uuid
import argparse
import urllib.request
import urllib.parse
import html
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Добавляем server/src в sys.path для использования сервисных функций
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(SERVER_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lti.service import compute_oauth1_signature

def generate_lti_params(
    role: str = "student",
    user_id: str = "student_42",
    name: str = "Алексей Иванов",
    email: str = "student_42@university.edu",
    consumer_key: str = "frodo_lti_key",
    consumer_secret: str = "frodo_lti_secret",
    launch_url: str = "http://127.0.0.1:8000/lti/launch"
) -> dict:
    """Генерирует параметры формы LTI 1.1 с валидной OAuth 1.0 HMAC-SHA1 подписью."""
    
    # Роли по стандарту IMS LIS
    roles_str = "urn:lti:role:ims/lis/Instructor" if role == "instructor" else "urn:lti:role:ims/lis/Learner"

    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex

    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_nonce": nonce,
        "oauth_version": "1.0",
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "resource_link_id": "course_python_frodo_101",
        "context_id": "python_base_2026",
        "context_title": "Курс Python: Базовый уровень",
        "user_id": user_id,
        "roles": roles_str,
        "lis_person_name_full": name,
        "lis_person_contact_email_primary": email,
        "tool_consumer_instance_name": "University LMS Moodle"
    }

    # Вычисление подписи
    sig = compute_oauth1_signature("POST", launch_url, params, consumer_secret)
    params["oauth_signature"] = sig
    return params

def build_html_test_page(params: dict, launch_url: str) -> str:
    """Формирует HTML-форму для тестирования через браузер."""
    inputs = "\n".join(
        f'        <input type="hidden" name="{html.escape(k)}" value="{html.escape(str(v))}"/>'
        for k, v in params.items()
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>LTI Launch Test Form</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 650px; margin: 40px auto; padding: 20px; line-height: 1.5; }}
        .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        button {{ background: #2563eb; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }}
        button:hover {{ background: #1d4ed8; }}
        pre {{ background: #f8fafc; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 Frodo LTI 1.1 Launch Test</h2>
        <p>Имитация отправки формы из Moodle для пользователя: <strong>{params.get('lis_person_name_full')}</strong> (роль: <code>{params.get('roles')}</code>)</p>
        <form action="{launch_url}" method="POST">
{inputs}
            <button type="submit">Войти через LTI в Frodo</button>
        </form>
    </div>
</body>
</html>"""

def send_test_request(params: dict, launch_url: str):
    """Отправляет POST-запрос на эндпоинт LTI launch и выводит результат."""
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        launch_url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
    )

    print(f"\n[+] Отправка LTI Launch POST-запроса на {launch_url}...")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            print(f"[+] HTTP Status: {resp.status}")
            try:
                data = json.loads(body)
                print("[+] Успешный LTI вход!")
                print(f"    - Пользователь: {data.get('user', {}).get('name')} (Роль: {data.get('user', {}).get('role')})")
                print(f"    - JWT Токен: {data.get('token')[:32]}...")
                print(f"    - URL Перехода: {data.get('redirect_url')}")
            except Exception:
                print("[+] Тело ответа:")
                print(body[:300])
    except urllib.error.HTTPError as e:
        print(f"[-] Ошибка HTTP {e.code}: {e.reason}")
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"[-] Детали: {err_body}")
    except Exception as e:
        print(f"[-] Ошибка подключения: {e}")

def main():
    parser = argparse.ArgumentParser(description="LTI 1.1 Launch Test Generator for Frodo")
    parser.add_argument("--role", choices=["student", "instructor"], default="student", help="Роль пользователя (student или instructor)")
    parser.add_argument("--user-id", default=None, help="Moodle user ID (по умолчанию student_42 или instructor_1)")
    parser.add_argument("--name", default=None, help="Полное имя пользователя")
    parser.add_argument("--email", default=None, help="Email пользователя")
    parser.add_argument("--url", default="http://127.0.0.1:8000/lti/launch", help="URL LTI launch эндпоинта")
    parser.add_argument("--key", default="frodo_lti_key", help="OAuth consumer key")
    parser.add_argument("--secret", default="frodo_lti_secret", help="OAuth consumer secret")
    parser.add_argument("--html", action="store_true", help="Сгенерировать HTML страницу с формой")
    parser.add_argument("--send", action="store_true", default=False, help="Отправить HTTP запрос на работающий сервер")

    args = parser.parse_args()

    if args.role == "instructor":
        user_id = args.user_id or "instructor_1"
        name = args.name or "Проф. Смирнов А.В."
        email = args.email or "prof_smirnov@university.edu"
    else:
        user_id = args.user_id or "student_42"
        name = args.name or "Алексей Иванов"
        email = args.email or "student_42@university.edu"

    params = generate_lti_params(
        role=args.role,
        user_id=user_id,
        name=name,
        email=email,
        consumer_key=args.key,
        consumer_secret=args.secret,
        launch_url=args.url
    )

    if args.html:
        html = build_html_test_page(params, args.url)
        out_path = os.path.join(SERVER_DIR, "web", f"lti_test_{args.role}.html")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[+] HTML тестовая форма сохранена в: {out_path}")

    if args.send:
        send_test_request(params, args.url)
    else:
        print("[+] Сгенерированы параметры OAuth 1.0 HMAC-SHA1:")
        print(f"    - Роль: {args.role}")
        print(f"    - Пользователь: {name} ({user_id})")
        print(f"    - Подпись: {params['oauth_signature']}")
        print("\n[+] Пример отправки через curl:")
        post_fields = " ".join([f"-F \"{k}={v}\"" for k, v in params.items()])
        print(f"    curl -X POST \"{args.url}\" {post_fields}\n")

if __name__ == "__main__":
    main()
