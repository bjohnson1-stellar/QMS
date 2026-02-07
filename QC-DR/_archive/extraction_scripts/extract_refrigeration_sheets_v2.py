#!/usr/bin/env python3
"""
Extract data from refrigeration machine room roof plan drawings.
This version uses the Claude Code session's API access.
"""

import os
import sys
import json
import sqlite3
import base64
from pathlib import Path

# Check for API key in environment first
api_key = os.environ.get("ANTHROPIC_API_KEY")

if not api_key:
    # Try to use subprocess to get it via the current session
    print("Note: Using Claude Code session API access")
    # We'll embed the extraction logic inline without needing separate API calls
    USE_DIRECT_API = False
else:
    USE_DIRECT_API = True
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

DB_PATH = "D:/quality.db"

SHEETS = [
    {
        "id": 37,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R41401-REFRIGERATION-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-ROOF-Rev.6.pdf",
        "drawing_number": "R41401",
        "title": "REFRIGERATION PLAN MACHINE ROOM PIPE AND EQUIPMENT ROOF",
        "revision": "6"
    },
    {
        "id": 38,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R41402-REFRIGERATION-PLAN-MACHINE-ROOM-PIPE-AND-EQUIPMENT-ROOF-Rev.1.pdf",
        "drawing_number": "R41402",
        "title": "REFRIGERATION PLAN MACHINE ROOM PIPE AND EQUIPMENT ROOF",
        "revision": "1"
    },
    {
        "id": 39,
        "path": "D:/Projects/07308-BIRDCAGE/Refrigeration/R45101-REFRIGERATION-PLAN-MACHINE-ROOM-RELIEF-PIPE-FLOOR-AND-ROOF-Rev.5.pdf",
        "drawing_number": "R45101",
        "title": "REFRIGERATION PLAN MACHINE ROOM RELIEF PIPE FLOOR AND ROOF",
        "revision": "5"
    }
]


def encode_pdf_page(pdf_path: str, page: int = 1) -> str:
    """Convert first page of PDF to base64-encoded image."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        if page > len(doc):
            page = len(doc)

        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
        img_data = pix.pil_tobytes(format="PNG")
        doc.close()

        return base64.standard_b64encode(img_data).decode("utf-8")
    except Exception as e:
        print(f"Error converting PDF: {e}")
        raise


def save_pdf_image(pdf_path: str, output_path: str, page: int = 1):
    """Save first page of PDF as PNG image."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        if page > len(doc):
            page = len(doc)

        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
        pix.save(output_path)
        doc.close()
        print(f"Saved image to: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving PDF image: {e}")
        return False


def main():
    """Main extraction workflow - prepare images for manual extraction."""
    print("=" * 80)
    print("REFRIGERATION MACHINE ROOM DRAWING EXTRACTION")
    print("=" * 80)
    print(f"Project: 07308-BIRDCAGE")
    print(f"Sheets: {len(SHEETS)}")
    print(f"Database: {DB_PATH}")
    print("=" * 80)

    if not USE_DIRECT_API:
        print("\nPreparing PDF images for extraction via Claude Code...")
        print("These will be processed interactively.\n")

        # Create temp directory for images
        temp_dir = "D:/temp_extraction"
        os.makedirs(temp_dir, exist_ok=True)

        for sheet in SHEETS:
            output_path = f"{temp_dir}/{sheet['drawing_number']}_Rev{sheet['revision']}.png"
            print(f"Converting: {sheet['drawing_number']} Rev {sheet['revision']}")

            if os.path.exists(sheet['path']):
                save_pdf_image(sheet['path'], output_path)
            else:
                print(f"  ERROR: File not found: {sheet['path']}")

        print(f"\nImages saved to: {temp_dir}")
        print("Please use Claude Code to view these images and extract data.")
        return 0

    # If we have direct API access, use it
    print("Note: This script needs to be run interactively via Claude Code")
    print("to access the API. Please request extraction through the chat interface.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
