import os
import sys
import time
import subprocess
import urllib.request
import webbrowser

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(ROOT_DIR, "server")
LLAMA_DIR = os.path.join(ROOT_DIR, "llama_server")

def check_embedding_server():
    """Проверяет доступность локального llama-server на порту 8085."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/health", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def start_embedding_server():
    """Запускает автономный llama-server в свернутом окне при необходимости."""
    bat_path = os.path.join(LLAMA_DIR, "start_embedding_server.bat")
    if os.path.exists(bat_path):
        print("  [>] Запуск автономного llama-server (:8085)...")
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            cwd=LLAMA_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        # Ждем старта до 5 секунд
        for _ in range(10):
            time.sleep(0.5)
            if check_embedding_server():
                return True
    return False

def main():
    print("=" * 72)
    print("   FRODO: ИИ-НАСТАВНИК КУРСА (GraphRAG + RLM + Dual Guardrail)")
    print("=" * 72)
    print()

    # 1. Проверка EmbeddingGemma 2
    print("[1/3] Проверка локального сервера эмбеддингов (порт 8085)...")
    if check_embedding_server():
        print("  [OK] llama-server (EmbeddingGemma 2) активен на порту 8085.")
    else:
        started = start_embedding_server()
        if started:
            print("  [OK] llama-server успешно запущен на порту 8085.")
        else:
            print("  [WARN] Сервер эмбеддингов не ответил. Будет использован встроенный фоллбэк.")

    print()
    print("[2/3] Запуск веб-сервера Frodo AI Mentor...")
    print("  [OK] Порт сервера: http://127.0.0.1:8000")
    print("  [OK] Интерфейс (Holad UI): http://127.0.0.1:8000/chat")

    # 2. Автоматическое открытие браузера
    print()
    print("[3/3] Открытие интерфейса в браузере...")
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:8000/chat")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    print()
    print("=" * 72)
    print("   Сервер запущен! Для остановки нажмите Ctrl+C.")
    print("=" * 72)
    print()

    # 3. Запуск uvicorn
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, app_dir=SERVER_DIR)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[OK] Сервер Frodo остановлен пользователем.")
