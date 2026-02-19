"""
Convert PDFs to images using PyMuPDF for Claude Code analysis.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def convert_pdf_to_images_pymupdf(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """Convert PDF to PNG images using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
        return []

    output_dir.mkdir(exist_ok=True)

    print(f"Converting {pdf_path.name} to images at {dpi} DPI...")

    doc = fitz.open(pdf_path)
    image_paths = []

    # Calculate zoom factor for desired DPI (72 DPI is default)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)

        img_path = output_dir / f"{pdf_path.stem}_page{page_num + 1}.png"
        pix.save(img_path)
        image_paths.append(img_path)
        print(f"  Saved page {page_num + 1} to {img_path.name}")

    doc.close()
    return image_paths


def main():
    """Convert the three utility PDFs to images."""

    sheets = [
        "U1161-PARTIAL-FIRST-FLOOR-UTILITIES-PLAN---AREA-6-Rev.1.pdf",
        "U1301-UTILITY-OVERALL-INTERSTITIAL-FLOOR-PLAN-Rev.2.pdf",
        "U1401-UTILITY-OVERALL-ROOF-PLAN-Rev.2.pdf",
    ]

    base_path = Path(r"D:\qms\data\projects\07609-Freshpet\Utility")
    output_path = Path(r"D:\qms\data\projects\07609-Freshpet\Utility\_extractions")

    all_images = []

    for sheet_name in sheets:
        pdf_path = base_path / sheet_name
        if not pdf_path.exists():
            print(f"SKIP: {sheet_name} not found")
            continue

        print(f"\n{'='*80}")
        print(f"Processing: {sheet_name}")
        print(f"{'='*80}")

        images = convert_pdf_to_images_pymupdf(pdf_path, output_path, dpi=150)
        print(f"Generated {len(images)} images")
        all_images.extend(images)

    print(f"\n{'='*80}")
    print(f"TOTAL: {len(all_images)} images ready for analysis")
    print(f"Location: {output_path}")
    print(f"{'='*80}\n")

    print("Next steps:")
    print("1. Share these image paths with Claude Code")
    print("2. Claude reads each image and extracts equipment data")
    print("3. Data is loaded into the database")


if __name__ == "__main__":
    main()
