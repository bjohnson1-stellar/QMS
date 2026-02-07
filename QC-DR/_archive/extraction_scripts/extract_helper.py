"""
Helper script to extract data from a single PDF and return as JSON.
This will be called by Claude Code with the PDF content.
"""
import sys
import json

def parse_extraction_response(response_text):
    """Parse the extraction response and return structured JSON"""
    # Try to find JSON in the response
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    else:
        json_text = response_text

    try:
        data = json.loads(json_text)
        return data
    except json.JSONDecodeError:
        print(f"Warning: Could not parse JSON", file=sys.stderr)
        return {
            "drawing_info": {"drawing_type": "refrigeration_plan", "complexity": "unknown", "quality_score": 0.5},
            "lines": [],
            "equipment": [],
            "instruments": []
        }

if __name__ == '__main__':
    # Read extraction response from stdin
    response_text = sys.stdin.read()
    data = parse_extraction_response(response_text)
    print(json.dumps(data, indent=2))
