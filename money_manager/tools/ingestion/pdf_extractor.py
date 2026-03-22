"""Extract text from PDF bank statements."""

from io import BytesIO
from typing import Optional

from PyPDF2 import PdfReader


def extract_text_from_pdf(file_bytes: bytes, password: Optional[str] = None) -> str:
    """
    Extract all text content from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.
        password: Optional password to decrypt protected PDFs.

    Returns:
        Concatenated text from all pages.

    Raises:
        ValueError: If no text could be extracted (may need OCR)
                    or if the PDF is encrypted and no/wrong password is given.
    """
    reader = PdfReader(BytesIO(file_bytes))

    # Handle password-protected PDFs
    if reader.is_encrypted:
        if not password:
            raise ValueError(
                "This PDF is password-protected. Please provide the password."
            )
        if not reader.decrypt(password):
            raise ValueError(
                "Failed to decrypt PDF – the password may be incorrect."
            )

    pages_text: list[str] = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text.strip())

    full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        raise ValueError(
            "No text extracted from PDF. The document may be scanned/image-based and require OCR."
        )

    return full_text
