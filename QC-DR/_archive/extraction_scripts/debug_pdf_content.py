"""Debug script to see what's in the PDFs."""
import fitz

pdf_files = [
    "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11040-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-4-Rev.6.pdf",
    "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11050-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-5-Rev.6.pdf",
    "D:/Projects/07308-BIRDCAGE/Refrigeration/RS11060-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-6-Rev.6.pdf",
]

for pdf_path in pdf_files:
    print(f"\n{'='*70}")
    print(f"FILE: {pdf_path.split('/')[-1]}")
    print('='*70)

    doc = fitz.open(pdf_path)
    print(f"Pages: {len(doc)}")

    for page_num, page in enumerate(doc):
        print(f"\n--- Page {page_num + 1} ---")
        text = page.get_text()
        print(f"Text length: {len(text)}")
        print(f"\nFirst 1000 characters:")
        print(text[:1000])
        print(f"\n... (truncated)")

    doc.close()
