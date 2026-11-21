from pathlib import Path

import pymupdf
from docx import Document


class DocumentExtractionError(RuntimeError):
    pass


def extract_document_text(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    try:
        if extension == ".pdf":
            with pymupdf.open(file_path) as pdf:
                text_parts = [page.get_text("text") for page in pdf]
            extracted_text = "\n".join(text_parts).strip()
            if extracted_text:
                return extracted_text
            raise DocumentExtractionError(
                f"No extractable text found in {file_path.name}."
            )

        if extension == ".docx":
            document = Document(file_path)
            text_parts = [paragraph.text for paragraph in document.paragraphs]
            text_parts.extend(
                cell.text
                for table in document.tables
                for row in table.rows
                for cell in row.cells
            )
            extracted_text = "\n".join(text_parts).strip()
            if extracted_text:
                return extracted_text
            raise DocumentExtractionError(
                f"No extractable text found in {file_path.name}."
            )
    except Exception as error:
        raise DocumentExtractionError(
            f"Unable to extract text from {file_path.name}."
        ) from error

    raise DocumentExtractionError(
        f"Unsupported document type: {extension or 'unknown'}"
    )
