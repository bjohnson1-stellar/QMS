#!/usr/bin/env python3
"""
Debug script to see what text is extracted from PDFs.
"""
import PyPDF2

pdf_files = [
    'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50001-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.7.pdf',
    'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50002-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.4.pdf',
    'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC50004-REFRIGERATION-CONTROLS-DETAIL-SHEET-Rev.1.pdf',
    'D:/Projects/07308-BIRDCAGE/Refrigeration-Controls/RC60000-REFRIGERATION-CONTROLS-CABLE-SCHEDULE-Rev.12.pdf',
]

for pdf_path in pdf_files:
    print(f"\n{'='*80}")
    print(f"FILE: {pdf_path.split('/')[-1]}")
    print('='*80)

    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            print(f"Number of pages: {len(reader.pages)}")

            for page_num, page in enumerate(reader.pages[:2], 1):  # First 2 pages
                text = page.extract_text()
                print(f"\n--- PAGE {page_num} (first 1500 chars) ---")
                print(text[:1500])
                print(f"\n--- Text length: {len(text)} characters ---")

    except Exception as e:
        print(f"ERROR: {e}")
