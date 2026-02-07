import PyPDF2
import sys
import base64
from pathlib import Path

def extract_pdf_content(pdf_path):
    """Extract text and basic info from PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)

            info = {
                'pages': len(reader.pages),
                'text': []
            }

            # Extract text from each page
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                info['text'].append(f"--- PAGE {i+1} ---\n{text}\n")

            return info
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_pdf_content(pdf_path)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Pages: {result['pages']}")
    print("\n" + "="*80 + "\n")
    for text in result['text']:
        print(text)
