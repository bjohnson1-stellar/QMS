"""
Convert PDF pages to PNG images for analysis.
"""
import fitz  # PyMuPDF
import os
from pathlib import Path

SHEETS = [
    {
        "id": 131,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS14070-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-7-Rev.5.pdf",
    },
    {
        "id": 132,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS14080-REFRIGERATION-PLAN-SUPPORTS-ROOF-AREA-8-Rev.5.pdf",
    },
    {
        "id": 133,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS42101-REFRIGERATION-PLAN-MACHINE-ROOM-SUPPORTS-FLOOR-Rev.3.pdf",
    },
    {
        "id": 134,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/RS42401-REFRIGERATION-PLAN-MACHINE-ROOM-SUPPORTS-ROOF-Rev.3.pdf",
    }
]

output_dir = Path("D:/Inbox/support_plans")
output_dir.mkdir(exist_ok=True)

for sheet in SHEETS:
    pdf_path = sheet["path"]
    sheet_id = sheet["id"]

    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        continue

    print(f"Processing sheet {sheet_id}: {Path(pdf_path).name}")

    doc = fitz.open(pdf_path)

    # Convert first page only
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x resolution

    output_path = output_dir / f"sheet_{sheet_id}_page_1.png"
    pix.save(str(output_path))

    print(f"  Saved: {output_path} ({pix.width}x{pix.height})")

    doc.close()

print(f"\nAll images saved to: {output_dir}")
