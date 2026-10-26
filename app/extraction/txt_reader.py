
from pathlib import Path

def extract_txt(file_path):
    try:
        text = Path(file_path).read_text(encoding="utf-8")
        return text

    except FileNotFoundError:
        print("Error: File not found.")
        return None

    except UnicodeDecodeError:
        print("Error: Unable to read the file's text.")
        return None


