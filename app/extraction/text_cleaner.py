
import re

def clean_text(text):
    # Remove null characters
    text = text.replace("\x00", "")

    # Make line endings consistent
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove extra spaces on each line
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = re.sub(r"[ \t]+", " ", line)
        cleaned_lines.append(line.strip())

    text = "\n".join(cleaned_lines)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


