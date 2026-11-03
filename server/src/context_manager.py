import re
from typing import Optional, List, Dict, Any
from database import db
from guardrails import PromptGuardrail

class DialogueContextManager:
    """
    Контекстный менеджер псевдо-stateless сессий:
    1. Загружает последние 2-3 сообщения диалога студента из chat_messages.
    2. Формирует компактный блок <dialogue_history>...</dialogue_history> без раздувания токенов.
    3. Обеспечивает нулевое удержание KV-кэша на сервере моделей: каждый запрос
       передает только строго необходимую сжатую предысторию в теле запроса.
    """

    MAX_HISTORY_MESSAGES = 4     # Последние 2 пары вопрос-ответ
    MAX_MESSAGE_CHARS = 220      # Лимит длины одной реплики для предотвращения раздувания KV-кэша

    @classmethod
    def compress_text(cls, text: str, max_chars: int = MAX_MESSAGE_CHARS) -> str:
        """Сжимает длинное сообщение до ключевых фраз для экономии токенов."""
        if not text:
            return ""
        # Удаляем избыточные пробелы и переносы строк
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[:max_chars - 3].rstrip() + "..."

    @classmethod
    def get_compressed_history(
        cls,
        user_id: Optional[int],
        lab_id: Optional[int] = None,
        max_messages: int = MAX_HISTORY_MESSAGES
    ) -> str:
        """
        Извлекает историю диалога из БД и формирует сжатый XML-блок истории.
        Если история отсутствует или user_id=None — возвращает пустую строку.
        """
        if not user_id:
            return ""

        try:
            # Получаем последние сообщения из БД
            recent_msgs = db.get_chat_history(user_id=user_id, lab_id=lab_id, limit=max_messages)
            if not recent_msgs:
                return ""

            # Сортируем хронологически
            sorted_msgs = sorted(recent_msgs, key=lambda m: m.get("id", 0))

            history_lines = []
            for m in sorted_msgs:
                role_label = "Студент" if m.get("role") in ("student", "user") else "Наставник"
                raw_content = m.get("content", "")
                
                # Если в ответе наставника был блок <thought>, вырезаем его из истории
                clean_content = re.sub(r'<\s*thought\s*>.*?<\s*/\s*thought\s*>', '', raw_content, flags=re.DOTALL)
                compressed = cls.compress_text(clean_content)
                sanitized = PromptGuardrail.sanitize_input(compressed)

                if sanitized:
                    history_lines.append(f"{role_label}: {sanitized}")

            if not history_lines:
                return ""

            joined = "\n".join(history_lines)
            return f"<dialogue_history>\n{joined}\n</dialogue_history>"

        except Exception as e:
            # В случае сбоя БД диалог не должен падать
            return ""
