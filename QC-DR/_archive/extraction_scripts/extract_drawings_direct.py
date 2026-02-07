#!/usr/bin/env python3
"""
Convert PDF drawings to images for manual extraction.
"""

import os
from pathlib import Path

# Drawing files to process
DRAWINGS = [
    {
        "id": 16,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R13030-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-3-Rev.6.pdf",
        "sheet_number": "R13030",
        "revision": "6"
    },
    {
        "id": 17,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R13040-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-4-Rev.7.pdf",
        "sheet_number": "R13040",
        "revision": "7"
    },
    {
        "id": 18,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R13050-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-5-Rev.6.pdf",
        "sheet_number": "R13050",
        "revision": "6"
    }
]

OUTPUT_DIR = "D:/temp_extraction_images"


def convert_pdf_to_images(pdf_path, output_dir, sheet_number):
    """Convert PDF pages to images using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Installing...")
        os.system("pip install PyMuPDF")
        import fitz

    doc = fitz.open(pdf_path)
    image_paths = []

    os.makedirs(output_dir, exist_ok=True)

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 150 DPI for good quality
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))

        output_path = os.path.join(output_dir, f"{sheet_number}_page_{page_num + 1}.png")
        pix.save(output_path)
        image_paths.append(output_path)
        print(f"Saved: {output_path}")

    doc.close()
    return image_paths


def main():
    """Convert all PDFs to images."""
    print("Converting PDFs to images for extraction...")
    print("=" * 80)

    all_images = []

    for drawing in DRAWINGS:
        print(f"\nProcessing: {drawing['sheet_number']} Rev {drawing['revision']}")
        print(f"File: {drawing['path']}")

        if not Path(drawing['path']).exists():
            print(f"ERROR: File not found: {drawing['path']}")
            continue

        images = convert_pdf_to_images(
            drawing['path'],
            OUTPUT_DIR,
            drawing['sheet_number']
        )

        all_images.extend(images)
        print(f"Converted {len(images)} page(s)")

    print("\n" + "=" * 80)
    print(f"Conversion complete! {len(all_images)} images saved to {OUTPUT_DIR}")
    print("\nImage files:")
    for img in all_images:
        print(f"  - {img}")


if __name__ == "__main__":
    main()
