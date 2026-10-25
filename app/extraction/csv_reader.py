
import csv

def extract_csv(file_path):
    try:
        text = ""

        with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file)

            for row in reader:
                text += " | ".join(row) + "\n"

        if not text.strip():
            print("No readable text found.")
            return None

        return text

    except FileNotFoundError:
        print("Error: CSV file not found.")
        return None

    except Exception as error:
        print("Error reading CSV:", error)
        return None


