import os
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class DocumentChunk:
    chunk_id: str
    doc_name: str
    section_title: str
    breadcrumbs: str
    line_start: int
    line_end: int
    content: str
    raw_text: str

class MarkdownHierarchicalParser:
    """
    Иерархический парсер Markdown документов:
    - Выделяет разделы по заголовкам H1-H4.
    - Сохраняет хлебные крошки (цепочку наследования разделов).
    - Фиксирует точные номера строк (line_start, line_end) для цитирования.
    - Не разрывает блоки кода и абзацы внутри смыслового раздела.
    """

    HEADER_REGEX = re.compile(r'^(#{1,4})\s+(.+)$')

    @classmethod
    def parse_file(cls, filepath: str) -> List[DocumentChunk]:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        chunks: List[DocumentChunk] = []
        stack: List[tuple[int, str]] = []  # [(level, title)]
        
        current_header = filename
        current_level = 0
        current_lines: List[str] = []
        section_start_line = 1

        def flush_chunk(end_line: int):
            nonlocal current_lines, section_start_line, current_header
            text = "".join(current_lines).strip()
            if text:
                crumbs = " > ".join([title for _, title in stack]) if stack else current_header
                chunk_id = f"{filename}::L{section_start_line}-L{end_line}"
                # Для эмбеддинга формируем обогащенный контекст
                enriched_text = f"Документ: {filename}\nРаздел: {crumbs}\nСтроки: {section_start_line}-{end_line}\n\n{text}"
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    doc_name=filename,
                    section_title=current_header,
                    breadcrumbs=crumbs,
                    line_start=section_start_line,
                    line_end=end_line,
                    content=enriched_text,
                    raw_text=text
                ))
            current_lines = []

        in_code_block = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            m = cls.HEADER_REGEX.match(line) if not in_code_block else None
            if m:
                # Нашли заголовок
                flush_chunk(lineno - 1)
                level = len(m.group(1))
                # Очищаем заголовок от якорей типа {#data-structures}
                title = re.sub(r'\{#[^}]+\}', '', m.group(2)).strip()
                title = re.sub(r'\[\^.+?\]', '', title).strip()

                # Обновляем стек заголовков
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))

                current_header = title
                current_level = level
                section_start_line = lineno
                current_lines.append(line)
            else:
                if not current_lines and stripped:
                    section_start_line = lineno
                current_lines.append(line)

        flush_chunk(len(lines))
        return chunks

    @classmethod
    def parse_directory(cls, dirpath: str) -> List[DocumentChunk]:
        all_chunks = []
        for root, _, files in os.walk(dirpath):
            for file in sorted(files):
                if file.endswith((".md", ".markdown", ".txt")):
                    full_path = os.path.join(root, file)
                    all_chunks.extend(cls.parse_file(full_path))
        return all_chunks
