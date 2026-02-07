#!/usr/bin/env python3
"""Extract text from PDF files using PyPDF2"""

import PyPDF2
import sys

def extract_pdf_text(file_path):
    """Extract all text from PDF."""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text_parts.append(f"=== PAGE {page_num} ===")
                text_parts.append(page.extract_text())
            return '\n\n'.join(text_parts)
    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract_text_from_pdfs.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    text = extract_pdf_text(pdf_file)
    print(text)
