"""
Extract text content from PDFs for manual review.
"""
import pypdf
from pathlib import Path

SHEETS = [
    {
        "id": 577,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1112.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-2-Rev.1.pdf",
        "drawing_number": "R1112.1"
    },
    {
        "id": 578,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1113.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-3-Rev.1.pdf",
        "drawing_number": "R1113.1"
    },
    {
        "id": 579,
        "path": r"D:\qms\data\projects\07609-Freshpet\Refrigeration\R1114.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FLOOR-AREA-4-Rev.1.pdf",
        "drawing_number": "R1114.1"
    }
]

def extract_text(pdf_path: str) -> str:
    """Extract all text from PDF."""
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n\n"
    return text

def main():
    for sheet in SHEETS:
        print(f"\n{'='*80}")
        print(f"Sheet {sheet['id']}: {sheet['drawing_number']}")
        print(f"{'='*80}\n")

        text = extract_text(sheet['path'])
        print(text[:3000])  # First 3000 chars
        print(f"\n... (total length: {len(text)} chars)\n")

if __name__ == '__main__':
    main()
