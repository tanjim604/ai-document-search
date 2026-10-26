
import pymupdf

def extract_pdf(file_path):
    try:
        with pymupdf.open(file_path) as document:
            text = ""

            for page in document:
                text += page.get_text() + "\n"

        if not text.strip():
            print("No readable text found. OCR may be needed.")
            return None

        return text

    except FileNotFoundError:
        print("Error: PDF file not found.")
        return None

    except Exception as error:
        print("Error reading PDF:", error)
        return None



