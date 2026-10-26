
from openpyxl import load_workbook

def extract_xlsx(file_path):
    try:
        workbook = load_workbook(
            file_path, read_only=True, data_only=True
        )

        text = ""

        for sheet in workbook.worksheets:
            text += f"Sheet: {sheet.title}\n"

            for row in sheet.iter_rows(values_only=True):
                values = [
                    str(cell) if cell is not None else ""
                    for cell in row
                ]

                if any(values):
                    text += " | ".join(values) + "\n"

        workbook.close()
        return text

    except Exception as error:
        print("Error reading Excel file:", error)
        return None


