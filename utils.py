import fitz  # PyMuPDF
import docx  # python-docx
import re
from pdfminer.high_level import extract_text as pdfminer_extract_text
import PyPDF2
import docx2txt as d2t


def normalize_text(text):
    """
    Normalizes text by removing extra spaces and non-ASCII characters.
    """
    text = re.sub(r"\s+", " ", text)  # Replace multiple spaces with a single space
    text = text.encode("ascii", "ignore").decode("utf-8")  # Remove non-ASCII characters
    return text.strip()


def fix_line_breaks(text):
    """
    Fixes unintended line breaks in the text.
    """
    text = re.sub(r"(\w+)\n(\w+)", r"\1 \2", text)  # Join words split by line breaks
    return text


def extract_text_from_pdf(file):
    """
    Extracts text from a PDF file using PyMuPDF, PDFMiner, and PyPDF2 as fallbacks.
    """
    text = ""
    try:
        # First try with PyMuPDF (fitz)
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        if not text.strip():
            # If PyMuPDF fails, try with PDFMiner
            file.seek(0)  # Reset file pointer
            text = pdfminer_extract_text(file)
        if not text.strip():
            # If both fail, try with PyPDF2
            file.seek(0)  # Reset file pointer
            reader = PyPDF2.PdfFileReader(file)
            num_pages = reader.getNumPages()
            for i in range(num_pages):
                page = reader.getPage(i)
                text += page.extractText()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        text = ""
    return normalize_text(fix_line_breaks(text))


def extract_text_from_docx(file):
    """
    Extracts text from a DOCX file using docx2txt.
    """
    try:
        text = d2t.process(file)
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
        text = ""
    return normalize_text(fix_line_breaks(text))


def extract_text_from_doc(file):
    """
    Extracts text from a DOC file using python-docx (fallback for textract).
    """
    try:
        # Try reading DOC files using python-docx (may not work for all DOC files)
        doc = docx.Document(file)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        print(f"Error extracting text from DOC: {e}")
        text = ""
    return normalize_text(fix_line_breaks(text))


def extract_text_from_txt(file):
    """
    Extracts text from a TXT file.
    """
    try:
        return normalize_text(fix_line_breaks(file.read().decode("utf-8")))
    except Exception as e:
        print(f"Error extracting text from TXT: {e}")
        return ""


def extract_text_from_file(file):
    """
    Extracts text from a file based on its MIME type.
    """
    if file.type == "application/pdf":
        return extract_text_from_pdf(file)
    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return extract_text_from_docx(file)
    elif file.type == "application/msword":
        return extract_text_from_doc(file)
    elif file.type == "text/plain":
        return extract_text_from_txt(file)
    else:
        raise ValueError(
            "Unsupported file type. Please upload PDF, DOCX, DOC, or TXT files."
        )