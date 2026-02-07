#!/usr/bin/env python3
"""
Extract text from PDF files for manual analysis
"""

import fitz  # PyMuPDF
import sys

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyMuPDF"""
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc, 1):
        text += f"\n{'='*80}\n"
        text += f"PAGE {page_num}\n"
        text += f"{'='*80}\n"
        text += page.get_text()
    doc.close()
    return text

def main():
    sheets = [
        ('116', 'D:/Projects/07308-BIRDCAGE/Refrigeration/RS13010-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-1-Rev.6.pdf'),
        ('117', 'D:/Projects/07308-BIRDCAGE/Refrigeration/RS13020-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-2-Rev.6.pdf'),
        ('118', 'D:/Projects/07308-BIRDCAGE/Refrigeration/RS13030-REFRIGERATION-PLAN-SUPPORTS-INTERSTITIAL-AREA-3-Rev.6.pdf'),
    ]

    for sheet_id, pdf_path in sheets:
        print(f"\n{'='*80}")
        print(f"SHEET {sheet_id}: {pdf_path.split('/')[-1]}")
        print(f"{'='*80}")

        try:
            text = extract_text_from_pdf(pdf_path)

            # Save to file
            output_file = f"D:/sheet_{sheet_id}_text.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)

            print(f"Text extracted: {len(text)} characters")
            print(f"Saved to: {output_file}")

            # Print first 2000 characters as preview
            print("\nPREVIEW (first 2000 chars):")
            print(text[:2000])

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
