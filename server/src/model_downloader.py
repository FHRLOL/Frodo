# -*- coding: utf-8 -*-
"""
Модуль автоматической проверки и докачивания весов моделей с Hugging Face.
Поддерживает:
1. EmbeddingGemma 2 (embeddinggemma-2-Q8_0.gguf)
2. Gemma 4 E4B-IT (gemma-4-e4b-it-q4_k_m.gguf)
"""

import os
import sys
import shutil
import urllib.request
from typing import Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(ROOT_DIR, "models")

MODELS_CONFIG: Dict[str, Dict[str, Any]] = {
    "embedding": {
        "filename": "embeddinggemma-2-Q8_0.gguf",
        "repo_id": "google/embeddinggemma-2-GGUF",
        "desc": "EmbeddingGemma 2 (Q8_0, ~300 МБ) — эмбеддер RAG",
        "fallback_repos": ["bartowski/embeddinggemma-2-GGUF"],
        "min_size_bytes": 100 * 1024 * 1024  # > 100 MB
    },
    "llm": {
        "filename": "gemma-4-e4b-it-q4_k_m.gguf",
        "repo_id": "google/gemma-4-e4b-it-GGUF",
        "desc": "Gemma 4 E4B-IT (Q4_K_M, ~2.8 ГБ) — локальная LLM наставника",
        "fallback_repos": [
            "bartowski/gemma-4-e4b-it-GGUF",
            "unsloth/gemma-4-e4b-it-GGUF"
        ],
        "min_size_bytes": 500 * 1024 * 1024  # > 500 MB
    }
}


def download_with_progress(url: str, dest_path: str, desc: str):
    """Потоковое скачивание файла по прямому URL с отображением прогресса."""
    temp_path = dest_path + ".tmp"
    headers = {"User-Agent": "Frodo-Model-Downloader/1.0"}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req, timeout=30.0) as resp, open(temp_path, "wb") as f_out:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB
        
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f_out.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = (downloaded / total_size) * 100
                mb_done = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(f"\r  [>>] {desc}: {percent:5.1f}% ({mb_done:.1f}/{mb_total:.1f} МБ)")
                sys.stdout.flush()
            else:
                mb_done = downloaded / (1024 * 1024)
                sys.stdout.write(f"\r  [>>] {desc}: скачано {mb_done:.1f} МБ...")
                sys.stdout.flush()
        print()
    shutil.move(temp_path, dest_path)


def download_model(key: str, target_dir: str = MODELS_DIR) -> bool:
    """Скачивает модель через huggingface_hub или HTTP-фоллбэк."""
    info = MODELS_CONFIG.get(key)
    if not info:
        return False
    
    filename = info["filename"]
    dest_path = os.path.join(target_dir, filename)
    os.makedirs(target_dir, exist_ok=True)
    
    repos_to_try = [info["repo_id"]] + info.get("fallback_repos", [])
    
    # 1. Попытка через huggingface_hub
    try:
        from huggingface_hub import hf_hub_download
        for repo in repos_to_try:
            try:
                print(f"  [>] Запрос весов {filename} из Hugging Face ({repo})...")
                cached_file = hf_hub_download(
                    repo_id=repo,
                    filename=filename,
                    local_dir=target_dir
                )
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
                    print(f"  [OK] Модель успешно скачана: {filename}")
                    return True
            except Exception as e:
                # Если в текущем репозитории нет файла, пробуем следующий
                continue
    except ImportError:
        pass
    
    # 2. Прямой HTTP-фоллбэк на Hugging Face resolve/main
    for repo in repos_to_try:
        url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
        try:
            print(f"  [>] Прямое скачивание с {url}...")
            download_with_progress(url, dest_path, filename)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
                print(f"  [OK] Модель {filename} успешно сохранена в {dest_path}")
                return True
        except Exception:
            continue
            
    print(f"  [WARN] Автоскачивание не удалось. Пожалуйста, скачайте {filename} вручную в папку models/.")
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
            print(f"  [OK] Найдена модель {key.upper()}: {fname} ({sz_mb:.1f} МБ)")
            status[key] = True
        else:
            print(f"  [MISSING] Модель {key.upper()} отсутствует: {fname}")
            if auto_download:
                ok = download_model(key, models_dir)
                status[key] = ok
            else:
                status[key] = False
                
    return status


if __name__ == "__main__":
    print("=" * 70)
    print("   ПРОВЕРКА И ДОКАЧИВАНИЕ МОДЕЛЕЙ FRODO (HUGGING FACE)")
    print("=" * 70)
    res = ensure_models_installed(MODELS_DIR, auto_download=True)
    print("Статус моделей:", res)
