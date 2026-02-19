"""
Manual extraction helper - converts PDFs to images for Claude Code to analyze.

Since we're running in Claude Code context, we'll convert PDFs to PNGs
and then I can read them directly with my vision capabilities.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """Convert PDF to PNG images using pdf2image."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("ERROR: pdf2image not installed. Run: pip install pdf2image")
        print("Also requires poppler: https://github.com/oschwartz10612/poppler-windows/releases/")
        return []

    output_dir.mkdir(exist_ok=True)

    print(f"Converting {pdf_path.name} to images at {dpi} DPI...")
    images = convert_from_path(pdf_path, dpi=dpi)

    image_paths = []
    for i, image in enumerate(images, 1):
        img_path = output_dir / f"{pdf_path.stem}_page{i}.png"
        image.save(img_path, "PNG")
        image_paths.append(img_path)
        print(f"  Saved page {i} to {img_path.name}")

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

    for sheet_name in sheets:
        pdf_path = base_path / sheet_name
        if not pdf_path.exists():
            print(f"SKIP: {sheet_name} not found")
            continue

        print(f"\n{'='*80}")
        print(f"Processing: {sheet_name}")
        print(f"{'='*80}")

        images = convert_pdf_to_images(pdf_path, output_path)
        print(f"Generated {len(images)} images")


if __name__ == "__main__":
    main()
