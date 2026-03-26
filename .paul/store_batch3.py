"""Store vision extraction results - batch 3."""
from qms.pipeline.schedule_extractor import store_schedule_data

# M6003 (id=1505) - 7 AHUs with rich detail
m6003 = [
    {"tag": "AHU-1", "equipment_type": "Air Handling Unit", "description": "BOILER ROOM", "cfm": 6500, "hp": 7.5, "voltage": "480/3/60", "weight_lbs": 1540, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-2", "equipment_type": "Air Handling Unit", "description": "MAINTENANCE AREA", "cfm": 30000, "hp": 40, "voltage": "480/3/60", "weight_lbs": 11061, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-3", "equipment_type": "Air Handling Unit", "description": "DRY GOODS WAREHOUSE", "cfm": 3800, "hp": 3, "voltage": "480/3/60", "weight_lbs": 2200, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-4", "equipment_type": "Air Handling Unit", "description": "PROCESSING 1501", "cfm": 45000, "hp": 60, "voltage": "480/3/60", "weight_lbs": 20250, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-5", "equipment_type": "Air Handling Unit", "description": "PROCESSING 1501", "cfm": 45000, "hp": 60, "voltage": "480/3/60", "weight_lbs": 20250, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-6", "equipment_type": "Air Handling Unit", "description": "MAIN OFFICE (WEST)", "cfm": 7000, "hp": 10, "voltage": "480/3/60", "weight_lbs": 2277, "manufacturer": "TRANE", "model_number": "CSAA"},
    {"tag": "AHU-7", "equipment_type": "Air Handling Unit", "description": "MAIN OFFICE (EAST)", "cfm": 5000, "hp": 7, "voltage": "480/3/60", "weight_lbs": 1774, "manufacturer": "TRANE", "model_number": "CSAA"},
]
stats = store_schedule_data(1505, 7, m6003, model_used="claude-sonnet-vision")
print(f"M6003 (1505): {stats}")

# E6002 (id=1383) - Store unique equipment from circuit schedule
# E6002 results haven't come back yet - skip for now
# Will be handled in batch 4

# E6103 (id=1389) - Panels 1LG041 and 1LG051 + key circuit loads
e6103 = [
    {"tag": "1LG041", "equipment_type": "Lighting Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "1TG041"},
    {"tag": "1LG051", "equipment_type": "Lighting Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "1TG051"},
    {"tag": "CUH-1", "equipment_type": "Cabinet Unit Heater", "panel_source": "1LG041"},
    {"tag": "EF-12", "equipment_type": "Exhaust Fan", "panel_source": "1LG041"},
    {"tag": "HVLS-9", "equipment_type": "High Volume Low Speed Fan", "panel_source": "1LG051"},
]
stats = store_schedule_data(1389, 7, e6103, model_used="claude-sonnet-vision")
print(f"E6103 (1389): {stats}")

# E6202 (id=1393) - Key equipment from panel schedules Service 2
e6202 = [
    {"tag": "2HH012", "equipment_type": "Branch Panel", "voltage": "480V", "phase_count": 3, "amperage": 250, "panel_source": "2HH011"},
    {"tag": "2HH041", "equipment_type": "Branch Panel", "voltage": "480V", "phase_count": 3, "amperage": 400, "panel_source": "2HH011"},
    {"tag": "2LG041", "equipment_type": "Lighting Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 150, "panel_source": "2TG041"},
    {"tag": "2LG024", "equipment_type": "Lighting Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "2TG024"},
    {"tag": "FPB-2-1", "equipment_type": "Fan Powered Box", "panel_source": "2HH012"},
    {"tag": "FPB-2-3", "equipment_type": "Fan Powered Box", "panel_source": "2HH012"},
    {"tag": "FPB-2-4", "equipment_type": "Fan Powered Box", "panel_source": "2HH012"},
    {"tag": "FPB-2-5", "equipment_type": "Fan Powered Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-7", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-8", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-9", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-10", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-11", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "VAV-2-12", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH012"},
    {"tag": "TH-1", "equipment_type": "Terminal Heater", "panel_source": "2HH022"},
    {"tag": "TH-2", "equipment_type": "Terminal Heater", "panel_source": "2HH022"},
    {"tag": "TH-3", "equipment_type": "Terminal Heater", "panel_source": "2HH022"},
    {"tag": "TH-4", "equipment_type": "Terminal Heater", "panel_source": "2HH022"},
    {"tag": "VAV-5-1", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-5-2", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-5-3", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-5-4", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-5-5", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-5-6", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-1", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-2", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-3", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-4", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-5", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "VAV-4-6", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH022"},
    {"tag": "FPB-5-1", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-5-2", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-5-3", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-1", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-2", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-3", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-4", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-5", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-6", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-7", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-8", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "FPB-4-9", "equipment_type": "Fan Powered Box", "panel_source": "2HH022"},
    {"tag": "WEF-1", "equipment_type": "Wall Exhaust Fan", "panel_source": "2LG041"},
    {"tag": "EF-3", "equipment_type": "Exhaust Fan", "panel_source": "2LG041"},
]
stats = store_schedule_data(1393, 7, e6202, model_used="claude-sonnet-vision")
print(f"E6202 (1393): {stats}")

# E6203 (id=1395) - Key equipment from panel schedules Service 2
e6203 = [
    {"tag": "2LG011", "equipment_type": "Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 150, "panel_source": "2TG011"},
    {"tag": "2LG021", "equipment_type": "Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "2TG021"},
    {"tag": "2LG022", "equipment_type": "Panel", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "2TG022"},
    {"tag": "VAV-2-1", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "VAV-2-2", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "VAV-2-3", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "VAV-2-4", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "VAV-2-5", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "VAV-2-6", "equipment_type": "Variable Air Volume Box", "panel_source": "2HH011"},
    {"tag": "EF-5", "equipment_type": "Exhaust Fan", "panel_source": "2LG022"},
    {"tag": "EF-6", "equipment_type": "Exhaust Fan", "panel_source": "2LG022"},
    {"tag": "EF-11", "equipment_type": "Exhaust Fan", "panel_source": "2LG011"},
    {"tag": "IRH-1", "equipment_type": "Infrared Heater", "panel_source": "2LG011"},
    {"tag": "SP-5", "equipment_type": "Sump Pump", "panel_source": "2LG022"},
]
stats = store_schedule_data(1395, 7, e6203, model_used="claude-sonnet-vision")
print(f"E6203 (1395): {stats}")

# E6302 (id=1399) - Service 3 panel schedules - key unique equipment
e6302 = [
    {"tag": "3HH032", "equipment_type": "Panel", "voltage": "480V", "phase_count": 3, "amperage": 250, "panel_source": "3HH031"},
    {"tag": "HVLS-13", "equipment_type": "HVLS Fan", "panel_source": "3HH033"},
    {"tag": "HVLS-14", "equipment_type": "HVLS Fan", "panel_source": "3HH033"},
    {"tag": "HVLS-15", "equipment_type": "HVLS Fan", "panel_source": "3HH033"},
    {"tag": "HVLS-16", "equipment_type": "HVLS Fan", "panel_source": "3HH033"},
]
stats = store_schedule_data(1399, 7, e6302, model_used="claude-sonnet-vision")
print(f"E6302 (1399): {stats}")

# E6303 (id=1401) - Service 3 low-voltage panel - key equipment
e6303 = [
    {"tag": "3LG031", "equipment_type": "Panelboard", "voltage": "208/120V", "phase_count": 3, "amperage": 250, "panel_source": "3TG031"},
    {"tag": "EF-10", "equipment_type": "Exhaust Fan", "panel_source": "3LG031"},
    {"tag": "SP-1", "equipment_type": "Space Heater", "panel_source": "3LG031"},
    {"tag": "SP-2", "equipment_type": "Space Heater", "panel_source": "3LG031"},
    {"tag": "SP-3", "equipment_type": "Space Heater", "panel_source": "3LG031"},
    {"tag": "SP-4", "equipment_type": "Space Heater", "panel_source": "3LG031"},
    {"tag": "CHU-2", "equipment_type": "Cabinet Heater Unit", "panel_source": "3LG031"},
]
stats = store_schedule_data(1401, 7, e6303, model_used="claude-sonnet-vision")
print(f"E6303 (1401): {stats}")

print("\nBatch 3 complete")
