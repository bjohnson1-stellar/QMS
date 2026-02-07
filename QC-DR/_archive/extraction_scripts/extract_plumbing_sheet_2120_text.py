#!/usr/bin/env python3
"""
Extract text from plumbing drawing sheet 2120 for manual analysis.
Sheet: PP11061 - PARTIAL FIRST FLOOR PLUMBING PLAN - AREA 6 - Rev.2
Project: 07650-BRV-PerroGrande

This script extracts text content from the PDF for manual review and entry.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
import os

# Drawing to process
DRAWING = {
    "id": 2120,
    "path": "D:/Projects/07650-BRV-PerroGrande/Plumbing/PP11061-PARTIAL-FIRST-FLOOR-PLUMBING-PLAN---AREA-6-Rev.2.pdf",
    "sheet_number": "PP11061",
    "revision": "2",
    "project": "07650"
}

DB_PATH = "D:/quality.db"


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Installing...")
        os.system("pip install PyMuPDF")
        import fitz

    doc = fitz.open(pdf_path)
    all_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        all_text.append(f"\n{'='*80}\nPAGE {page_num + 1}\n{'='*80}\n{text}")

    doc.close()
    return "\n".join(all_text)


def analyze_text_for_plumbing_data(text):
    """Analyze extracted text to identify plumbing components."""
    print("\n" + "="*80)
    print("TEXT ANALYSIS FOR PLUMBING COMPONENTS")
    print("="*80)

    lines = text.split('\n')

    # Look for common plumbing indicators
    pipes = []
    fixtures = []
    cleanouts = []
    locations = []

    keywords = {
        'pipe_sizes': ['1"', '1-1/2"', '2"', '3"', '4"', '6"', '8"'],
        'pipe_types': ['PVC', 'CI', 'CW', 'HW', 'DW', 'VTR', 'SW', 'CPVC', 'COPPER'],
        'fixtures': ['WC', 'LAV', 'SINK', 'UR', 'FD', 'FLOOR DRAIN', 'WATER CLOSET', 'LAVATORY', 'URINAL'],
        'services': ['WASTE', 'VENT', 'WATER', 'DRAIN', 'STORM', 'SANITARY'],
        'cleanouts': ['CO', 'CLEANOUT', 'C.O.']
    }

    print("\nScanning for plumbing components...")
    print("\nLines with pipe size indicators:")
    for i, line in enumerate(lines):
        for size in keywords['pipe_sizes']:
            if size in line:
                print(f"  Line {i+1}: {line.strip()}")
                break

    print("\nLines with fixture indicators:")
    for i, line in enumerate(lines):
        for fixture in keywords['fixtures']:
            if fixture in line.upper():
                print(f"  Line {i+1}: {line.strip()}")
                break

    print("\nLines with service type indicators:")
    for i, line in enumerate(lines):
        for service in keywords['services']:
            if service in line.upper():
                print(f"  Line {i+1}: {line.strip()}")
                break

    return {
        'pipes': pipes,
        'fixtures': fixtures,
        'cleanouts': cleanouts,
        'locations': locations
    }


def save_text_to_file(text, output_path):
    """Save extracted text to a file for review."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"\nText saved to: {output_path}")


def main():
    """Main extraction process."""
    print("Plumbing Drawing Text Extraction")
    print("=" * 80)
    print(f"Sheet ID: {DRAWING['id']}")
    print(f"Sheet Number: {DRAWING['sheet_number']}")
    print(f"Project: {DRAWING['project']}")
    print(f"File: {DRAWING['path']}")

    try:
        # Check if file exists
        if not Path(DRAWING['path']).exists():
            print(f"ERROR: File not found: {DRAWING['path']}")
            return

        # Extract text
        print("\nExtracting text from PDF...")
        text = extract_text_from_pdf(DRAWING['path'])

        # Save to file
        output_file = f"D:/sheet_{DRAWING['id']}_text_extraction.txt"
        save_text_to_file(text, output_file)

        # Analyze text
        data = analyze_text_for_plumbing_data(text)

        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"\nReview the extracted text in: {output_file}")
        print("\nNext steps:")
        print("1. Review the text file to identify plumbing components")
        print("2. Run extract_plumbing_sheet_2120.py with proper API credentials")
        print("   OR")
        print("3. Manually create a JSON file with extracted data")
        print("4. Use insert_plumbing_data.py to load the data into the database")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
