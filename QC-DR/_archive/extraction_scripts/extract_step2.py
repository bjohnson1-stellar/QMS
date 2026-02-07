import PyPDF2
import re

pdf_path = r'D:/Projects/07308-BIRDCAGE/Refrigeration/RS11070-REFRIGERATION-PLAN-SUPPORTS-FLOOR-AREA-7-Rev.6.pdf'

with open(pdf_path, 'rb') as file:
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    # Show first 1000 chars to see what we're working with
    print("First 1000 characters of extracted text:")
    print("=" * 70)
    print(text[:1000])
    print("=" * 70)
    
    # Look for drawing number
    dwg_match = re.search(r'RS\d{5}', text)
    if dwg_match:
        print(f"\nDrawing number: {dwg_match.group()}")
    
    # Look for revision
    rev_match = re.search(r'REV[\s.:-]*(\d+)', text, re.IGNORECASE)
    if rev_match:
        print(f"Revision: {rev_match.group(1)}")
    
    # Try broader patterns for supports
    # Look for patterns like "S-7-1" or just numbers that might be supports
    patterns = [
        (r'S-\d+-\d+', 'S-X-X pattern'),
        (r'\bRS-\d+', 'RS-X pattern'),
        (r'\bHS-\d+', 'HS-X pattern'),
        (r'\bPS-\d+', 'PS-X pattern'),
        (r'SUPPORT\s+\d+', 'SUPPORT X pattern'),
    ]
    
    print("\n\nSearching for support patterns:")
    for pattern, desc in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"\n{desc}: Found {len(matches)} matches")
            for m in matches[:10]:
                print(f"  - {m}")
