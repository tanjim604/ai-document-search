
from docx import Document

def extract_docx(file_path):
    try:
        document = Document(file_path)
        text = ""

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"

        if not text.strip():
            print("No readable text found.")
            return None

        return text

    except FileNotFoundError:
        print("Error: Word document not found.")
        return None

    except Exception as error:
        print("Error reading Word document:", error)
        return None


