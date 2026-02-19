"""
Temporary extraction script for Freshpet refrigeration sheets.
"""
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
import fitz
import anthropic

def extract_pdf_content(pdf_path: Path) -> tuple[str, Optional[bytes]]:
    """
    Extract text and/or image from PDF.

    Returns:
        (text_content, image_bytes) - image_bytes is None if text is available
    """
    with fitz.open(pdf_path) as doc:
        page = doc[0]
        text = page.get_text('text')

        # If no text, render as image
        if len(text.strip()) < 100:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes('png')
            return "", img_bytes
        else:
            return text, None

def classify_drawing(sheet_id: int, drawing_number: str, content: str) -> Dict[str, str]:
    """
    Classify drawing type based on drawing number and content.
    """
    drawing_number = drawing_number.upper()

    # Refrigeration Details - typically equipment and pipe details
    if 'DETAILS-PIPE' in drawing_number or 'R5101' in drawing_number:
        return {
            'type': 'Details',
            'subtype': 'Pipe and Equipment',
            'complexity': 'medium',
            'model': 'sonnet'
        }

    # Refrigeration Plan - P&ID-like plan view
    if 'PLAN-PIPE' in drawing_number or 'R5141' in drawing_number:
        return {
            'type': 'Plan',
            'subtype': 'Pipe and Equipment',
            'complexity': 'medium',
            'model': 'sonnet'
        }

    # Support Details - structural supports
    if 'SUPPORTS' in drawing_number or 'R5200' in drawing_number:
        return {
            'type': 'Details',
            'subtype': 'Supports',
            'complexity': 'low',
            'model': 'haiku'
        }

    return {
        'type': 'Unknown',
        'subtype': '',
        'complexity': 'medium',
        'model': 'sonnet'
    }

def build_extraction_prompt(drawing_class: Dict[str, str], drawing_number: str) -> str:
    """
    Build extraction prompt based on drawing classification.
    """
    if drawing_class['subtype'] == 'Pipe and Equipment':
        return f"""Extract all piping and equipment data from this refrigeration drawing ({drawing_number}).

For each PROCESS LINE visible, provide:
- Line number (format typically: SIZE-MATERIAL-NUMBER-SPEC or similar)
- Size (pipe diameter)
- Material (e.g., CS, SS, SCH40)
- Spec class if shown
- From equipment/location
- To equipment/location
- Insulation code if shown
- Any special notes

For each EQUIPMENT item, provide:
- Tag number
- Equipment type (e.g., vessel, tank, heat exchanger)
- Description/name if shown
- Location/elevation if shown

For each INSTRUMENT or VALVE, provide:
- Tag number
- Instrument type
- Associated equipment or line

For each NOTE or SPECIAL REQUIREMENT:
- Note text
- Reference location

Return as structured JSON with this format:
{{
  "lines": [
    {{
      "line_number": "...",
      "size": "...",
      "material": "...",
      "spec_class": "...",
      "from_location": "...",
      "to_location": "...",
      "insulation": "...",
      "notes": "...",
      "confidence": 0.0-1.0
    }}
  ],
  "equipment": [
    {{
      "tag": "...",
      "type": "...",
      "description": "...",
      "location": "...",
      "confidence": 0.0-1.0
    }}
  ],
  "instruments": [
    {{
      "tag": "...",
      "type": "...",
      "loop_number": "...",
      "confidence": 0.0-1.0
    }}
  ],
  "notes": [
    {{
      "text": "...",
      "location": "...",
      "confidence": 0.0-1.0
    }}
  ]
}}

Include a confidence score (0.0-1.0) for each item based on:
- Clear, readable text: +0.2
- Standard format: +0.1
- Partial/unclear text: -0.2
- Non-standard format: -0.1
Base confidence: 0.7
"""

    elif drawing_class['subtype'] == 'Supports':
        return f"""Extract all support and structural data from this refrigeration support details drawing ({drawing_number}).

For each SUPPORT detail shown:
- Support ID/mark
- Support type (e.g., pipe support, equipment support, anchor)
- Supported item (pipe line number or equipment tag)
- Material specification
- Size/dimensions
- Installation notes

For each PIPE SUPPORT:
- Mark/ID
- Pipe line number
- Support type
- Location/elevation

For each NOTE or SPECIFICATION:
- Note text
- Reference detail

Return as structured JSON:
{{
  "supports": [
    {{
      "mark": "...",
      "type": "...",
      "supported_item": "...",
      "material": "...",
      "size": "...",
      "notes": "...",
      "confidence": 0.0-1.0
    }}
  ],
  "notes": [
    {{
      "text": "...",
      "reference": "...",
      "confidence": 0.0-1.0
    }}
  ]
}}

Include confidence scores as described above.
"""

    else:
        return f"""Extract all relevant technical data from this refrigeration drawing ({drawing_number}).

Identify and extract:
- Equipment tags and descriptions
- Pipe line numbers and sizes
- Notes and specifications
- Any other technical information

Return as structured JSON with appropriate categories and confidence scores.
"""

def call_anthropic_vision(image_bytes: bytes, prompt: str, model: str = "sonnet") -> str:
    """Call Anthropic API with vision (image input)."""
    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    model_id = model_map.get(model, model)

    client = anthropic.Anthropic()

    # Encode image as base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    response = client.messages.create(
        model=model_id,
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    )

    return response.content[0].text

def call_anthropic_text(text: str, prompt: str, model: str = "sonnet") -> str:
    """Call Anthropic API with text input."""
    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    model_id = model_map.get(model, model)

    client = anthropic.Anthropic()

    full_prompt = f"{prompt}\n\n=== DRAWING TEXT ===\n{text}"

    response = client.messages.create(
        model=model_id,
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": full_prompt
        }]
    )

    return response.content[0].text

def parse_json_response(response: str) -> Dict[str, Any]:
    """Parse JSON from model response, handling markdown code blocks."""
    # Try to extract JSON from markdown code blocks
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        json_str = response[start:end].strip()
    else:
        json_str = response.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response: {response[:500]}")
        return {}

def extract_sheet(sheet_id: int, pdf_path: str, drawing_number: str) -> Dict[str, Any]:
    """
    Extract data from a single sheet.

    Returns:
        Extraction result with status, data, and metadata
    """
    print(f"\n{'='*60}")
    print(f"Extracting Sheet {sheet_id}: {drawing_number}")
    print(f"{'='*60}")

    pdf_path = Path(pdf_path)

    # Step 1: Extract content
    print("1. Extracting content from PDF...")
    text_content, image_bytes = extract_pdf_content(pdf_path)

    if image_bytes:
        print(f"   Image-based PDF ({len(image_bytes) / 1024 / 1024:.2f} MB)")
    else:
        print(f"   Text-based PDF ({len(text_content)} chars)")

    # Step 2: Classify drawing
    print("2. Classifying drawing type...")
    drawing_class = classify_drawing(sheet_id, drawing_number, text_content or "")
    print(f"   Type: {drawing_class['type']} - {drawing_class['subtype']}")
    print(f"   Complexity: {drawing_class['complexity']}")
    print(f"   Model: {drawing_class['model']}")

    # Step 3: Build extraction prompt
    print("3. Building extraction prompt...")
    prompt = build_extraction_prompt(drawing_class, drawing_number)

    # Step 4: Call model
    print(f"4. Calling {drawing_class['model']} model for extraction...")
    try:
        if image_bytes:
            response = call_anthropic_vision(image_bytes, prompt, drawing_class['model'])
        else:
            response = call_anthropic_text(text_content, prompt, drawing_class['model'])

        print(f"   Response received ({len(response)} chars)")
    except Exception as e:
        print(f"   ERROR: {e}")
        return {
            'sheet_id': sheet_id,
            'drawing_number': drawing_number,
            'status': 'failed',
            'error': str(e),
            'data': None
        }

    # Step 5: Parse response
    print("5. Parsing extraction response...")
    data = parse_json_response(response)

    if not data:
        print("   WARNING: Failed to parse JSON response")
        return {
            'sheet_id': sheet_id,
            'drawing_number': drawing_number,
            'status': 'failed',
            'error': 'JSON parse failure',
            'raw_response': response[:500],
            'data': None
        }

    # Step 6: Calculate summary statistics
    stats = {}
    for category in ['lines', 'equipment', 'instruments', 'supports', 'notes']:
        if category in data:
            items = data[category]
            count = len(items)
            if count > 0 and isinstance(items[0], dict) and 'confidence' in items[0]:
                avg_confidence = sum(item.get('confidence', 0.0) for item in items) / count
                stats[category] = {
                    'count': count,
                    'avg_confidence': round(avg_confidence, 2)
                }
            else:
                stats[category] = {'count': count}

    print("\n   Extraction Summary:")
    for category, info in stats.items():
        if 'avg_confidence' in info:
            print(f"   - {category.capitalize()}: {info['count']} (avg confidence: {info['avg_confidence']})")
        else:
            print(f"   - {category.capitalize()}: {info['count']}")

    return {
        'sheet_id': sheet_id,
        'drawing_number': drawing_number,
        'drawing_type': drawing_class['type'],
        'drawing_subtype': drawing_class['subtype'],
        'complexity': drawing_class['complexity'],
        'model_used': drawing_class['model'],
        'status': 'success',
        'data': data,
        'stats': stats
    }

def main():
    """Extract data from the three Freshpet sheets."""
    sheets = [
        (616, 'D:/qms/data/projects/07609-Freshpet/Refrigeration/R5101.1-REFRIGERATION-DETAILS-PIPE-AND-EQUIPMENT-Rev.1.pdf', 'R5101.1'),
        (617, 'D:/qms/data/projects/07609-Freshpet/Refrigeration/R5141.1-REFRIGERATION-PLAN-PIPE-AND-EQUIPMENT-FREEZER-FLOOR-HEAT-Rev.1.pdf', 'R5141.1'),
        (618, 'D:/qms/data/projects/07609-Freshpet/Refrigeration/R5200.1-REFRIGERATION-DETAILS-SUPPORTS-Rev.1.pdf', 'R5200.1')
    ]

    results = []

    for sheet_id, pdf_path, drawing_number in sheets:
        try:
            result = extract_sheet(sheet_id, pdf_path, drawing_number)
            results.append(result)
        except Exception as e:
            print(f"\n!!! FATAL ERROR for sheet {sheet_id}: {e}")
            results.append({
                'sheet_id': sheet_id,
                'drawing_number': drawing_number,
                'status': 'fatal_error',
                'error': str(e)
            })

    # Save results
    output_file = Path('D:/qms/data/extraction_results.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Results saved to: {output_file}")
    print(f"\nSummary:")
    for result in results:
        status = result['status']
        sheet_id = result['sheet_id']
        drawing = result['drawing_number']
        print(f"  Sheet {sheet_id} ({drawing}): {status}")

    return results

if __name__ == '__main__':
    main()
