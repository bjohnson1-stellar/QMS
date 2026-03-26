"""Store shadow review corrections — M6001 gap-fill from Opus shadow."""
from qms.pipeline.schedule_extractor import store_schedule_data, clear_schedule_data

# M6001 (id=1501) — Shadow found 60 equipment vs our 15 Docling entries
# Clear and re-store with comprehensive shadow data
cleared = clear_schedule_data(7, sheet_id=1501)
print(f"Cleared M6001: {cleared} entries removed")

m6001_shadow = [
    # HVLS Fans (15)
    {"tag": "HVLS-1", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-2", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-3", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-4", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-5", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-6", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-7", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-8", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-9", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-10", "equipment_type": "High Volume Low Speed Fan", "description": "PROCESSING 1501", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-11", "equipment_type": "High Volume Low Speed Fan", "description": "PALLET/TRAY STAGING 1504", "cfm": 55800, "hp": 0.3, "voltage": "115V", "weight_lbs": 99, "manufacturer": "Greenheck", "model_number": "DC-5-14"},
    {"tag": "HVLS-12", "equipment_type": "High Volume Low Speed Fan", "description": "NEST RUN STORAGE 1301", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-13", "equipment_type": "High Volume Low Speed Fan", "description": "NEST RUN STORAGE 1301", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-14", "equipment_type": "High Volume Low Speed Fan", "description": "NEST RUN STORAGE 1301", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    {"tag": "HVLS-15", "equipment_type": "High Volume Low Speed Fan", "description": "NEST RUN STORAGE 1301", "cfm": 110000, "hp": 0.8, "voltage": "480V", "weight_lbs": 170, "manufacturer": "Greenheck", "model_number": "DS-6-16"},
    # Exhaust Fans (13)
    {"tag": "EF-1", "equipment_type": "Exhaust Fan", "description": "BOILER ROOM", "cfm": 6500, "hp": 2, "voltage": "480V", "weight_lbs": 270, "manufacturer": "Greenheck", "model_number": "CUBE-240-VGD"},
    {"tag": "EF-2", "equipment_type": "Exhaust Fan", "description": "MAINTENANCE ECONOMIZER", "cfm": 25000, "hp": 7.5, "voltage": "480V", "weight_lbs": 709, "manufacturer": "Greenheck", "model_number": "RDU-48"},
    {"tag": "EF-3", "equipment_type": "Exhaust Fan", "description": "SOAP STORAGE", "cfm": 2100, "hp": 2, "voltage": "480V", "weight_lbs": 142, "manufacturer": "Greenheck", "model_number": "CUE-160XP-VG"},
    {"tag": "EF-4", "equipment_type": "Exhaust Fan", "description": "DRY GOODS WAREHOUSE", "cfm": 3800, "hp": 1, "voltage": "480V", "weight_lbs": 270, "manufacturer": "Greenheck", "model_number": "CUBE-240-VGD"},
    {"tag": "EF-5", "equipment_type": "Exhaust Fan", "description": "1225 MEN", "cfm": 625, "hp": 2, "voltage": "480V", "weight_lbs": 64, "manufacturer": "Greenheck", "model_number": "CUE-121-VG"},
    {"tag": "EF-6", "equipment_type": "Exhaust Fan", "description": "1215 WOMENS LOCKERS", "cfm": 975, "hp": 2, "voltage": "480V", "weight_lbs": 64, "manufacturer": "Greenheck", "model_number": "CUE-121-VG"},
    {"tag": "EF-7", "equipment_type": "Exhaust Fan", "description": "1231 OPEN OFFICE", "cfm": 10150, "hp": 5, "voltage": "480V", "weight_lbs": 468, "manufacturer": "Greenheck", "model_number": "CUBE-300-VGD"},
    {"tag": "EF-8", "equipment_type": "Exhaust Fan", "description": "EGG WASH 1202", "cfm": 8000, "hp": 2, "voltage": "460V", "weight_lbs": 305, "manufacturer": "Greenheck", "model_number": "USF-24"},
    {"tag": "EF-9", "equipment_type": "Exhaust Fan", "description": "EGG WASH 1503", "cfm": 8000, "hp": 2, "voltage": "460V", "weight_lbs": 305, "manufacturer": "Greenheck", "model_number": "USF-24"},
    {"tag": "EF-10", "equipment_type": "Exhaust Fan", "description": "TRUCKER AREA", "cfm": 600, "hp": 0.3, "voltage": "115V", "weight_lbs": 64, "manufacturer": "Greenheck", "model_number": "CUE-121-VG"},
    {"tag": "EF-11", "equipment_type": "Exhaust Fan", "description": "TRASH ROOM", "cfm": 125, "hp": 0.2, "voltage": "115V", "weight_lbs": 54, "manufacturer": "Greenheck", "model_number": "SE1-8-440-VG"},
    {"tag": "EF-12", "equipment_type": "Exhaust Fan", "description": "FIRE PUMP 1401", "cfm": 125, "hp": 0.2, "voltage": "115V", "weight_lbs": 54, "manufacturer": "Greenheck", "model_number": "SE1-8-440-VG"},
    {"tag": "EF-13", "equipment_type": "Exhaust Fan", "description": "BOILER ROOM", "cfm": 45000, "hp": 10, "voltage": "480V", "weight_lbs": 1294, "manufacturer": "Greenheck", "model_number": "RBCE-3H72-100"},
    # Louvers (4)
    {"tag": "L-1", "equipment_type": "Louver", "description": "AHU-1 & AHU-3 OUTDOOR AIR", "cfm": 12500, "manufacturer": "Greenheck", "model_number": "EDD-401"},
    {"tag": "L-2", "equipment_type": "Louver", "description": "AC-3 EXHAUST AIR", "cfm": 7060, "manufacturer": "Greenheck", "model_number": "EDD-401"},
    {"tag": "L-3", "equipment_type": "Louver", "description": "AC-2 EXHAUST AIR", "cfm": 7060, "manufacturer": "Greenheck", "model_number": "EDD-401"},
    {"tag": "L-4", "equipment_type": "Louver", "description": "BOILER ROOM OUTDOOR AIR", "cfm": 45000, "manufacturer": "Greenheck", "model_number": "EDD-401"},
    # Gravity Ventilators (9)
    {"tag": "GRE-1", "equipment_type": "Gravity Roof Exhaust", "description": "ERV-1", "cfm": 22000, "weight_lbs": 246, "manufacturer": "Greenheck", "model_number": "FGR-48X66"},
    {"tag": "GRE-2", "equipment_type": "Gravity Roof Exhaust", "description": "ERV-2", "cfm": 22000, "weight_lbs": 246, "manufacturer": "Greenheck", "model_number": "FGR-36X36"},
    {"tag": "GRE-3", "equipment_type": "Gravity Roof Exhaust", "description": "AHU-4", "cfm": 45000, "weight_lbs": 457, "manufacturer": "Greenheck", "model_number": "FGR-60X60"},
    {"tag": "GRE-4", "equipment_type": "Gravity Roof Exhaust", "description": "AHU-5", "cfm": 45000, "weight_lbs": 457, "manufacturer": "Greenheck", "model_number": "FGR-48X78"},
    {"tag": "GRE-5", "equipment_type": "Gravity Roof Exhaust", "description": "ERV-3", "cfm": 4400, "weight_lbs": 51, "manufacturer": "Greenheck", "model_number": "FGR-24X24"},
    {"tag": "GRI-1", "equipment_type": "Gravity Roof Intake", "description": "ERV-2", "cfm": 22000, "weight_lbs": 246, "manufacturer": "Greenheck", "model_number": "FGI-36X36"},
    {"tag": "GRI-2", "equipment_type": "Gravity Roof Intake", "description": "AHU-4", "cfm": 45000, "weight_lbs": 457, "manufacturer": "Greenheck", "model_number": "FGI-48X84"},
    {"tag": "GRI-3", "equipment_type": "Gravity Roof Intake", "description": "AHU-5", "cfm": 45000, "weight_lbs": 457, "manufacturer": "Greenheck", "model_number": "FGI-48X84"},
    {"tag": "GRI-4", "equipment_type": "Gravity Roof Intake", "description": "ERV-3", "cfm": 4400, "weight_lbs": 51, "manufacturer": "Greenheck", "model_number": "FGI-24X24"},
    # Trench Heaters (4)
    {"tag": "TH-1", "equipment_type": "Trench Heater", "description": "Vestibule 1242", "kva": 1, "voltage": "277/1/60", "manufacturer": "Berko", "model_number": "THX"},
    {"tag": "TH-2", "equipment_type": "Trench Heater", "description": "Vestibule 1242", "kva": 1, "voltage": "277/1/60", "manufacturer": "Berko", "model_number": "THX"},
    {"tag": "TH-3", "equipment_type": "Trench Heater", "description": "Vestibule 1242", "kva": 1, "voltage": "277/1/60", "manufacturer": "Berko", "model_number": "THX"},
    {"tag": "TH-4", "equipment_type": "Trench Heater", "description": "Vestibule 1242", "kva": 1, "voltage": "277/1/60", "manufacturer": "Berko", "model_number": "THX"},
    # Air Curtain (1)
    {"tag": "ACT-1", "equipment_type": "Air Curtain", "cfm": 6000, "hp": 1, "voltage": "115/1/60", "weight_lbs": 120, "manufacturer": "Mars Air", "model_number": "HV236-1UA-TS"},
    # Heaters (4)
    {"tag": "CUH-1", "equipment_type": "Cabinet Unit Heater", "description": "FIRE PUMP 1401", "kva": 1.5, "voltage": "120/1/60", "manufacturer": "Marley", "model_number": "ST06250"},
    {"tag": "CUH-2", "equipment_type": "Cabinet Unit Heater", "description": "TRUCKER'S LOUNGE 1308", "kva": 1.5, "voltage": "120/1/60", "manufacturer": "Marley", "model_number": "ST06250"},
    {"tag": "UH-1", "equipment_type": "Unit Heater", "description": "EQUIPMENT PLATFORM 2201", "kva": 5, "voltage": "480/3/60", "manufacturer": "Trane", "model_number": "UHEC-053DACA"},
    {"tag": "UH-2", "equipment_type": "Unit Heater", "description": "EQUIPMENT PLATFORM 2501", "kva": 5, "voltage": "480/3/60", "manufacturer": "Trane", "model_number": "UHEC-053DACA"},
    # RTUs (3)
    {"tag": "RTU-1", "equipment_type": "Rooftop Unit", "description": "TRUCKER AREA", "cfm": 2500, "voltage": "480/3/60", "weight_lbs": 1043, "manufacturer": "Trane", "model_number": "Precedent"},
    {"tag": "RTU-2", "equipment_type": "Rooftop Unit", "description": "EGG DRY 1201", "cfm": 2500, "voltage": "480/3/60", "weight_lbs": 1043, "manufacturer": "Trane", "model_number": "Precedent"},
    {"tag": "RTU-3", "equipment_type": "Rooftop Unit", "description": "EGG DRY 1502", "cfm": 2500, "voltage": "480/3/60", "weight_lbs": 1043, "manufacturer": "Trane", "model_number": "Precedent"},
    # CRACs + Condensers (4)
    {"tag": "CRAC-1", "equipment_type": "Computer Room AC", "description": "IT 1211", "cfm": 2750, "voltage": "480/3/60", "weight_lbs": 500, "manufacturer": "Liebert", "model_number": "MT060HE1A0S150MLBSP"},
    {"tag": "CRAC-2", "equipment_type": "Computer Room AC", "description": "IT 1211", "cfm": 2750, "voltage": "480/3/60", "weight_lbs": 500, "manufacturer": "Liebert", "model_number": "MT060HE1A0S150MLBSP"},
    {"tag": "ACCU-1", "equipment_type": "CRAC Condensing Unit", "description": "CRAC-1", "voltage": "480/3/60", "weight_lbs": 350, "manufacturer": "Liebert", "model_number": "PFD067A-AH1"},
    {"tag": "ACCU-2", "equipment_type": "CRAC Condensing Unit", "description": "CRAC-2", "voltage": "480/3/60", "weight_lbs": 350, "manufacturer": "Liebert", "model_number": "PFD067A-AH1"},
    # ERVs (3)
    {"tag": "ERV-1", "equipment_type": "Energy Recovery Ventilator", "cfm": 22000, "voltage": "480V"},
    {"tag": "ERV-2", "equipment_type": "Energy Recovery Ventilator", "cfm": 22000, "voltage": "480V"},
    {"tag": "ERV-3", "equipment_type": "Energy Recovery Ventilator", "cfm": 4400, "voltage": "480V"},
]

stats = store_schedule_data(1501, 7, m6001_shadow, model_used="claude-opus-shadow")
print(f"M6001 shadow fix (1501): {stats}")

# Final count
from qms.pipeline.schedule_extractor import get_schedule_summary
summary = get_schedule_summary(7)
print(f"\nPost-shadow summary:")
print(f"  Total entries: {summary['total_equipment_entries']}")
print(f"  Extracted sheets: {summary['extracted_sheets']}")
for d in summary['by_discipline']:
    print(f"  {d['discipline']}: {d['sheets']} sheets, {d['entries']} entries")
