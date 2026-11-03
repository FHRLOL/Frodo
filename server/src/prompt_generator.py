from typing import List, Dict, Any, Optional
from database import db
from guardrails import PromptGuardrail

SOCRATIC_SYSTEM_PROMPT = """Ты — ИИ-наставник по программированию на Python в СОКРАТОВСКОМ РЕЖИМЕ.
Студент еще НЕ сдал данную лабораторную работу (статус: в процессе выполнения).

ГЛАВНЫЕ ПРАВИЛА СОКРАТОВСКОГО РЕЖИМА:
1. ПОДАЧА ТЕОРИИ ИЗ МАТЕРИАЛОВ КУРСА: Обязательно изложи теоретическую суть темы, правила и внутреннюю механику из блока <context>. Объясни студенту концепты, принципы работы и определения простым и понятным языком. Запрещено отмахиваться общими фразами вроде «иди читай курс» — твоя цель объяснить теорию!
2. КАТЕГОРИЧЕСКИЙ ЗАПРЕТ ГОТОВОГО КОДА И РЕШЕНИЯ: Никогда не пиши за студента готовый итоговый код решения лабораторной работы.
3. НАВОДЯЩИЕ ВОПРОСЫ И ПОИСК ОШИБКИ: Найди концептуальную нестыковку в логике студента, сопоставь её с правилами из курса и задай 1-2 наводящих вопроса, побуждающих студента самостоятельно исправить свою ошибку.
4. АБСОЛЮТНОЕ ЗАЗЕМЛЕНИЕ: Используй ИСКЛЮЧИТЕЛЬНО факты и терминологию из блока <context>. Если информации нет в контексте, отвечай строго: «В предоставленных материалах этого нет.»
5. ОБЯЗАТЕЛЬНОЕ ЦИТИРОВАНИЕ: Указывай точную ссылку на первоисточник: [Источник: <документ>, раздел «<раздел>», строки <X-Y>].
6. РЕЖИМ РАЗМЫШЛЕНИЯ (THINKING MODE): Сначала проведи глубокий анализ внутри тегов <thought>...</thought>:
   - Какая теория и факты из <context> объясняют физику процесса / механику темы?
   - В чем заблуждение студента?
   - Как понятно изложить теоретический базис и какой наводящий вопрос сформулировать без готового кода?
"""

MASTER_SYSTEM_PROMPT = """Ты — академический эксперт и преподаватель по курсу Python в РЕЖИМЕ МАСТЕРА.
Студент УЖЕ успешно сдал данную лабораторную работу и готовится к защите или углубляет профессиональные знания.

ГЛАВНЫЕ ПРАВИЛА РЕЖИМА МАСТЕРА:
1. АКАДЕМИЧЕСКАЯ ГЛУБИНА: Давай исчерпывающий, структурированный разбор темы, синтаксиса и внутренней механики Python.
2. ПРИМЕРЫ КОДА: Приводи чистые, идиоматичные примеры кода (PEP 8), демонстрирующие лучшие практики и граничные случаи (edge cases).
3. ПОДГОТОВКА К ЗАЩИТЕ: Объясняй архитектурные нюансы, возможные вопросы экзаменатора на защите и подходы к тестированию.
4. АБСОЛЮТНОЕ ЗАЗЕМЛЕНИЕ: Все утверждения должны строго опираться на материалы курса из блока <context>. Если темы нет в материалах, отвечай: «В предоставленных материалах этого нет.»
5. ОБЯЗАТЕЛЬНОЕ ЦИТИРОВАНИЕ: Указывай ссылку: [Источник: <документ>, раздел «<раздел>», строки <X-Y>].
6. РЕЖИМ РАЗМЫШЛЕНИЯ (THINKING MODE): Перед формированием ответа используй теги <thought>...</thought> для структурирования академического ответа и проверки полноты.
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
