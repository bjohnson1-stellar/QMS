"""Store E6002 unique equipment (skip receptacles already captured elsewhere)."""
from qms.pipeline.schedule_extractor import store_schedule_data

# E6002 (id=1383) - 240/208/120V circuit schedules
# Most unique equipment already stored from E6103/E6202/E6203/E6302/E6303
# Store only the sump pumps SP-1 through SP-4 with correct locations from this sheet
# (E6303 had them as "Space Heater" which was wrong - E6002 confirms they're sump pumps)
# Also store transformer tags with their feed relationships
e6002 = [
    {"tag": "SP-1", "equipment_type": "Sump Pump", "voltage": "120V", "panel_source": "3LG031", "description": "NEST RUN DOCK 1302"},
    {"tag": "SP-2", "equipment_type": "Sump Pump", "voltage": "120V", "panel_source": "3LG031", "description": "NEST RUN DOCK 1302"},
    {"tag": "SP-3", "equipment_type": "Sump Pump", "voltage": "120V", "panel_source": "3LG031", "description": "NEST RUN STORAGE 1301"},
    {"tag": "SP-4", "equipment_type": "Sump Pump", "voltage": "120V", "panel_source": "3LG031", "description": "NEST RUN DOCK 1302"},
]
stats = store_schedule_data(1383, 7, e6002, model_used="claude-sonnet-vision")
print(f"E6002 (1383): {stats}")

# Quick summary
from qms.pipeline.schedule_extractor import get_schedule_summary
summary = get_schedule_summary(7)
print(f"\nFinal summary:")
print(f"  Total schedule sheets: {summary['total_schedule_sheets']}")
print(f"  Extracted sheets: {summary['extracted_sheets']}")
print(f"  Pending sheets: {summary['pending_sheets']}")
print(f"  Total equipment entries: {summary['total_equipment_entries']}")
print(f"  By discipline:")
for d in summary['by_discipline']:
    print(f"    {d['discipline']}: {d['sheets']} sheets, {d['entries']} entries")
