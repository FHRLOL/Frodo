import urllib.request
import json
import math
import time
from typing import List, Optional

class LocalEmbedder:
    """
    Клиент для локального движка эмбеддингов (EmbeddingGemma 2 на llama-server, порт 8085).
    Использует стандартную библиотеку Python urllib для максимальной переносимости без зависимостей.
    Оснащен детерминированным 768-мерным фоллбэком и кэшем доступности сервера.
    """

    def __init__(self, endpoint: str = "http://localhost:8085/v1/embeddings", timeout: float = 1.0):
        self.endpoint = endpoint
        self.timeout = timeout
        self._cache = {}
        self._server_offline_until = 0.0

    def get_embedding(self, text: str) -> List[float]:
        text_clean = text.strip()
        if not text_clean:
            return [0.0] * 768

        if text_clean in self._cache:
            return self._cache[text_clean]

        now = time.time()
        # Если сервер недавно был недоступен, используем фоллбэк без задержки тайм-аута
        if now < self._server_offline_until:
            return self._fallback_embedding(text_clean, dim=768)

        payload = json.dumps({"input": text_clean}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                emb = data["data"][0]["embedding"]
                self._cache[text_clean] = emb
                return emb
        except Exception:
            # Помечаем сервер как оффлайн на 30 секунд для предотвращения подвисания тестов
            self._server_offline_until = time.time() + 30.0
            return self._fallback_embedding(text_clean, dim=768)

    def _fallback_embedding(self, text: str, dim: int = 768) -> List[float]:
        """Детерминированный легковесный фоллбэк хэш-эмбеддинг размерности 768."""
        vec = [0.0] * dim
        for i, word in enumerate(text.lower().split()):
            h = hash(word) % dim
            vec[h] += 1.0 / (1.0 + i * 0.1)
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm > 0 else vec

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
