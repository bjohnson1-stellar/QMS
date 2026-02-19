"""
Extract text from mechanical drawings and analyze structure.
"""

import fitz  # PyMuPDF
from pathlib import Path

SHEETS = [
    {
        "id": 551,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M1401-MECHANICAL-OVERALL-ROOF-PLAN-Rev.1.pdf",
        "drawing_number": "M1401-MECHANICAL-OVERALL-ROOF-PLAN",
    },
    {
        "id": 552,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M3001-MECHANICAL-SECTIONS-Rev.1.pdf",
        "drawing_number": "M3001-MECHANICAL-SECTIONS",
    },
    {
        "id": 553,
        "path": r"D:\qms\data\projects\07609-Freshpet\Mechanical\M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN-Rev.1.pdf",
        "drawing_number": "M4001-ENLARGED-FIRST-FLOOR-MECHANICAL-PLAN",
    },
]


def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text from PDF."""
    doc = fitz.open(pdf_path)
    text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            text_parts.append(f"\n=== PAGE {page_num + 1} ===\n{text}")

    doc.close()
    return "\n".join(text_parts)


def main():
    for sheet in SHEETS:
        print(f"\n{'='*80}")
        print(f"Sheet {sheet['id']}: {sheet['drawing_number']}")
        print(f"{'='*80}")

        text = extract_pdf_text(sheet["path"])

        # Save to file for analysis
        output_file = Path(sheet["path"]).with_suffix(".txt")
        output_file.write_text(text, encoding="utf-8")

        print(f"Extracted {len(text)} characters")
        print(f"Saved to: {output_file}")

        # Show first 2000 characters
        print(f"\nFirst 2000 characters:")
        print(text[:2000])


if __name__ == "__main__":
    main()
