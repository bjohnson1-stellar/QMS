#!/usr/bin/env python3
"""
Extract text content from PDF drawings for database population
"""
import sys
import PyPDF2
import json

def extract_pdf_text(pdf_path):
    """Extract text from all pages of a PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text_by_page = []

            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text = page.extract_text()
                text_by_page.append({
                    'page': page_num + 1,
                    'text': text
                })

            return {
                'success': True,
                'page_count': len(reader.pages),
                'pages': text_by_page
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No PDF path provided'}))
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_pdf_text(pdf_path)
    print(json.dumps(result, indent=2))
