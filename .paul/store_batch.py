"""Store vision extraction results for completed agents."""
import json
from qms.pipeline.schedule_extractor import store_schedule_data

# M6004 (id=1507) - empty (ventilation calculations)
stats = store_schedule_data(1507, 7, [], model_used="claude-sonnet-vision")
print(f"M6004 (1507): {stats}")

# E6101 (id=1385) - single-line diagram Service 1
e6101 = [
    {"tag": "1TUTIL", "equipment_type": "Transformer", "kva": 2500, "voltage": "12470V to 480/277V", "phase_count": 3},
    {"tag": "1HMSB", "equipment_type": "Switchboard", "voltage": "480/277V", "amperage": 3000, "phase_count": 3, "panel_source": "1TUTIL via ATS"},
    {"tag": "ATS-1", "equipment_type": "Automatic Transfer Switch", "amperage": 3000, "phase_count": 3, "panel_source": "1TUTIL"},
    {"tag": "1HH041", "equipment_type": "Distribution Panel", "voltage": "480V", "amperage": 800, "panel_source": "1HMSB"},
    {"tag": "1HH051", "equipment_type": "Distribution Panel", "voltage": "480V", "amperage": 600, "panel_source": "1HMSB"},
    {"tag": "1HP051", "equipment_type": "Distribution Panel", "voltage": "480V", "amperage": 1200, "panel_source": "1HMSB"},
    {"tag": "1HP052", "equipment_type": "Distribution Panel", "voltage": "480V", "amperage": 1200, "panel_source": "1HMSB"},
    {"tag": "1HMCC041", "equipment_type": "MCC", "voltage": "480V", "amperage": 600, "panel_source": "1HH041"},
    {"tag": "1HL041", "equipment_type": "Lighting Panel", "voltage": "480/277V", "amperage": 250, "panel_source": "1HH041"},
    {"tag": "1HH042", "equipment_type": "Distribution Panel", "voltage": "480V", "amperage": 250, "panel_source": "1HH041"},
    {"tag": "1HL051", "equipment_type": "Lighting Panel", "voltage": "480/277V", "amperage": 250, "panel_source": "1HH051"},
    {"tag": "1TG041", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "1HH041"},
    {"tag": "1LG041", "equipment_type": "Distribution Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "1TG041"},
    {"tag": "1TG051", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "1HH051"},
    {"tag": "1LG051", "equipment_type": "Distribution Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "1TG051"},
    {"tag": "AC-1", "equipment_type": "Motor", "voltage": "480V", "hp": 100, "panel_source": "1HP051"},
    {"tag": "CH-1", "equipment_type": "Motor Load", "voltage": "480V", "panel_source": "1HP051"},
    {"tag": "1HH041-GEN", "equipment_type": "Generator Distribution", "kva": 2500, "voltage": "480V"},
]
stats = store_schedule_data(1385, 7, e6101, model_used="claude-sonnet-vision")
print(f"E6101 (1385): {stats}")

# E6201 (id=1391) - single-line diagram Service 2
e6201 = [
    {"tag": "2TUTIL", "equipment_type": "Transformer", "kva": 2500, "voltage": "12470V to 480/277V", "phase_count": 3},
    {"tag": "2HMSB", "equipment_type": "Main Switchboard", "voltage": "480/277V", "amperage": 3000, "phase_count": 3, "panel_source": "2TUTIL"},
    {"tag": "2GEN1", "equipment_type": "Generator", "kva": 2500, "voltage": "480/277V", "phase_count": 3},
    {"tag": "ATS-2", "equipment_type": "Automatic Transfer Switch", "voltage": "480V", "amperage": 3000, "panel_source": "2HMSB / 2GEN1"},
    {"tag": "2HP021", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "2HMSB"},
    {"tag": "2HP041", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "2HMSB"},
    {"tag": "2HH011", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "2HMSB"},
    {"tag": "2HH012", "equipment_type": "Panel", "voltage": "480V", "amperage": 250, "panel_source": "2HMSB"},
    {"tag": "2HH021", "equipment_type": "Panel", "voltage": "480/277V", "amperage": 600, "panel_source": "2HP021"},
    {"tag": "2HH022", "equipment_type": "Panel", "voltage": "480/277V", "amperage": 600, "panel_source": "2HMSB"},
    {"tag": "2HH041", "equipment_type": "Panel", "voltage": "480V", "amperage": 400, "panel_source": "2HP041"},
    {"tag": "2HL022", "equipment_type": "Panel", "voltage": "480/277V", "amperage": 250, "panel_source": "2HH022"},
    {"tag": "2TG021", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "2HP021"},
    {"tag": "2LG021", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "2TG021"},
    {"tag": "2TG022", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "2HH021"},
    {"tag": "2LG022", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "2TG022"},
    {"tag": "2TG024", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "2HH022"},
    {"tag": "2LG024", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "2TG024"},
    {"tag": "2TG011", "equipment_type": "Transformer", "kva": 45, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "2HH011"},
    {"tag": "2LG011", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 150, "panel_source": "2TG011"},
    {"tag": "2TG041", "equipment_type": "Transformer", "kva": 45, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "2HH041"},
    {"tag": "2LG041", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 150, "panel_source": "2TG041"},
    {"tag": "AC-2", "equipment_type": "Motor", "voltage": "480V", "hp": 100, "panel_source": "2HP021"},
]
stats = store_schedule_data(1391, 7, e6201, model_used="claude-sonnet-vision")
print(f"E6201 (1391): {stats}")

# E6301 (id=1397) - single-line diagram Service 3
e6301 = [
    {"tag": "3TUTIL", "equipment_type": "Transformer", "kva": 2500, "voltage": "12470V to 480/277V", "phase_count": 3},
    {"tag": "3HMSB", "equipment_type": "Main Switchboard", "voltage": "480/277V", "amperage": 3000, "phase_count": 3},
    {"tag": "3GEN1", "equipment_type": "Generator", "kva": 2500, "voltage": "480/277V", "phase_count": 3, "panel_source": "3HMSB"},
    {"tag": "3HH051", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "3HMSB"},
    {"tag": "3HH031", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "3HMSB"},
    {"tag": "3HH033", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "3HMSB"},
    {"tag": "3HH032", "equipment_type": "Panel", "voltage": "480V", "amperage": 250, "panel_source": "3HMSB"},
    {"tag": "3HH021", "equipment_type": "Panel", "voltage": "480V", "amperage": 1200, "panel_source": "3HMSB"},
    {"tag": "3HL031", "equipment_type": "Lighting Panel", "voltage": "480/277V", "amperage": 250, "panel_source": "3HMSB"},
    {"tag": "3HP031", "equipment_type": "Power Panel", "voltage": "480V", "amperage": 1200, "panel_source": "3HMSB"},
    {"tag": "3TG031", "equipment_type": "Transformer", "kva": 75, "voltage": "480V to 208/120V", "phase_count": 3, "panel_source": "3HH031"},
    {"tag": "3LG031", "equipment_type": "Panel", "voltage": "208/120V", "amperage": 250, "panel_source": "3TG031"},
]
stats = store_schedule_data(1397, 7, e6301, model_used="claude-sonnet-vision")
print(f"E6301 (1397): {stats}")

# R6001 (id=1556) - 44 refrigeration entries (13 RCU + 31 RAHU)
r6001 = [
    {"tag": "RCU-1", "equipment_type": "Condensing Unit", "description": "NEST RUN STORAGE", "manufacturer": "CENTURY", "model_number": "NDF90M4C", "hp": 50, "voltage": "460/3/60", "weight_lbs": 6500},
    {"tag": "RCU-2", "equipment_type": "Condensing Unit", "description": "NEST RUN STORAGE", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-3", "equipment_type": "Condensing Unit", "description": "NEST RUN STORAGE", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-4", "equipment_type": "Condensing Unit", "description": "NEST RUN STORAGE", "manufacturer": "CENTURY", "model_number": "NDF90M4C", "hp": 50, "voltage": "460/3/60", "weight_lbs": 6500},
    {"tag": "RCU-5", "equipment_type": "Condensing Unit", "description": "NEST RUN STORAGE", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-6", "equipment_type": "Condensing Unit", "description": "NEST RUN DOCK", "manufacturer": "CENTURY", "model_number": "NDF90M4C", "hp": 50, "voltage": "460/3/60", "weight_lbs": 6500},
    {"tag": "RCU-7", "equipment_type": "Condensing Unit", "description": "FINISHED GOODS DOCK", "manufacturer": "CENTURY", "model_number": "NDF90M4C", "hp": 50, "voltage": "460/3/60", "weight_lbs": 6500},
    {"tag": "RCU-8", "equipment_type": "Condensing Unit", "description": "FINISHED GOODS", "manufacturer": "CENTURY", "model_number": "NSF35M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 2500},
    {"tag": "RCU-9", "equipment_type": "Condensing Unit", "description": "FINISHED GOODS", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-10", "equipment_type": "Condensing Unit", "description": "FINISHED GOODS", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-11", "equipment_type": "Condensing Unit", "description": "FINISHED GOODS", "manufacturer": "CENTURY", "model_number": "NDF90M4C", "hp": 50, "voltage": "460/3/60", "weight_lbs": 6500},
    {"tag": "RCU-12", "equipment_type": "Condensing Unit", "description": "PALLET STORAGE", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
    {"tag": "RCU-13", "equipment_type": "Condensing Unit", "description": "PALLET STORAGE", "manufacturer": "CENTURY", "model_number": "NDF70M4C", "hp": 35, "voltage": "460/3/60", "weight_lbs": 4750},
]

# RAHUs 1-26 (skip 25) - BOC434C model
for i in range(1, 27):
    if i == 25:
        continue
    areas = {
        range(1, 13): "NEST RUN STORAGE",
        range(13, 16): "NEST RUN DOCK",
        range(16, 19): "FINISHED GOODS DOCK",
        range(19, 27): "FINISHED GOODS",
    }
    desc = "NEST RUN STORAGE"
    for rng, area in areas.items():
        if i in rng:
            desc = area
            break
    r6001.append({
        "tag": f"RAHU-{i}", "equipment_type": "Air Handling Unit",
        "description": desc, "manufacturer": "CENTURY",
        "model_number": "BOC434C-1216M-E", "hp": 1, "voltage": "460/3/60",
        "weight_lbs": 1300,
    })

# RAHUs 27-29 - BALV554C model (pallet storage)
for i in range(27, 30):
    r6001.append({
        "tag": f"RAHU-{i}", "equipment_type": "Air Handling Unit",
        "description": "PALLET STORAGE", "manufacturer": "CENTURY",
        "model_number": "BALV554C-983M", "hp": 0.25, "voltage": "460/3/60",
        "weight_lbs": 1350,
    })

# RAHUs 30-31 - BOC434C model (pallet storage)
for i in range(30, 32):
    r6001.append({
        "tag": f"RAHU-{i}", "equipment_type": "Air Handling Unit",
        "description": "PALLET STORAGE", "manufacturer": "CENTURY",
        "model_number": "BOC434C-1216M-E", "hp": 1, "voltage": "460/3/60",
        "weight_lbs": 1300,
    })

stats = store_schedule_data(1556, 7, r6001, model_used="claude-sonnet-vision")
print(f"R6001 (1556): {stats}")

print(f"\nTotal R6001 entries submitted: {len(r6001)}")
