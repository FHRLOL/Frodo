import urllib.request
import json
import math
from typing import List, Optional

class LocalEmbedder:
    """
    Клиент для локального движка эмбеддингов (EmbeddingGemma 2 на llama-server, порт 8085).
    Использует стандартную библиотеку Python urllib для максимальной переносимости без зависимостей.
    """

    def __init__(self, endpoint: str = "http://localhost:8085/v1/embeddings", timeout: float = 15.0):
        self.endpoint = endpoint
        self.timeout = timeout
        self._cache = {}

    def get_embedding(self, text: str) -> List[float]:
        text_clean = text.strip()
        if not text_clean:
            return [0.0] * 512

        if text_clean in self._cache:
            return self._cache[text_clean]

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
        except Exception as e:
            # Fallback на случай недоступности сервера
            return self._fallback_embedding(text_clean)

    def _fallback_embedding(self, text: str, dim: int = 512) -> List[float]:
        """Детерминированный легковесный фоллбэк хэш-эмбеддинг при выключенном llama-server."""
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
