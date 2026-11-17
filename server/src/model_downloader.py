# -*- coding: utf-8 -*-
"""
Модуль автоматической проверки и высокоскоростного докачивания весов моделей с Hugging Face / CDN.
Поддерживает:
1. EmbeddingGemma 2 (embeddinggemma-2-Q8_0.gguf)
2. Gemma 4 E4B-IT (gemma-4-e4b-it-q4_k_m.gguf)

Особенности:
- Прямой резолв Hugging Face CDN (AWS CloudFront / HF CDN) для исключения 302-редиректов.
- Многопоточное скачивание параллельными чанками (Range requests) с замером скорости (МБ/с) в реальном времени.
- Автоматическое переключение на зеркала (hf-mirror.com) и альтернативные публичные репозитории (unsloth, lmstudio-community).
- Докачка (resumable) при обрыве соединения и валидация заголовков GGUF (magic bytes b'GGUF').
- Сохранение СТРОГО в целевую директорию models/ без засорения системного кэша.
"""

import os
import sys
import time
import json
import shutil
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(ROOT_DIR, "models")

MODELS_CONFIG: Dict[str, Dict[str, Any]] = {
    "embedding": {
        "filename": "embeddinggemma-2-Q8_0.gguf",
        "remote_filenames": ["embeddinggemma-2-Q8_0.gguf"],
        "repo_id": "google/embeddinggemma-2-GGUF",
        "desc": "EmbeddingGemma 2 (Q8_0, ~300 МБ) — эмбеддер RAG",
        "fallback_repos": ["bartowski/embeddinggemma-2-GGUF"],
        "min_size_bytes": 100 * 1024 * 1024  # > 100 MB
    },
    "llm": {
        "filename": "gemma-4-e4b-it-q4_k_m.gguf",
        "remote_filenames": [
            "gemma-4-E4B-it-Q4_K_M.gguf",
            "gemma-4-e4b-it-q4_k_m.gguf"
        ],
        "repo_id": "unsloth/gemma-4-e4b-it-GGUF",  # Публичный и самый быстрый репозиторий
        "desc": "Gemma 4 E4B-IT (Q4_K_M, ~4.6 ГБ) — локальная LLM наставника",
        "fallback_repos": [
            "lmstudio-community/gemma-4-E4B-it-GGUF",
            "google/gemma-4-e4b-it-GGUF",
            "bartowski/gemma-4-e4b-it-GGUF"
        ],
        "min_size_bytes": 500 * 1024 * 1024  # > 500 MB
    }
}


def verify_gguf_integrity(file_path: str, min_size: int = 1024 * 1024) -> bool:
    """Проверяет сигнатуру b'GGUF' и минимальный размер файла."""
    if not os.path.exists(file_path):
        return False
    size = os.path.getsize(file_path)
    if size < min_size:
        return False
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
            return magic == b"GGUF"
    except Exception:
        return False


def get_cdn_direct_url(initial_url: str, timeout: float = 12.0) -> Tuple[Optional[str], int, bool]:
    """
    Получает конечный CDN URL, размер файла и поддержку Range.
    Возвращает (cdn_url, content_length, supports_range).
    """
    headers = {"User-Agent": "Frodo-Model-Downloader/2.0"}
    req = urllib.request.Request(initial_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            cl = int(resp.headers.get("Content-Length", 0))
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
            return final_url, cl, accept_ranges
    except Exception as e:
        return None, 0, False


def download_chunk(
    cdn_url: str,
    dest_path: str,
    start: int,
    end: int,
    chunk_idx: int,
    progress_callback,
    max_retries: int = 3
) -> bool:
    """Загружает один байтовый диапазон [start, end] и записывает в файл."""
    expected_bytes = end - start + 1
    headers = {
        "User-Agent": "Frodo-Model-Downloader/2.0",
        "Range": f"bytes={start}-{end}"
    }

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(cdn_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                downloaded_chunk = 0
                buf_size = 512 * 1024  # 512 KB буфер
                with open(dest_path, "r+b") as f_out:
                    f_out.seek(start)
                    while True:
                        buf = resp.read(buf_size)
                        if not buf:
                            break
                        f_out.write(buf)
                        downloaded_chunk += len(buf)
                        progress_callback(len(buf))

                if downloaded_chunk == expected_bytes:
                    return True
                else:
                    progress_callback(-(downloaded_chunk))
        except Exception:
            time.sleep(1.0 * attempt)
            continue
    return False


def download_parallel(
    cdn_url: str,
    dest_path: str,
    total_size: int,
    desc: str,
    num_workers: int = 10,
    chunk_size: int = 32 * 1024 * 1024
) -> bool:
    """
    Высокоскоростное многопоточное скачивание файла параллельными чанками.
    Выводит скорость (МБ/с), процент выполнения и ETA в реальном времени.
    """
    part_path = dest_path + ".part"
    meta_path = dest_path + ".parts.json"

    # Преаллокация файла нужного размера
    already_done_chunks = set()
    if os.path.exists(meta_path) and os.path.exists(part_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f_meta:
                meta = json.load(f_meta)
                if meta.get("total_size") == total_size:
                    already_done_chunks = set(meta.get("completed_chunks", []))
                    print(f"  [RESUME] Найдена незавершенная загрузка: восстановлено {len(already_done_chunks)} чанков.")
        except Exception:
            already_done_chunks = set()

    if not os.path.exists(part_path) or os.path.getsize(part_path) != total_size:
        print(f"  [>] Инициализация дискового пространства ({total_size / (1024**3):.2f} ГБ)...")
        with open(part_path, "wb") as f_pre:
            f_pre.truncate(total_size)
        already_done_chunks = set()

    # Формирование списка чанков
    num_chunks = (total_size + chunk_size - 1) // chunk_size
    chunks_to_dl = []
    initial_downloaded = 0

    for i in range(num_chunks):
        c_start = i * chunk_size
        c_end = min(total_size - 1, (i + 1) * chunk_size - 1)
        c_bytes = c_end - c_start + 1
        if i in already_done_chunks:
            initial_downloaded += c_bytes
        else:
            chunks_to_dl.append((i, c_start, c_end))

    if not chunks_to_dl:
        print("  [OK] Все чанки уже загружены.")
        shutil.move(part_path, dest_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return True

    # Потокобезопасный счетчик байт
    lock = threading.Lock()
    total_downloaded = [initial_downloaded]
    completed_chunks = set(already_done_chunks)
    stop_event = threading.Event()
    start_time = time.time()
    last_reported_time = [start_time]
    last_reported_bytes = [initial_downloaded]

    def on_progress(num_bytes: int):
        with lock:
            total_downloaded[0] += num_bytes

    def progress_reporter():
        while not stop_event.is_set():
            time.sleep(0.5)
            with lock:
                curr_bytes = total_downloaded[0]
            now = time.time()
            dt = now - last_reported_time[0]
            if dt >= 0.5:
                speed = (curr_bytes - last_reported_bytes[0]) / (dt * 1024 * 1024)
                last_reported_time[0] = now
                last_reported_bytes[0] = curr_bytes

                percent = (curr_bytes / total_size) * 100 if total_size > 0 else 0
                mb_done = curr_bytes / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)

                rem_bytes = max(0, total_size - curr_bytes)
                if speed > 0.05:
                    eta_sec = int(rem_bytes / (speed * 1024 * 1024))
                    m, s = divmod(eta_sec, 60)
                    eta_str = f"{m:02d}:{s:02d}"
                else:
                    eta_str = "--:--"

                sys.stdout.write(
                    f"\r  [>>] {desc}: {percent:5.1f}% ({mb_done:.1f}/{mb_total:.1f} МБ) | "
                    f"Скорость: {speed:5.1f} МБ/с | ETA: {eta_str}   "
                )
                sys.stdout.flush()

    reporter_thread = threading.Thread(target=progress_reporter, daemon=True)
    reporter_thread.start()

    success_all = True
    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_chunk = {
                executor.submit(
                    download_chunk,
                    cdn_url,
                    part_path,
                    c_start,
                    c_end,
                    c_idx,
                    on_progress
                ): c_idx
                for c_idx, c_start, c_end in chunks_to_dl
            }

            for future in as_completed(future_to_chunk):
                c_idx = future_to_chunk[future]
                res = future.result()
                if res:
                    with lock:
                        completed_chunks.add(c_idx)
                        if len(completed_chunks) % 5 == 0:
                            try:
                                with open(meta_path, "w", encoding="utf-8") as f_meta:
                                    json.dump(
                                        {"total_size": total_size, "completed_chunks": list(completed_chunks)},
                                        f_meta
                                    )
                            except Exception:
                                pass
                else:
                    success_all = False
                    break
    except KeyboardInterrupt:
        print("\n  [!] Загрузка приостановлена пользователем. Прогресс сохранен.")
        stop_event.set()
        return False
    finally:
        stop_event.set()
        reporter_thread.join(timeout=1.0)
        print()

    if success_all and len(completed_chunks) == num_chunks:
        total_time = time.time() - start_time
        avg_speed = (total_size - initial_downloaded) / (total_time * 1024 * 1024) if total_time > 0 else 0
        print(f"  [OK] Загрузка завершена за {total_time:.1f} с (средняя скорость: {avg_speed:.2f} МБ/с).")
        
        # Переименование и очистка метаданных
        if os.path.exists(dest_path):
            os.remove(dest_path)
        shutil.move(part_path, dest_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return True
    else:
        print("  [WARN] Некоторые чанки не были загружены. Повторите запуск для докачки.")
        return False


def download_model(key: str, target_dir: str = MODELS_DIR) -> bool:
    """Скачивает модель по ключу (embedding / llm) с многопоточным контролем скорости."""
    info = MODELS_CONFIG.get(key)
    if not info:
        print(f"[ERR] Неизвестная модель: {key}")
        return False

    dest_filename = info["filename"]
    dest_path = os.path.join(target_dir, dest_filename)
    os.makedirs(target_dir, exist_ok=True)

    # Список кандидатов: (репозиторий, список удаленных имен, хост)
    repos = [info["repo_id"]] + info.get("fallback_repos", [])
    remote_names = info.get("remote_filenames", [dest_filename])

    # Формируем список URL источников: прямые HF + hf-mirror
    candidate_urls = []
    for repo in repos:
        for rname in remote_names:
            candidate_urls.append((f"https://huggingface.co/{repo}/resolve/main/{rname}", repo, rname))
            candidate_urls.append((f"https://hf-mirror.com/{repo}/resolve/main/{rname}", repo + " [Mirror]", rname))

    print(f"\n[>] Поиск доступных источников для {info['desc']}...")
    for url, repo_desc, rname in candidate_urls:
        print(f"  [?] Проверка источника: {repo_desc} -> {rname}...")
        cdn_url, total_size, supports_range = get_cdn_direct_url(url)
        if not cdn_url or total_size < info.get("min_size_bytes", 1024):
            continue

        print(f"  [+] Источник подтвержден! Размер: {total_size / (1024**3):.2f} ГБ ({total_size} байт).")
        print(f"  [+] CDN: {cdn_url[:75]}...")

        if supports_range and total_size > 50 * 1024 * 1024:
            print(f"  [>>] Запуск 10-поточного параллельного скачивания...")
            ok = download_parallel(
                cdn_url=cdn_url,
                dest_path=dest_path,
                total_size=total_size,
                desc=dest_filename,
                num_workers=10
            )
        else:
            # Однопоточный фоллбэк
            print(f"  [>>] Запуск прямого потокового скачивания...")
            ok = download_single_stream(cdn_url, dest_path, total_size, dest_filename)

        if ok and verify_gguf_integrity(dest_path, info.get("min_size_bytes", 1024)):
            print(f"  [SUCCESS] Файл верифицирован (GGUF magic OK): {dest_path}")
            return True
        elif ok:
            print(f"  [WARN] Файл скачан, но не прошел проверку GGUF сигнатуры.")

    print(f"  [ERROR] Не удалось загрузить модель {dest_filename} из доступных репозиториев.")
    return False


def download_single_stream(url: str, dest_path: str, total_size: int, desc: str) -> bool:
    """Однопоточное скачивание с индикатором скорости."""
    temp_path = dest_path + ".tmp"
    headers = {"User-Agent": "Frodo-Model-Downloader/2.0"}
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp, open(temp_path, "wb") as f_out:
            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MB
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                downloaded += len(chunk)
                dt = time.time() - t0
                speed = (downloaded / (1024 * 1024)) / dt if dt > 0 else 0
                percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                mb_done = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(f"\r  [>>] {desc}: {percent:5.1f}% ({mb_done:.1f}/{mb_total:.1f} МБ) | Скорость: {speed:.1f} МБ/с")
                sys.stdout.flush()
            print()
        shutil.move(temp_path, dest_path)
        return True
    except Exception as e:
        print(f"\n  [ERR] Ошибка потока: {e}")
        return False


def ensure_models_installed(models_dir: str = MODELS_DIR, auto_download: bool = True) -> Dict[str, bool]:
    """
    Проверяет наличие обеих моделей в models/.
    При отсутствии — скачивает их с Hugging Face.
    """
    os.makedirs(models_dir, exist_ok=True)
    status = {}

    for key, info in MODELS_CONFIG.items():
        fname = info["filename"]
        fpath = os.path.join(models_dir, fname)
        min_bytes = info.get("min_size_bytes", 1024)

        if os.path.exists(fpath) and os.path.getsize(fpath) >= min_bytes:
            sz_mb = os.path.getsize(fpath) / (1024 * 1024)
            is_valid = verify_gguf_integrity(fpath, min_bytes)
            status_text = "OK, GGUF valid" if is_valid else "CORRUPTED"
            print(f"  [OK] Модель {key.upper()}: {fname} ({sz_mb:.1f} МБ) -> {status_text}")
            status[key] = is_valid
        else:
            print(f"  [MISSING] Модель {key.upper()} отсутствует или повреждена: {fname}")
            if auto_download:
                ok = download_model(key, models_dir)
                status[key] = ok
            else:
                status[key] = False

    return status


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Загрузчик весов моделей Frodo")
    parser.add_argument("model", nargs="?", default="all", choices=["all", "llm", "embedding"],
                        help="Какую модель скачать (all, llm, embedding)")
    args = parser.parse_args()

    print("=" * 72)
    print("   🧙 FRODO: АВТОНОМНЫЙ ВЫСОКОСКОРОСТНОЙ ЗАГРУЗЧИК МОДЕЛЕЙ")
    print(f"   Целевая папка: {MODELS_DIR}")
    print("=" * 72)

    if args.model == "all":
        res = ensure_models_installed(MODELS_DIR, auto_download=True)
    else:
        ok = download_model(args.model, MODELS_DIR)
        res = {args.model: ok}

    print("\nФинальный статус моделей:", res)
