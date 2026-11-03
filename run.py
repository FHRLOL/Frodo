import os
import sys
import time
import subprocess
import urllib.request
import webbrowser

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(ROOT_DIR, "server")
SRC_DIR = os.path.join(SERVER_DIR, "src")
LLAMA_DIR = os.path.join(ROOT_DIR, "llama_server")
MODELS_DIR = os.path.join(ROOT_DIR, "models")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def check_embedding_server():
    """Проверяет доступность локального llama-server на порту 8085."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/health", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_embedding_server():
    """Запускает автономный llama-server (EmbeddingGemma 2) в свернутом окне."""
    bat_path = os.path.join(LLAMA_DIR, "start_embedding_server.bat")
    if os.path.exists(bat_path):
        print("  [>] Запуск llama-server (EmbeddingGemma 2, порт :8085)...")
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            cwd=LLAMA_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        for _ in range(10):
            time.sleep(0.5)
            if check_embedding_server():
                return True
    return False


def check_llm_server():
    """Проверяет доступность локального llama-server на порту 8086 (Gemma 4)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8086/health", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_llm_server():
    """Запускает автономный llama-server для Gemma 4 E4B (:8086)."""
    bat_path = os.path.join(LLAMA_DIR, "start_llm_server.bat")
    gemma_path = os.path.join(MODELS_DIR, "gemma-4-e4b-it-q4_k_m.gguf")
    
    if not os.path.exists(gemma_path):
        print("  [INFO] Веса gemma-4-e4b-it-q4_k_m.gguf пока не обнаружены в models/.")
        print("         Сервер будет запущен в режиме интеллектуального RAG-фоллбэка.")
        return False

    if os.path.exists(bat_path):
        print("  [>] Запуск llama-server (Gemma 4 E4B-IT, порт :8086)...")
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            cwd=LLAMA_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        for _ in range(12):
            time.sleep(0.5)
            if check_llm_server():
                return True
    return False


def main():
    print("=" * 72)
    print("   🧙‍♂️ FRODO: ИИ-НАСТАВНИК (Gemma 4 + EmbeddingGemma 2 + LTI 1.1)")
    print("=" * 72)
    print()

    # 1. Проверка и автоматическое скачивание моделей с Hugging Face
    print("[1/4] Проверка моделей в папке models/ (Hugging Face sync)...")
    try:
        from model_downloader import ensure_models_installed
        ensure_models_installed(MODELS_DIR, auto_download=False)
    except Exception as e:
        print(f"  [INFO] Проверка загрузчика моделей: {e}")

    print()
    # 2. Проверка EmbeddingGemma 2 (порт 8085)
    print("[2/4] Проверка локального сервера эмбеддингов (порт 8085)...")
    if check_embedding_server():
        print("  [OK] llama-server (EmbeddingGemma 2) активен на порту 8085.")
    else:
        started = start_embedding_server()
        if started:
            print("  [OK] llama-server успешно запущен на порту 8085.")
        else:
            print("  [WARN] Сервер эмбеддингов не ответил. Используется встроенный фоллбэк.")

    print()
    # 3. Проверка Gemma 4 E4B (порт 8086)
    print("[3/4] Проверка локального LLM сервера (Gemma 4 E4B, порт 8086)...")
    if check_llm_server():
        print("  [OK] llama-server (Gemma 4 E4B) активен на порту 8086.")
    else:
        llm_started = start_llm_server()
        if llm_started:
            print("  [OK] llama-server (Gemma 4) успешно запущен на порту 8086.")
        else:
            print("  [INFO] Инференс-сервер LLM не активен. Активен режим эталонного RAG-наставника.")

    print()
    # 4. Запуск веб-сервера Frodo AI Mentor
    print("[4/4] Запуск веб-сервера Frodo AI Mentor...")
    print("  [OK] Порт сервера: http://127.0.0.1:8000")
    print("  [OK] Интерфейс (Holad UI): http://127.0.0.1:8000/chat")

    # Автоматическое открытие браузера
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

    # Запуск uvicorn
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, app_dir=SERVER_DIR)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[OK] Сервер Frodo остановлен пользователем.")
