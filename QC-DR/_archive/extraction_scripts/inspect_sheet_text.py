#!/usr/bin/env python3
"""Inspect text extracted from refrigeration drawings"""

import fitz

SHEETS = [
    ('R14080', 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14080-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-8-Rev.5.pdf'),
    ('R14100', 'D:/Projects/07308-BIRDCAGE/Refrigeration/R14100-REFRIGERATION-PLAN-PIPE-AND-DUCT-ROOF-AREA-10-Rev.3.pdf'),
    ('R31101', 'D:/Projects/07308-BIRDCAGE/Refrigeration/R31101-REFRIGERATION-MACHINE-ROOM-ELEVATIONS-Rev.3.pdf'),
]

for drawing_num, path in SHEETS:
    print(f"\n{'=' * 80}")
    print(f"{drawing_num}")
    print('=' * 80)

    doc = fitz.open(path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        print(f"\nPage {page_num + 1}:")
        print("-" * 80)
        print(text)
        print("-" * 80)

    doc.close()
