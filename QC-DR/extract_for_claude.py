#!/usr/bin/env python3
"""
Extract PDF pages as images for Claude Code to analyze
"""
import sys
import fitz  # PyMuPDF
from pathlib import Path

def pdf_to_images(pdf_path, output_dir, sheet_id):
    """Convert first page of PDF to PNG image"""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Open PDF
    doc = fitz.open(pdf_path)

    # Get first page
    page = doc[0]

    # Render at high resolution for better readability
    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = 144 DPI
    pix = page.get_pixmap(matrix=mat)

    # Save as PNG
    output_file = output_dir / f"sheet_{sheet_id}.png"
    pix.save(str(output_file))

    doc.close()

    print(f"Saved: {output_file}")
    return str(output_file)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: extract_for_claude.py <pdf_path> <output_dir> <sheet_id>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]
    sheet_id = sys.argv[3]

    output_file = pdf_to_images(pdf_path, output_dir, sheet_id)
    print(f"OUTPUT_FILE={output_file}")
