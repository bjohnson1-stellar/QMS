"""Store vision extraction results - batch 5 (E6102)."""
from qms.pipeline.schedule_extractor import store_schedule_data

# E6102 (id=1387) - Service 1 panel schedules - store unique equipment
# Focus on panels + named equipment loads (skip lighting circuits, spares, spaces)
e6102 = [
    # Panels (with kVA data)
    {"tag": "1HH042", "equipment_type": "Distribution Panel", "voltage": "480V", "phase_count": 3, "amperage": 250, "panel_source": "1HH041", "kva": 50},
    {"tag": "1HL051", "equipment_type": "Lighting Panel", "voltage": "480/277V", "phase_count": 3, "amperage": 250, "panel_source": "1HL041"},
    # MCC motor loads with HP and starter types
    {"tag": "EF-4", "equipment_type": "Exhaust Fan", "hp": 1, "panel_source": "1HMCC041", "circuit": "1"},
    {"tag": "EF-1", "equipment_type": "Exhaust Fan", "hp": 2, "panel_source": "1HMCC041", "circuit": "3"},
    {"tag": "EF-2", "equipment_type": "Exhaust Fan", "hp": 7.5, "panel_source": "1HMCC041", "circuit": "4"},
    {"tag": "P-D1", "equipment_type": "Pump", "hp": 20, "panel_source": "1HMCC041", "circuit": "5"},
    {"tag": "P-D2", "equipment_type": "Pump", "hp": 20, "panel_source": "1HMCC041", "circuit": "6"},
    {"tag": "P-P1", "equipment_type": "Pump", "hp": 20, "panel_source": "1HMCC041", "circuit": "7"},
    {"tag": "P-P2", "equipment_type": "Pump", "hp": 20, "panel_source": "1HMCC041", "circuit": "8"},
    {"tag": "P-H2", "equipment_type": "Pump", "hp": 50, "panel_source": "1HMCC041", "circuit": "9"},
    {"tag": "P-H1", "equipment_type": "Pump", "hp": 50, "panel_source": "1HMCC041", "circuit": "10"},
    {"tag": "P-C2", "equipment_type": "Pump", "hp": 25, "panel_source": "1HMCC041", "circuit": "11"},
    {"tag": "P-C1", "equipment_type": "Pump", "hp": 25, "panel_source": "1HMCC041", "circuit": "12"},
    {"tag": "EF-8", "equipment_type": "Exhaust Fan", "hp": 2, "panel_source": "1HMCC041", "circuit": "13"},
    {"tag": "EF-9", "equipment_type": "Exhaust Fan", "hp": 2, "panel_source": "1HMCC041", "circuit": "14"},
    {"tag": "EF-13", "equipment_type": "Exhaust Fan", "hp": 10, "panel_source": "1HMCC041", "circuit": "15"},
    # Other named equipment
    {"tag": "HVLS-3", "equipment_type": "HVLS Fan", "panel_source": "1HH051"},
    {"tag": "HVLS-4", "equipment_type": "HVLS Fan", "panel_source": "1HH051"},
    {"tag": "HVLS-8", "equipment_type": "HVLS Fan", "panel_source": "1HH051"},
    {"tag": "HVLS-10", "equipment_type": "HVLS Fan", "panel_source": "1HH051"},
    {"tag": "JIB CRANE", "equipment_type": "Crane", "panel_source": "1HH051"},
]
stats = store_schedule_data(1387, 7, e6102, model_used="claude-sonnet-vision")
print(f"E6102 (1387): {stats}")

# E6002 hasn't returned yet - store empty placeholder to not block
# Will update if it returns
print("Batch 5 complete")
