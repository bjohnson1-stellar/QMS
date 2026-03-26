"""Store vision extraction results - batch 4 (P6001)."""
from qms.pipeline.schedule_extractor import store_schedule_data, clear_schedule_data

# P6001 (id=1521) - 25 plumbing fixtures + 1 pump
# Clear the 2 docling entries first, then store complete vision extraction
clear_schedule_data(7, sheet_id=1521)
print("Cleared existing P6001 docling entries")

p6001 = [
    {"tag": "EWC-1", "equipment_type": "Electric Water Cooler", "manufacturer": "Elkay", "model_number": "EZS8L"},
    {"tag": "EWC-2", "equipment_type": "Electric Water Cooler / Bottle Filling Station", "manufacturer": "Elkay", "model_number": "LZS8WSLP"},
    {"tag": "FCO-1", "equipment_type": "Floor Cleanout", "manufacturer": "Zurn", "model_number": "ZN1400-DC"},
    {"tag": "FCO-2", "equipment_type": "Floor Cleanout", "manufacturer": "Zurn", "model_number": "Z1840-6B"},
    {"tag": "FCO-3", "equipment_type": "Floor Cleanout", "manufacturer": "Zurn", "model_number": "ZN1400-HD"},
    {"tag": "FD-1", "equipment_type": "Floor Drain", "manufacturer": "Zurn", "model_number": "SDCS-CUSTOM"},
    {"tag": "FD-2", "equipment_type": "Floor Drain", "manufacturer": "Zurn", "model_number": "Z415NZ"},
    {"tag": "FD-3", "equipment_type": "Floor Drain", "manufacturer": "Zurn", "model_number": "Z415-BZ1"},
    {"tag": "FD-4", "equipment_type": "Floor Drain", "manufacturer": "Zurn", "model_number": "Z508"},
    {"tag": "HD-1", "equipment_type": "Hub Drain", "manufacturer": "Zurn", "model_number": "Z1870"},
    {"tag": "HD-2", "equipment_type": "Hub Drain", "manufacturer": "Zurn", "model_number": "Z1870-6-4NH"},
    {"tag": "S-1", "equipment_type": "Wash Station", "manufacturer": "Bradley Corp.", "model_number": "ELX-2"},
    {"tag": "S-2", "equipment_type": "Wash Basin", "manufacturer": "Bradley Corp.", "model_number": "GLX-1"},
    {"tag": "S-3", "equipment_type": "Wash Station", "manufacturer": "Columbia Products Sani-Lav", "model_number": "58W0"},
    {"tag": "S-4", "equipment_type": "Sink", "manufacturer": "Elkay", "model_number": "LR33221"},
    {"tag": "S-5", "equipment_type": "Sink", "manufacturer": "Elkay", "model_number": "LR-1722"},
    {"tag": "S-6", "equipment_type": "Sink", "manufacturer": "Elkay", "model_number": "EHS-18-KVX"},
    {"tag": "S-7", "equipment_type": "Lavatory", "manufacturer": "Bradley Corp.", "model_number": "TLX-4"},
    {"tag": "S-8", "equipment_type": "Sink", "manufacturer": "Elkay", "model_number": "EWMA48202"},
    {"tag": "SHWR", "equipment_type": "Shower", "manufacturer": "Delta", "model_number": "RPW324HDF-1.5"},
    {"tag": "UR-1", "equipment_type": "Urinal", "manufacturer": "American Standard", "model_number": "Washbrook 6501.610"},
    {"tag": "WC-1", "equipment_type": "Water Closet", "manufacturer": "American Standard", "model_number": "Afwall 2257.103"},
    {"tag": "MS-1", "equipment_type": "Mop Basin", "manufacturer": "Fiat", "model_number": "TSBC-6010"},
    {"tag": "FS-1", "equipment_type": "Floor Sink", "manufacturer": "Kusel", "model_number": "FS4-061-181816-0"},
    {"tag": "P-1", "equipment_type": "Sump Pump", "hp": 0.25, "voltage": "115/1", "manufacturer": "Liberty", "model_number": "247", "weight_lbs": 21},
]
stats = store_schedule_data(1521, 7, p6001, model_used="claude-sonnet-vision")
print(f"P6001 (1521): {stats}")
print("Batch 4 complete")
