"""Convert PDFs to PNG images for analysis"""
import fitz  # PyMuPDF
from pathlib import Path

def pdf_to_png(pdf_path, output_dir):
    """Convert first page of PDF to PNG"""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    page = doc[0]  # First page

    # Render at high resolution
    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
    pix = page.get_pixmap(matrix=mat)

    output_file = output_dir / f"{pdf_path.stem}.png"
    pix.save(output_file)
    doc.close()

    return output_file

if __name__ == '__main__':
    sheets = [
        'D:/Projects/07308-BIRDCAGE/Refrigeration/R11070-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-7-Rev.5.pdf',
        'D:/Projects/07308-BIRDCAGE/Refrigeration/R11080-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-8-Rev.5.pdf',
        'D:/Projects/07308-BIRDCAGE/Refrigeration/R11100-REFRIGERATION-PLAN-PIPE-AND-DUCT-FLOOR-AREA-10-Rev.5.pdf'
    ]

    output_dir = Path('D:/temp_extractions')

    for sheet_path in sheets:
        print(f"Converting {Path(sheet_path).name}...")
        output_file = pdf_to_png(sheet_path, output_dir)
        print(f"  Saved to: {output_file}")
