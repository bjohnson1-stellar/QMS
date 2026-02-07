import PyPDF2
import sqlite3
import re

# Test extraction from first PDF
pdf_path = r'D:/Projects/07308-BIRDCAGE/Refrigeration/RS11070-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-7-Rev.6.pdf'

print("Opening PDF...")
try:
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        print(f"PDF has {len(reader.pages)} pages")
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            text += page_text
            print(f"Page {i+1}: {len(page_text)} chars")
        print(f"\nTotal text extracted: {len(text)} characters")
        
        # Look for support tags
        pattern = r'\b([A-Z]{1,3})-(\d{1,4}[A-Z]?)\b'
        matches = re.finditer(pattern, text)
        tags = set()
        for match in matches:
            prefix, number = match.groups()
            if prefix.upper() in ['S', 'HS', 'PS', 'RS', 'SS']:
                tag = f"{prefix.upper()}-{number}"
                tags.add(tag)
        
        print(f"\nFound {len(tags)} support tags:")
        for tag in sorted(tags)[:20]:
            print(f"  - {tag}")
        if len(tags) > 20:
            print(f"  ... and {len(tags) - 20} more")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
