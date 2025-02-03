import pdfplumber
import docx
import re
# Extract text from PDF
def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        return text.strip()
# Extract text from DOCX
def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    return text.strip()
# Extract text from TXT
def extract_text_from_txt(file):
    return file.read().decode("utf-8").strip()
# Extract text from file based on type
def extract_text_from_file(file):
    if file.type == "application/pdf":
        return extract_text_from_pdf(file)
    elif file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
        return extract_text_from_docx(file)
    elif file.type == "text/plain":
        return extract_text_from_txt(file)
    else:
        raise ValueError("Unsupported file type. Please upload PDF, DOCX, or TXT files.")
# Extract email and name from resume text
def extract_email_and_name(resume_text):
    email = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", resume_text)
    name = resume_text.split("\n")[0]
    return name.strip(), email.group(0) if email else None