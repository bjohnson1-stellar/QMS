import PyPDF2
from pathlib import Path

def extract_and_show_text(pdf_path):
    """Extract text and show what's in the PDF"""
    print(f"\n{'='*80}")
    print(f"File: {Path(pdf_path).name}")
    print('='*80)

    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            print(f"Pages: {len(reader.pages)}")

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                print(f"\n--- Page {page_num} ({len(text)} chars) ---")
                print(text[:1500])  # Show first 1500 chars

    except Exception as e:
        print(f"Error: {e}")

# Test with one drawing
pdf_path = 'D:/Projects/07308-BIRDCAGE/Refrigeration/R13100-REFRIGERATION-PLAN-PIPE-AND-DUCT-INTERSTITIAL-AREA-10-Rev.5.pdf'
extract_and_show_text(pdf_path)
