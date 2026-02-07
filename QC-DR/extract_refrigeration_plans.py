#!/usr/bin/env python3
"""
Refrigeration Plan Drawing Extractor

Extracts lines, equipment, and instruments from refrigeration plan drawings
using the Anthropic API with PDF vision capabilities.

Usage:
    python extract_refrigeration_plans.py --sheet-ids 19,20,21
    python extract_refrigeration_plans.py --all-pending
"""

import argparse
import base64
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add QC-DR to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from sis_common import get_db_connection, get_logger, SIS_PATHS

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed")
    print("Install with: pip install anthropic")
    sys.exit(1)

logger = get_logger('extract_refrigeration_plans')


class RefrigerationPlanExtractor:
    """Extract data from refrigeration plan drawings"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Current Sonnet model

    def get_pending_sheets(self, sheet_ids: Optional[List[int]] = None) -> List[Dict]:
        """Get sheets to process"""
        with get_db_connection(readonly=True) as conn:
            if sheet_ids:
                placeholders = ','.join('?' * len(sheet_ids))
                query = f"""
                    SELECT id, drawing_number, title, revision, file_path
                    FROM sheets
                    WHERE id IN ({placeholders})
                    ORDER BY id
                """
                cursor = conn.execute(query, sheet_ids)
            else:
                query = """
                    SELECT s.id, s.drawing_number, s.title, s.revision, s.file_path
                    FROM sheets s
                    JOIN processing_queue q ON q.sheet_id = s.id
                    WHERE q.task = 'EXTRACT' AND q.status = 'pending'
                    ORDER BY q.priority, s.id
                    LIMIT 10
                """
                cursor = conn.execute(query)

            sheets = []
            for row in cursor.fetchall():
                sheets.append({
                    'id': row['id'],
                    'drawing_number': row['drawing_number'],
                    'title': row['title'],
                    'revision': row['revision'],
                    'file_path': row['file_path']
                })

            return sheets

    def read_pdf_as_base64(self, file_path: str) -> str:
        """Read PDF file and encode as base64"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        with open(path, 'rb') as f:
            return base64.standard_b64encode(f.read()).decode('utf-8')

    def classify_drawing(self, drawing_number: str, title: str) -> Tuple[str, str]:
        """Classify drawing type and complexity"""
        drawing_number_upper = drawing_number.upper()
        title_upper = title.upper() if title else ""

        # Determine type
        if 'PLAN' in title_upper or 'PIPE-AND-DUCT' in title_upper:
            drawing_type = 'REFRIGERATION_PLAN'
        elif 'ISO' in drawing_number_upper:
            drawing_type = 'ISOMETRIC'
        elif 'P&ID' in title_upper or 'P-ID' in title_upper:
            drawing_type = 'PID'
        elif 'GA' in drawing_number_upper or 'GENERAL' in title_upper:
            drawing_type = 'GA'
        else:
            drawing_type = 'PLAN'

        # Estimate complexity
        complexity = 'medium'  # Default for refrigeration plans

        return drawing_type, complexity

    def extract_from_drawing(self, sheet: Dict) -> Dict:
        """Extract data from a single drawing using Anthropic API"""
        logger.info(f"Processing sheet {sheet['id']}: {sheet['drawing_number']}")

        # Classify the drawing
        drawing_type, complexity = self.classify_drawing(
            sheet['drawing_number'],
            sheet['title'] or ""
        )

        logger.info(f"  Type: {drawing_type}, Complexity: {complexity}")

        # Read PDF
        try:
            pdf_data = self.read_pdf_as_base64(sheet['file_path'])
        except Exception as e:
            logger.error(f"  Failed to read PDF: {e}")
            return {
                'success': False,
                'error': str(e),
                'drawing_type': drawing_type,
                'complexity': complexity
            }

        # Create extraction prompt
        prompt = self._create_extraction_prompt(drawing_type)

        # Call Anthropic API
        try:
            logger.info(f"  Calling Anthropic API with model {self.model}")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Parse response
            response_text = response.content[0].text
            logger.info(f"  Received response ({len(response_text)} chars)")

            # Extract JSON from response
            extracted_data = self._parse_extraction_response(response_text)

            return {
                'success': True,
                'drawing_type': drawing_type,
                'complexity': complexity,
                'model': self.model,
                'data': extracted_data
            }

        except Exception as e:
            logger.error(f"  API call failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'drawing_type': drawing_type,
                'complexity': complexity
            }

    def _create_extraction_prompt(self, drawing_type: str) -> str:
        """Create extraction prompt based on drawing type"""

        if drawing_type == 'REFRIGERATION_PLAN':
            return """Extract all refrigeration piping and equipment data from this plan drawing.

For each REFRIGERATION LINE visible, provide:
- line_number: Full line number (format: SIZE-MATERIAL-NUMBER-SPEC, e.g., "1-1/2-CS-101-R1")
- size: Pipe size (e.g., "1-1/2", "2", "3")
- material: Material code (e.g., CS, SS, CU for copper)
- spec_class: Spec class if shown (e.g., R1, R2)
- from_location: Starting equipment or location
- to_location: Ending equipment or location
- service: Service description if noted (e.g., "HOT GAS", "SUCTION", "LIQUID")

For each EQUIPMENT item visible (refrigeration equipment), provide:
- tag: Equipment tag number (e.g., "RF-101", "COND-1", "EVAP-2")
- description: Equipment name or description
- equipment_type: Type (e.g., CONDENSER, EVAPORATOR, COMPRESSOR, RECEIVER, PUMP)

For each INSTRUMENT or CONTROL DEVICE, provide:
- tag: Instrument tag (e.g., "PT-101", "TT-201", "PSV-301")
- instrument_type: Type (e.g., PRESSURE_TRANSMITTER, TEMPERATURE_TRANSMITTER, PRESSURE_SAFETY_VALVE)
- loop_number: Associated loop or control number if shown

Return the data as valid JSON in this exact format:
{
  "lines": [
    {
      "line_number": "1-1/2-CS-101-R1",
      "size": "1-1/2",
      "material": "CS",
      "spec_class": "R1",
      "from_location": "RF-101",
      "to_location": "COND-1",
      "service": "HOT GAS",
      "confidence": 0.9
    }
  ],
  "equipment": [
    {
      "tag": "RF-101",
      "description": "Refrigeration Compressor",
      "equipment_type": "COMPRESSOR",
      "confidence": 0.95
    }
  ],
  "instruments": [
    {
      "tag": "PT-101",
      "instrument_type": "PRESSURE_TRANSMITTER",
      "loop_number": "101",
      "confidence": 0.85
    }
  ],
  "notes": ["Any special observations or areas of uncertainty"]
}

Confidence scoring guidelines:
- 0.9-1.0: Clear, readable text and symbols
- 0.7-0.9: Mostly clear, minor uncertainty
- 0.5-0.7: Partially obscured or ambiguous
- <0.5: Significant uncertainty, flag for review

If text is unclear, provide your best interpretation and reduce confidence score.
Return ONLY the JSON object, no other text."""

        else:
            # Generic plan extraction
            return """Extract all piping, equipment, and instrumentation from this drawing.

Provide data as JSON with lines, equipment, and instruments arrays.
Include confidence scores (0.0-1.0) for each item.
Return ONLY the JSON object."""

    def _parse_extraction_response(self, response_text: str) -> Dict:
        """Parse JSON from API response"""
        # Try to find JSON in response
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        response_text = response_text.strip()
        if response_text.startswith('json'):
            response_text = response_text[4:].strip()

        try:
            data = json.loads(response_text)
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"  Failed to parse JSON: {e}")
            logger.warning(f"  Response text: {response_text[:500]}")
            return {
                'lines': [],
                'equipment': [],
                'instruments': [],
                'notes': [f"Failed to parse response: {e}"]
            }

    def store_extraction(self, sheet_id: int, result: Dict) -> None:
        """Store extracted data in database"""
        if not result.get('success'):
            logger.error(f"  Cannot store failed extraction for sheet {sheet_id}")
            return

        data = result['data']

        with get_db_connection() as conn:
            # Store lines
            lines_added = 0
            for line in data.get('lines', []):
                try:
                    conn.execute("""
                        INSERT INTO lines (
                            sheet_id, line_number, size, material, spec_class,
                            from_location, to_location, service, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        line.get('line_number'),
                        line.get('size'),
                        line.get('material'),
                        line.get('spec_class'),
                        line.get('from_location'),
                        line.get('to_location'),
                        line.get('service'),
                        line.get('confidence', 1.0)
                    ))
                    lines_added += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"  Duplicate line skipped: {line.get('line_number')}")

            # Store equipment
            equipment_added = 0
            for equip in data.get('equipment', []):
                try:
                    conn.execute("""
                        INSERT INTO equipment (
                            sheet_id, tag, description, equipment_type, confidence
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        equip.get('tag'),
                        equip.get('description'),
                        equip.get('equipment_type'),
                        equip.get('confidence', 1.0)
                    ))
                    equipment_added += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"  Duplicate equipment skipped: {equip.get('tag')}")

            # Store instruments
            instruments_added = 0
            for inst in data.get('instruments', []):
                try:
                    conn.execute("""
                        INSERT INTO instruments (
                            sheet_id, tag, instrument_type, loop_number, confidence
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        sheet_id,
                        inst.get('tag'),
                        inst.get('instrument_type'),
                        inst.get('loop_number'),
                        inst.get('confidence', 1.0)
                    ))
                    instruments_added += 1
                except sqlite3.IntegrityError as e:
                    logger.warning(f"  Duplicate instrument skipped: {inst.get('tag')}")

            # Calculate quality score
            all_items = (
                data.get('lines', []) +
                data.get('equipment', []) +
                data.get('instruments', [])
            )

            if all_items:
                confidences = [item.get('confidence', 1.0) for item in all_items]
                quality_score = sum(confidences) / len(confidences)
            else:
                quality_score = 0.0

            # Update sheet metadata
            conn.execute("""
                UPDATE sheets
                SET extracted_at = ?,
                    extraction_model = ?,
                    quality_score = ?,
                    drawing_type = ?,
                    complexity = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                result['model'],
                quality_score,
                result['drawing_type'],
                result['complexity'],
                sheet_id
            ))

            # Update processing queue if exists
            conn.execute("""
                UPDATE processing_queue
                SET status = 'completed',
                    completed_at = ?
                WHERE sheet_id = ? AND task = 'EXTRACT'
            """, (datetime.now().isoformat(), sheet_id))

            conn.commit()

            logger.info(f"  Stored: {lines_added} lines, {equipment_added} equipment, {instruments_added} instruments")
            logger.info(f"  Quality score: {quality_score:.2f}")

    def process_sheets(self, sheet_ids: Optional[List[int]] = None) -> Dict:
        """Process multiple sheets"""
        sheets = self.get_pending_sheets(sheet_ids)

        if not sheets:
            logger.info("No sheets to process")
            return {'processed': 0, 'failed': 0, 'results': []}

        logger.info(f"Processing {len(sheets)} sheet(s)")

        results = []
        processed = 0
        failed = 0

        for sheet in sheets:
            try:
                result = self.extract_from_drawing(sheet)

                if result['success']:
                    self.store_extraction(sheet['id'], result)
                    processed += 1
                else:
                    failed += 1

                results.append({
                    'sheet_id': sheet['id'],
                    'drawing_number': sheet['drawing_number'],
                    'success': result['success'],
                    'drawing_type': result.get('drawing_type'),
                    'quality_score': result.get('data', {}).get('quality_score'),
                    'lines': len(result.get('data', {}).get('lines', [])),
                    'equipment': len(result.get('data', {}).get('equipment', [])),
                    'instruments': len(result.get('data', {}).get('instruments', [])),
                    'error': result.get('error')
                })

            except Exception as e:
                logger.error(f"  Unexpected error processing sheet {sheet['id']}: {e}")
                failed += 1
                results.append({
                    'sheet_id': sheet['id'],
                    'drawing_number': sheet['drawing_number'],
                    'success': False,
                    'error': str(e)
                })

        return {
            'processed': processed,
            'failed': failed,
            'results': results
        }


def main():
    parser = argparse.ArgumentParser(description='Extract data from refrigeration plan drawings')
    parser.add_argument('--sheet-ids', help='Comma-separated sheet IDs (e.g., 19,20,21)')
    parser.add_argument('--all-pending', action='store_true', help='Process all pending sheets')

    args = parser.parse_args()

    # Parse sheet IDs
    sheet_ids = None
    if args.sheet_ids:
        try:
            sheet_ids = [int(x.strip()) for x in args.sheet_ids.split(',')]
        except ValueError:
            logger.error("Invalid sheet IDs. Use format: 19,20,21")
            sys.exit(1)
    elif not args.all_pending:
        logger.error("Must specify --sheet-ids or --all-pending")
        sys.exit(1)

    # Run extractor
    try:
        extractor = RefrigerationPlanExtractor()
        summary = extractor.process_sheets(sheet_ids)

        # Print summary
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Processed: {summary['processed']}")
        print(f"Failed: {summary['failed']}")
        print()

        for result in summary['results']:
            print(f"Sheet {result['sheet_id']}: {result['drawing_number']}")
            if result['success']:
                print(f"  Type: {result['drawing_type']}")
                print(f"  Lines: {result['lines']}")
                print(f"  Equipment: {result['equipment']}")
                print(f"  Instruments: {result['instruments']}")
            else:
                print(f"  ERROR: {result.get('error', 'Unknown error')}")
            print()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
