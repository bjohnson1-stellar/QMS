"""
Manual text extraction from Freshpet architectural drawings.
Since we can't call the Anthropic API from the script, we'll just extract
the raw text and display it for manual review.
"""

import sys
from pathlib import Path

# Add qms to path
sys.path.insert(0, str(Path(__file__).parent))

from qms.pipeline.extractor import extract_pdf_text, classify_drawing

def main():
    """Extract and display text from the three drawings."""
    drawings = [
        (451, "D:\\qms\\data\\projects\\07609-Freshpet\\Architectural\\A3001-BUILDING-SECTIONS-Rev.2.pdf"),
        (452, "D:\\qms\\data\\projects\\07609-Freshpet\\Architectural\\A3002-BUILDING-SECTIONS-Rev.1.pdf"),
        (453, "D:\\qms\\data\\projects\\07609-Freshpet\\Architectural\\A3003-BUILDING-SECTIONS-Rev.1.pdf"),
    ]

    for sheet_id, file_path in drawings:
        print("\n" + "=" * 80)
        print(f"SHEET {sheet_id}: {Path(file_path).name}")
        print("=" * 80)

        # Extract text
        text = extract_pdf_text(Path(file_path))
        drawing_type, complexity = classify_drawing(text, Path(file_path).name)

        print(f"\nDrawing Type: {drawing_type}")
        print(f"Complexity: {complexity}")
        print(f"\nText Length: {len(text)} characters")
        print("\nEXTRACTED TEXT:")
        print("-" * 80)
        print(text)
        print("-" * 80)

        # Extract equipment tags (simple regex)
        import re
        tags = set()

        # Common equipment tag patterns
        patterns = [
            r'\b([A-Z]{1,3}-\d{2,4}[A-Z]?)\b',  # P-101, TK-201, etc.
            r'\b([A-Z]{2,4}\s*\d{2,4})\b',      # EU 101, AHU 201, etc.
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            tags.update(matches)

        if tags:
            print(f"\nPOTENTIAL EQUIPMENT TAGS FOUND ({len(tags)}):")
            for tag in sorted(tags):
                print(f"  - {tag}")
        else:
            print("\nNo equipment tags detected with standard patterns.")

        print("\n")

if __name__ == "__main__":
    main()
