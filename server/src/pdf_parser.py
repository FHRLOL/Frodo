import os
import re
from typing import List, Optional, Dict, Any
from parser import DocumentChunk

# Безопасные импорты PDF библиотек в порядке предпочтения
PYPDF_AVAILABLE = False
FITZ_AVAILABLE = False
PDFPLUMBER_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    pass

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    pass

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pass


class PDFManualParser:
    """
    Универсальный парсер учебных PDF методичек и пособий:
    - Извлекает структурированный текст с сохранением номеров страниц и строк.
    - Выделяет смысловые разделы и главы (по закладкам/оглавлению или эвристикам).
    - Формирует объекты DocumentChunk, совместимые с гибридным поиском Frodo.
    """

    HEADING_REGEX = re.compile(
        r'^(Лабораторная\s+работа\s*№?\d+|Глава\s+\d+|Раздел\s+\d+|\d+(\.\d+)*\s+[А-ЯA-ZЁ].{2,80})$',
        re.MULTILINE
    )

    @classmethod
    def is_supported(cls) -> bool:
        """Проверяет наличие хотя бы одного доступного PDF-парсера."""
        return PYPDF_AVAILABLE or FITZ_AVAILABLE or PDFPLUMBER_AVAILABLE

    @classmethod
    def parse_file(cls, filepath: str) -> List[DocumentChunk]:
        """Парсит PDF файл с сохранением метаданных страниц и строк."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF файл не найден: {filepath}")

        if FITZ_AVAILABLE:
            return cls._parse_with_fitz(filepath)
        elif PYPDF_AVAILABLE:
            return cls._parse_with_pypdf(filepath)
        elif PDFPLUMBER_AVAILABLE:
            return cls._parse_with_pdfplumber(filepath)
        else:
            raise ImportError(
                "Не найден ни один PDF модуль (pypdf, pymupdf/fitz или pdfplumber). "
                "Установите pypdf: pip install pypdf"
            )

    @classmethod
    def _parse_with_pypdf(cls, filepath: str) -> List[DocumentChunk]:
        filename = os.path.basename(filepath)
        reader = pypdf.PdfReader(filepath)
        chunks: List[DocumentChunk] = []

        total_line_counter = 1
        current_section = f"Введение ({filename})"
        breadcrumbs = f"{filename} > {current_section}"

        for page_idx, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            lines = [l for l in page_text.splitlines() if l.strip()]
            if not lines:
                continue

            page_start_line = total_line_counter
            page_chunks_lines: List[str] = []
            chunk_start_line = page_start_line

            for line in lines:
                stripped = line.strip()
                # Проверяем, является ли строка заголовком раздела
                if cls.HEADING_REGEX.match(stripped):
                    # Сбрасываем накопленный чанк перед новым разделом
                    if page_chunks_lines:
                        chunk_end_line = total_line_counter - 1
                        raw = "\n".join(page_chunks_lines).strip()
                        if raw:
                            chunks.append(cls._create_chunk(
                                filename=filename,
                                page_idx=page_idx,
                                start_line=chunk_start_line,
                                end_line=chunk_end_line,
                                section=current_section,
                                crumbs=breadcrumbs,
                                text=raw
                            ))
                        page_chunks_lines = []

                    current_section = stripped
                    breadcrumbs = f"{filename} > Стр. {page_idx} > {current_section}"
                    chunk_start_line = total_line_counter

                page_chunks_lines.append(stripped)
                total_line_counter += 1

            if page_chunks_lines:
                chunk_end_line = total_line_counter - 1
                raw = "\n".join(page_chunks_lines).strip()
                if raw:
                    chunks.append(cls._create_chunk(
                        filename=filename,
                        page_idx=page_idx,
                        start_line=chunk_start_line,
                        end_line=chunk_end_line,
                        section=current_section,
                        crumbs=breadcrumbs,
                        text=raw
                    ))

        return chunks

    @classmethod
    def _parse_with_fitz(cls, filepath: str) -> List[DocumentChunk]:
        import fitz
        filename = os.path.basename(filepath)
        doc = fitz.open(filepath)
        chunks: List[DocumentChunk] = []
        total_line_counter = 1
        current_section = f"Введение ({filename})"
        breadcrumbs = f"{filename} > {current_section}"

        for page_idx, page in enumerate(doc, 1):
            text = page.get_text("text") or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not lines:
                continue

            chunk_start_line = total_line_counter
            page_lines = []

            for line in lines:
                if cls.HEADING_REGEX.match(line):
                    if page_lines:
                        raw = "\n".join(page_lines).strip()
                        chunks.append(cls._create_chunk(
                            filename=filename,
                            page_idx=page_idx,
                            start_line=chunk_start_line,
                            end_line=total_line_counter - 1,
                            section=current_section,
                            crumbs=breadcrumbs,
                            text=raw
                        ))
                        page_lines = []
                    current_section = line
                    breadcrumbs = f"{filename} > Стр. {page_idx} > {current_section}"
                    chunk_start_line = total_line_counter

                page_lines.append(line)
                total_line_counter += 1

            if page_lines:
                raw = "\n".join(page_lines).strip()
                chunks.append(cls._create_chunk(
                    filename=filename,
                    page_idx=page_idx,
                    start_line=chunk_start_line,
                    end_line=total_line_counter - 1,
                    section=current_section,
                    crumbs=breadcrumbs,
                    text=raw
                ))

        return chunks

    @classmethod
    def _parse_with_pdfplumber(cls, filepath: str) -> List[DocumentChunk]:
        import pdfplumber
        filename = os.path.basename(filepath)
        chunks: List[DocumentChunk] = []
        total_line_counter = 1

        with pdfplumber.open(filepath) as pdf:
            for page_idx, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                if not lines:
                    continue

                chunk_start = total_line_counter
                total_line_counter += len(lines)
                raw = "\n".join(lines).strip()
                section = f"Страница {page_idx}"
                crumbs = f"{filename} > {section}"

                chunks.append(cls._create_chunk(
                    filename=filename,
                    page_idx=page_idx,
                    start_line=chunk_start,
                    end_line=total_line_counter - 1,
                    section=section,
                    crumbs=crumbs,
                    text=raw
                ))

        return chunks

    @classmethod
    def _create_chunk(
        cls,
        filename: str,
        page_idx: int,
        start_line: int,
        end_line: int,
        section: str,
        crumbs: str,
        text: str
    ) -> DocumentChunk:
        """Создает стандартизированный DocumentChunk с цитированием страниц и строк."""
        chunk_id = f"{filename}::P{page_idx}::L{start_line}-L{end_line}"
        enriched_content = (
            f"Документ: {filename} (PDF, Стр. {page_idx})\n"
            f"Раздел: {crumbs}\n"
            f"Строки: {start_line}-{end_line}\n\n"
            f"{text}"
        )
        return DocumentChunk(
            chunk_id=chunk_id,
            doc_name=filename,
            section_title=section,
            breadcrumbs=crumbs,
            line_start=start_line,
            line_end=end_line,
            content=enriched_content,
            raw_text=text
        )

    @classmethod
    def parse_directory(cls, dirpath: str) -> List[DocumentChunk]:
        """Рекурсивно сканирует директорию и парсит все найденные PDF файлы."""
        all_chunks: List[DocumentChunk] = []
        if not os.path.exists(dirpath):
            return all_chunks

        for root, _, files in os.walk(dirpath):
            for file in sorted(files):
                if file.lower().endswith(".pdf"):
                    full_path = os.path.join(root, file)
                    try:
                        chunks = cls.parse_file(full_path)
                        all_chunks.extend(chunks)
                    except Exception as e:
                        print(f"[PDFParser] Ошибка парсинга {file}: {e}")

        return all_chunks
