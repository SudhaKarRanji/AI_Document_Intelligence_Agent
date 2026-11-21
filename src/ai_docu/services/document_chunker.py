from dataclasses import dataclass
from pathlib import Path

import pymupdf
from docx import Document


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class TextRange:
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None


def ranges_for_pdf(file_path: Path) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    offset = 0

    with pymupdf.open(file_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            page_text = page.get_text("text").strip()
            if not page_text:
                continue
            start = offset
            end = start + len(page_text)
            ranges.append((start, end, page_number))
            offset = end + 1

    return ranges


def ranges_for_docx(file_path: Path) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    offset = 0
    document = Document(file_path)

    for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
        paragraph_text = paragraph.text.strip()
        if not paragraph_text:
            continue
        start = offset
        end = start + len(paragraph_text)
        ranges.append((start, end, paragraph_number))
        offset = end + 1

    return ranges


def source_ranges(
    chunk_start: int,
    chunk_end: int,
    ranges: list[tuple[int, int, int]],
) -> tuple[int | None, int | None]:
    matches = [
        source_number
        for start, end, source_number in ranges
        if start < chunk_end and end > chunk_start
    ]
    return (min(matches), max(matches)) if matches else (None, None)


def build_text_chunks(text: str) -> list[tuple[int, int, str]]:
    if not text:
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append((start, end, text[start:end]))
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP

    return chunks


def build_document_chunks(
    file_path: Path,
    extracted_text: str,
) -> list[TextRange]:
    text_chunks = build_text_chunks(extracted_text)
    extension = file_path.suffix.lower()
    source_range = (
        ranges_for_pdf(file_path)
        if extension == ".pdf"
        else ranges_for_docx(file_path)
    )

    result: list[TextRange] = []
    for start, end, _ in text_chunks:
        source_start, source_end = source_ranges(start, end, source_range)
        if extension == ".pdf":
            result.append(
                TextRange(
                    start_char=start,
                    end_char=end,
                    page_start=source_start,
                    page_end=source_end,
                )
            )
        else:
            result.append(
                TextRange(
                    start_char=start,
                    end_char=end,
                    paragraph_start=source_start,
                    paragraph_end=source_end,
                )
            )

    return result
