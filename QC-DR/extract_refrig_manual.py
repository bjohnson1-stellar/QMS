#!/usr/bin/env python3
"""
Manual Refrigeration Plan Extractor

Converts PDFs to images for manual extraction by Claude Code.
Claude Code will then analyze the images and extract the data.
"""

import sys
from pathlib import Path
import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).parent))
from sis_common import get_db_connection, get_logger

logger = get_logger('extract_refrig_manual')


def pdf_to_images(pdf_path: str, output_dir: str, sheet_id: int) -> list:
    """Convert PDF pages to PNG images"""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(f"Converting {pdf_path.name} to images")

    doc = fitz.open(str(pdf_path))
    image_paths = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render at 2x resolution for better quality
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)

        output_path = output_dir / f"sheet_{sheet_id}_page_{page_num + 1}.png"
        pix.save(str(output_path))

        image_paths.append(str(output_path))
        logger.info(f"  Saved page {page_num + 1} to {output_path.name}")

    doc.close()
    return image_paths


def main():
    # Get sheets 19, 20, 21
    with get_db_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT id, drawing_number, file_path
            FROM sheets
            WHERE id IN (19, 20, 21)
            ORDER BY id
        """)
        sheets = cursor.fetchall()

    if not sheets:
        logger.error("No sheets found")
        return

    output_dir = Path("D:/QC-DR/_temp_extraction")

    all_images = []
    for sheet in sheets:
        try:
            images = pdf_to_images(
                sheet['file_path'],
                output_dir,
                sheet['id']
            )
            all_images.extend([(sheet['id'], sheet['drawing_number'], img) for img in images])
        except Exception as e:
            logger.error(f"Failed to process sheet {sheet['id']}: {e}")

    print("\n" + "=" * 70)
    print("IMAGES CREATED FOR MANUAL EXTRACTION")
    print("=" * 70)
    print(f"\nImages saved to: {output_dir}")
    print(f"\nTotal images: {len(all_images)}")
    print("\nFiles:")
    for sheet_id, drawing_num, img_path in all_images:
        print(f"  Sheet {sheet_id} ({drawing_num}): {img_path}")

    print("\nNext: Claude Code will analyze these images and extract data")


if __name__ == '__main__':
    main()
