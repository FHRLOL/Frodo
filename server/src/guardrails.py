import re
from typing import Tuple, Optional, List
from dataclasses import dataclass

RELEVANCE_THRESHOLD = 0.42
NOT_FOUND_MESSAGE = "В предоставленных материалах этого нет."
INJECTION_BLOCKED_MESSAGE = "Запрос отклонен: обнаружена попытка нарушения правил безопасности или обхода системных инструкций."

@dataclass
class GuardrailResult:
    allowed: bool
    sanitized_text: str
    reason: Optional[str] = None
    status: str = "OK"

class PromptGuardrail:
    """
    Многоуровневая система защиты RAG-пайплайна Frodo:
    1. Детекция Prompt Injection, Jailbreak (DAN, Developer Mode) и манипуляций системными инструкциями.
    2. Экранирование и нейтрализация инъекций XML-тегов (<context>, <dialogue_history>, <system>).
    3. Проверка порога семантической релевантности (relevance_threshold = 0.42).
    4. Выходной фильтр от утечек системных инструкций и промптов.
    """

    # Шаблоны атак на системный промпт и джейлбрейков
    INJECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("bypass_rules", re.compile(
            r"(игнорируй|забудь|отмени|сбрось|пренебреги)\s+(все\s+)?(предыдущие\s+|свои\s+|системные\s+)?(правила|инструкции|ограничения|указания|промпт)",
            re.IGNORECASE
        )),
        ("english_bypass", re.compile(
            r"(ignore|disregard|forget|bypass|override)\s+(all\s+)?(previous\s+|system\s+)?(instructions|rules|prompts|commands|constraints)",
            re.IGNORECASE
        )),
        ("leak_prompt", re.compile(
            r"(выведи|покажи|напечатай|процитируй|скажи)\s+(свой\s+|твой\s+|системный\s+)?(системный\s+)?(промпт|инструкци[ию]|system\s*prompt)",
            re.IGNORECASE
        )),
        ("english_leak_prompt", re.compile(
            r"(show|display|reveal|print|repeat|output|what\s+is)\s+(your\s+)?(initial\s+|system\s+)?(prompt|instructions)",
            re.IGNORECASE
        )),
        ("jailbreak_dan", re.compile(
            r"\b(jailbreak|dan\s+mode|dan\s+prompt|do\s+anything\s+now|developer\s+mode|unfiltered\s+mode|god\s+mode)\b",
            re.IGNORECASE
        )),
        ("roleplay_subversion", re.compile(
            r"(ты\s+теперь|с\s+этого\s+момента\s+ты|представь,\s*что\s+ты|притворись)\s+(не\s+наставник|dan|злодей|хакер|unrestricted)",
            re.IGNORECASE
        )),
        ("tag_tampering", re.compile(
            r"<\s*/?\s*(context|dialogue_history|system|prompt|thought|instruction|meta)\s*>",
            re.IGNORECASE
        ))
    ]

    # Шаблоны системных инструкций, которые не должны утекать в финальный ответ
    SYSTEM_LEAK_PATTERNS: List[re.Pattern] = [
        re.compile(r"ГЛАВНЫЕ\s+ПРАВИЛА\s+НАСТАВНИКА", re.IGNORECASE),
        re.compile(r"АБСОЛЮТНОЕ\s+ЗАЗЕМЛЕНИЕ", re.IGNORECASE),
        re.compile(r"ЧЕСТНЫЙ\s+ОТКАЗ", re.IGNORECASE),
        re.compile(r"ОБЯЗАТЕЛЬНОЕ\s+ЦИТИРОВАНИЕ", re.IGNORECASE),
        re.compile(r"Ты\s+—\s+(строгий\s+)?ассистент-наставник", re.IGNORECASE),
        re.compile(r"MENTOR_SYSTEM_PROMPT", re.IGNORECASE),
        re.compile(r"<\s*/?\s*(system|instruction|context_prompt)\s*>", re.IGNORECASE),
        re.compile(r"Твоя\s+задача\s+—\s+отвечать\s+ИСКЛЮЧИТЕЛЬНО", re.IGNORECASE),
        re.compile(r"В\s+режиме\s+мастера\s+ты\s+обязан", re.IGNORECASE),
        re.compile(r"В\s+сократовском\s+режиме\s+запрещено", re.IGNORECASE)
    ]

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """
        Экранирует теги разметки промпта, чтобы пользовательский ввод
        не мог замкнуть теги <context>, <dialogue_history>, <thought> и др.
        """
        if not text:
            return ""
        # Заменяем опасные теговые скобки на безопасные аналоги
        sanitized = re.sub(
            r"<\s*(/?\s*(context|dialogue_history|system|prompt|thought|instruction|meta))\s*>",
            r"[\1]",
            text,
            flags=re.IGNORECASE
        )
        return sanitized.strip()

    @classmethod
    def validate_input(cls, query: str) -> GuardrailResult:
        """
        Проверяет входящий запрос студента на попытки инъекций и обхода инструкций.
        """
        if not query or not query.strip():
            return GuardrailResult(
                allowed=False,
                sanitized_text="",
                reason="Пустой запрос",
                status="EMPTY_QUERY"
            )

        # Проверка по сигнатурам Prompt Injection
        for attack_name, pattern in cls.INJECTION_PATTERNS:
            if pattern.search(query):
                return GuardrailResult(
                    allowed=False,
                    sanitized_text=cls.sanitize_input(query),
                    reason=f"Обнаружен паттерн атаки на системный промпт: {attack_name}",
                    status="REJECTED_BY_GUARDRAIL"
                )

        sanitized = cls.sanitize_input(query)
        return GuardrailResult(
            allowed=True,
            sanitized_text=sanitized,
            status="OK"
        )

    @classmethod
    def check_relevance(cls, score: Optional[float], threshold: float = RELEVANCE_THRESHOLD) -> bool:
        """
        Проверяет, удовлетворяет ли скор релевантности минимальному порогу RAG.
        """
        if score is None:
            return False
        return score >= threshold

    @classmethod
    def filter_output(cls, response: str) -> str:
        """
        Выходной фильтр (Output Guardrail): удаляет случайные утечки служебных инструкций
        или системных промптов в генерации LLM.
        """
        if not response:
            return ""

        cleaned = response
        # Проверяем на прямое цитирование системных правил
        for pattern in cls.SYSTEM_LEAK_PATTERNS:
            if pattern.search(cleaned):
                # Удаляем строки, содержащие утечки
                lines = cleaned.splitlines()
                safe_lines = [line for line in lines if not pattern.search(line)]
                cleaned = "\n".join(safe_lines).strip()

        if not cleaned:
            return NOT_FOUND_MESSAGE

        return cleaned
