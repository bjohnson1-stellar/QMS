#!/usr/bin/env python3
"""Convert PDF pages to PNG images for analysis"""

import fitz  # PyMuPDF
import sys
from pathlib import Path

def convert_pdf_page(pdf_path, page_num=0, output_path=None):
    """Convert specific PDF page to PNG"""
    doc = fitz.open(pdf_path)

    if page_num >= len(doc):
        print(f"ERROR: Page {page_num} does not exist (PDF has {len(doc)} pages)")
        doc.close()
        return None

    page = doc[page_num]
    # Render at 150 DPI for good quality
    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))

    if output_path is None:
        pdf_stem = Path(pdf_path).stem
        output_path = f"D:/temp_{pdf_stem}_page{page_num}.png"

    pix.save(output_path)
    doc.close()

    print(f"Saved: {output_path}")
    return output_path

if __name__ == '__main__':
    sheets = [
        ("D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11060-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-6-Rev.5.pdf", "D:/temp_RC11060.png"),
        ("D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11070-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR-AREA-7-Rev.6.pdf", "D:/temp_RC11070.png"),
        ("D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC11080-REFRIGERATION-CONTROLS-PLAN-PIPE-AND-DUCT-FLOOR---AREA-8-Rev.10.pdf", "D:/temp_RC11080.png")
    ]

    for pdf_path, output_path in sheets:
        convert_pdf_page(pdf_path, 0, output_path)
