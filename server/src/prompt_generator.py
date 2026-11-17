from typing import List, Dict, Any, Optional
from database import db
from guardrails import PromptGuardrail

SOCRATIC_SYSTEM_PROMPT = """Ты — ИИ-наставник по программированию на Python в СОКРАТОВСКОМ РЕЖИМЕ.
Студент еще НЕ сдал данную лабораторную работу (статус: в процессе выполнения).

ГЛАВНЫЕ ПРАВИЛА СОКРАТОВСКОГО РЕЖИМА:
1. ПОДАЧА ТЕОРИИ ИЗ МАТЕРИАЛОВ КУРСА: Изложи теоретическую суть темы, правила и внутреннюю механику из блока <context>. Объясни студенту концепты, принципы работы и определения понятным академическим языком. Запрещено отмахиваться общими фразами вроде «иди читай курс» — твоя цель объяснить теорию!
2. КАТЕГОРИЧЕСКИЙ ЗАПРЕТ ГОТОВОГО КОДА И РЕШЕНИЯ: Никогда не пиши за студента готовый итоговый код решения задания лабораторной работы.
3. НАВОДЯЩИЕ ВОПРОСЫ: Задай 1-2 наводящих вопроса, побуждающих студента самостоятельно сопоставить правила с его задачей.
4. АБСОЛЮТНОЕ ЗАЗЕМЛЕНИЕ: Используй ИСКЛЮЧИТЕЛЬНО факты и терминологию из блока <context>. Если информации нет в контексте, отвечай строго: «В предоставленных материалах этого нет.»
5. ИСТОЧНИКИ: Не пиши в конце ответа текстовые сноски вроде [Источник: ...], интерактивная карточка источника формируется интерфейсом автоматически.
6. РЕЖИМ РАЗМЫШЛЕНИЯ (THINKING MODE): Сначала проведи анализ внутри тегов <thought>...</thought> (НЕ БОЛЕЕ 256 токенов), затем обязательно закрой тег </thought>. Сразу после </thought> пиши чистый ответ студенту БЕЗ заголовков (#) и БЕЗ дублирования вопроса.
"""

MASTER_SYSTEM_PROMPT = """Ты — академический эксперт и преподаватель по курсу Python в РЕЖИМЕ МАСТЕРА.
Студент УЖЕ успешно сдал данную лабораторную работу и готовится к защите или углубляет профессиональные знания.

ГЛАВНЫЕ ПРАВИЛА РЕЖИМА МАСТЕРА:
1. АКАДЕМИЧЕСКАЯ ГЛУБИНА: Давай исчерпывающий, структурированный разбор темы, синтаксиса и внутренней механики Python. Начинай ответ сразу с сути, БЕЗ markdown-заголовков первого уровня (#) и БЕЗ приветствий.
2. ПРИМЕРЫ КОДА: Приводи чистый, идиоматичный пример кода в блоке ```python ... ``` с реальными переносами строк. Пример кода ОБЯЗАН строго и наглядно демонстрировать именно те функции, методы или операции, о которых спросил студент (например, если спросили про append, sort, del — покажи именно их работу).
3. ПОДГОТОВКА К ЗАЩИТЕ: Объясняй нюансы выполнения, возможные вопросы экзаменатора на защите и поведение изменяемых/неизменяемых структур данных.
4. АБСОЛЮТНОЕ ЗАЗЕМЛЕНИЕ: Все утверждения должны строго опираться на материалы курса из блока <context>. Если темы нет в материалах, отвечай строго: «В предоставленных материалах этого нет.»
5. ИСТОЧНИКИ: Не вставляй в тело ответа ручные текстовые ссылки вроде [Источник: ...], интерфейс сформирует интерактивную карточку источника автоматически.
6. РЕЖИМ РАЗМЫШЛЕНИЯ (THINKING MODE): Сначала сформулируй план ответа внутри тегов <thought>...</thought> (НЕ БОЛЕЕ 256 токенов) и закрой тег </thought>. Ответ студенту пиши сразу после закрывающего тега.
"""

def determine_chat_mode(user_id: Optional[int], lab_id: Optional[int]) -> str:
    """
    Определяет режим работы наставника на основе прогресса студента:
    - 'master': лабораторная работа успешно сдана (status == 'passed').
    - 'socratic': лабораторная не сдана, не начата или lab_id не указан.
    """
    if not user_id or not lab_id:
        return "socratic"

    status_info = db.get_student_lab_status(user_id, lab_id)
    if status_info and status_info.get("status") == "passed":
        return "master"

    return "socratic"

def format_context_blocks(chunks: List[Dict[str, Any]]) -> str:
    """Форматирует найденные чанки базы знаний в изолированный блок <context>."""
    if not chunks:
        return "<context>\nМатериалы по данному вопросу отсутствуют.\n</context>"

    context_parts = []
    for i, c in enumerate(chunks, 1):
        clean_content = PromptGuardrail.sanitize_input(c.get("content", ""))
        context_parts.append(
            f"--- ФРАГМЕНТ #{i} ---\n"
            f"Документ: {c.get('doc_name', 'unknown')}\n"
            f"Раздел: {c.get('breadcrumbs', c.get('section_title', ''))}\n"
            f"Строки в документе: {c.get('line_start', 1)}–{c.get('line_end', 1)}\n"
            f"Релевантность (score): {round(c.get('score', 0.0), 3)}\n\n"
            f"{clean_content}\n"
        )

    joined = "\n".join(context_parts)
    return f"<context>\n{joined}\n</context>"

def build_mentor_prompt(
    mode: str,
    query: str,
    chunks: List[Dict[str, Any]],
    dialogue_history: str = ""
) -> List[Dict[str, str]]:
    """
    Формирует полный список сообщений (OpenAI Messages Format) для Gemma 4 E4B.
    Обеспечивает изоляцию контекста и нулевое удержание серверного KV-кэша.
    """
    system_prompt = MASTER_SYSTEM_PROMPT if mode == "master" else SOCRATIC_SYSTEM_PROMPT
    context_block = format_context_blocks(chunks)
    sanitized_query = PromptGuardrail.sanitize_input(query)

    user_parts = [context_block]
    if dialogue_history:
        user_parts.append(dialogue_history)
    user_parts.append(f"Вопрос студента: {sanitized_query}")

    user_content = "\n\n".join(user_parts)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
