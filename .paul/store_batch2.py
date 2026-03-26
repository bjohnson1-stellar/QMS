"""Store vision extraction results - batch 2."""
import json
from qms.pipeline.schedule_extractor import store_schedule_data, clear_schedule_data

# U6001 (id=1714) - empty (pipe schedule only)
stats = store_schedule_data(1714, 7, [], model_used="claude-sonnet-vision")
print(f"U6001 (1714): {stats}")

# R6002 (id=1557) - valve schedule with RAHU P&ID references
# Store only unique data: RAHU-25 (not on R6001) + valve/refrigerant info
# Actually R6002 data is mostly TBD valves. The RAHU tags already exist from R6001.
# Store as empty — R6001 has the authoritative equipment data.
stats = store_schedule_data(1557, 7, [], model_used="claude-sonnet-vision")
print(f"R6002 (1557): {stats}")

# U6002-UTILITIES rev1 (id=2706) - 37 utility entries
# NOTE: U6002 rev.E (id=1715) already has 35 docling entries.
# Rev.1 has similar data. Store only entries NOT already in 1715.
# Actually, rev.1 is a DIFFERENT revision — may have different/additional items.
# The Docling entries on 1715 are from the .E rev. Rev.1 is separate sheet id 2706.
u6002_rev1 = [
    {"tag": "P-C1", "equipment_type": "Pump", "description": "Chilled Water Pump", "hp": 25, "voltage": "480/3/60", "manufacturer": "Taco", "model_number": "TA1030", "weight_lbs": 850},
    {"tag": "P-C2", "equipment_type": "Pump", "description": "Chilled Water Pump", "hp": 25, "voltage": "480/3/60", "manufacturer": "Taco", "model_number": "TA1030", "weight_lbs": 850},
    {"tag": "P-H1", "equipment_type": "Pump", "description": "Heating Water Pump", "hp": 50, "voltage": "480/3/60", "manufacturer": "Taco", "model_number": "TA1038", "weight_lbs": 850},
    {"tag": "P-H2", "equipment_type": "Pump", "description": "Heating Water Pump", "hp": 50, "voltage": "480/3/60", "manufacturer": "Taco", "model_number": "TA1038", "weight_lbs": 850},
    {"tag": "P-D1", "equipment_type": "Pump", "description": "Domestic Hot Water Pump", "hp": 20, "voltage": "480/3/60", "manufacturer": "Finish Thompson", "model_number": "AC8", "weight_lbs": 400},
    {"tag": "P-D2", "equipment_type": "Pump", "description": "Domestic Hot Water Pump", "hp": 20, "voltage": "480/3/60", "manufacturer": "Finish Thompson", "model_number": "AC8", "weight_lbs": 400},
    {"tag": "P-P1", "equipment_type": "Pump", "description": "Process Hot Water Pump", "hp": 20, "voltage": "480/3/60", "manufacturer": "Finish Thompson", "model_number": "AC8", "weight_lbs": 400},
    {"tag": "P-P2", "equipment_type": "Pump", "description": "Process Hot Water Pump", "hp": 20, "voltage": "480/3/60", "manufacturer": "Finish Thompson", "model_number": "AC8", "weight_lbs": 400},
    {"tag": "CH-1", "equipment_type": "Chiller", "description": "Air Cooled Chiller 375 Ton", "voltage": "460/3", "manufacturer": "Trane", "model_number": "ACR Series C", "weight_lbs": 24000},
    {"tag": "GWH-1", "equipment_type": "Gas Condensing Water Heater", "voltage": "480/3", "manufacturer": "Lochinvar", "model_number": "Armor AWH4000NPM", "weight_lbs": 4500},
    {"tag": "GWH-2", "equipment_type": "Gas Condensing Water Heater", "voltage": "480/3", "manufacturer": "Lochinvar", "model_number": "Armor AWH4000NPM", "weight_lbs": 4500},
    {"tag": "GWH-4", "equipment_type": "Gas Condensing Water Heater", "voltage": "120/1", "manufacturer": "Lochinvar", "model_number": "Armor AWH800NPM", "weight_lbs": 1000},
    {"tag": "GWH-5", "equipment_type": "Gas Condensing Water Heater", "voltage": "120/1", "manufacturer": "Lochinvar", "model_number": "Armor AWH800NPM", "weight_lbs": 1000},
    {"tag": "EWH-1", "equipment_type": "Electric Water Heater", "kva": 12, "voltage": "480/3", "manufacturer": "A.O. Smith", "model_number": "Dura-Power DEN-120", "weight_lbs": 1350},
    {"tag": "HWT-1", "equipment_type": "Hot Water Storage Tank", "manufacturer": "Lochinvar", "model_number": "TVG 2500J", "weight_lbs": 25000},
    {"tag": "AC-1", "equipment_type": "Air Compressor", "hp": 100, "voltage": "480/3/60", "manufacturer": "Sullair", "model_number": "DSP-7509AY", "weight_lbs": 4000},
    {"tag": "AC-2", "equipment_type": "Air Compressor", "hp": 100, "voltage": "480/3/60", "manufacturer": "Sullair", "model_number": "DSP-7509AY", "weight_lbs": 4000},
    {"tag": "AD-1", "equipment_type": "Compressed Air Dryer", "voltage": "480/3/60", "manufacturer": "Zeks", "model_number": "400HSF", "weight_lbs": 750},
    {"tag": "AD-2", "equipment_type": "Compressed Air Dryer", "voltage": "480/3/60", "manufacturer": "Zeks", "model_number": "400HSF", "weight_lbs": 750},
    {"tag": "CAR-1", "equipment_type": "Compressed Air Receiver Tank"},
    {"tag": "CAR-2", "equipment_type": "Compressed Air Receiver Tank"},
    {"tag": "ET-1", "equipment_type": "Expansion Tank", "manufacturer": "Grundfos", "model_number": "GNLA-35", "weight_lbs": 70},
    {"tag": "ET-2", "equipment_type": "Expansion Tank", "manufacturer": "Grundfos", "model_number": "GNLA-200", "weight_lbs": 650},
    {"tag": "ET-3", "equipment_type": "Expansion Tank", "manufacturer": "Grundfos", "model_number": "GFXA-300", "weight_lbs": 500},
    {"tag": "ET-4", "equipment_type": "Expansion Tank", "manufacturer": "Grundfos", "model_number": "GFXA-800L", "weight_lbs": 2300},
    {"tag": "WS-1", "equipment_type": "Water Softener System", "manufacturer": "Marlo", "model_number": "MHC-1200-3"},
    {"tag": "AS-1", "equipment_type": "Air Separator", "manufacturer": "Spirotherm", "model_number": "Spirovent VHT", "weight_lbs": 900},
    {"tag": "AS-2", "equipment_type": "Air Separator", "manufacturer": "Spirotherm", "model_number": "Spirovent VHT", "weight_lbs": 900},
    {"tag": "WPB-1", "equipment_type": "Booster Pump System", "hp": 7.5, "voltage": "460/3/60", "manufacturer": "Grundfos", "model_number": "Hydro MPC-E 3CRE 32-2-1", "weight_lbs": 1051},
    {"tag": "EWS-1", "equipment_type": "Emergency Eyewash/Shower", "manufacturer": "Guardian", "model_number": "G1994"},
    {"tag": "HB-1", "equipment_type": "Hose Bibb", "manufacturer": "Woodford", "model_number": "B65"},
    {"tag": "HB-2", "equipment_type": "Hose Bibb", "manufacturer": "Mifab", "model_number": "MHY-90"},
    {"tag": "HB-3", "equipment_type": "Hose Bibb", "manufacturer": "Mifab", "model_number": "MHY-65"},
    {"tag": "CP-1", "equipment_type": "Circulator Pump", "hp": 0.04, "voltage": "120/1", "manufacturer": "Taco", "model_number": "IL-008", "weight_lbs": 20},
    {"tag": "SA", "equipment_type": "Shock Arrestor", "manufacturer": "Zurn", "model_number": "Shoktrol Z1700"},
    {"tag": "RPBFP", "equipment_type": "Backflow Preventer", "manufacturer": "Watts", "model_number": "LF909NRS"},
    {"tag": "BFP-C", "equipment_type": "Backflow Preventer", "manufacturer": "Watts", "model_number": "SD-2"},
]
stats = store_schedule_data(2706, 7, u6002_rev1, model_used="claude-sonnet-vision")
print(f"U6002-rev1 (2706): {stats}")

# U6003 (id=1717) - additional utility items from combined U6001/U6002/U6003 extraction
# Store only items NOT already on U6002 sheets: boilers, HWT-2/3/4, flowmeters, shot feeders
u6003 = [
    {"tag": "B-1", "equipment_type": "Boiler", "description": "Closed Loop Heating Water Boiler", "voltage": "480/3", "manufacturer": "Lochinvar", "model_number": "Crest FB-4001", "weight_lbs": 6900},
    {"tag": "B-2", "equipment_type": "Boiler", "description": "Closed Loop Heating Water Boiler", "voltage": "480/3", "manufacturer": "Lochinvar", "model_number": "Crest FB-4001", "weight_lbs": 6900},
    {"tag": "HWT-2", "equipment_type": "Hot Water Storage Tank", "manufacturer": "Lochinvar", "model_number": "TVG 2500J", "weight_lbs": 25000},
    {"tag": "HWT-3", "equipment_type": "Hot Water Storage Tank", "manufacturer": "Lochinvar", "model_number": "TVG 2500J", "weight_lbs": 25000},
    {"tag": "HWT-4", "equipment_type": "Hot Water Storage Tank", "manufacturer": "Lochinvar", "model_number": "TVG 2500J", "weight_lbs": 25000},
    {"tag": "SF-1", "equipment_type": "Chemical Shot Feeder", "manufacturer": "Neptune", "model_number": "DBF-5", "weight_lbs": 80},
    {"tag": "SF-2", "equipment_type": "Chemical Shot Feeder", "manufacturer": "Neptune", "model_number": "DBF-5", "weight_lbs": 80},
    {"tag": "FM-W1", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W8", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W9", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W10", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W11", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W12", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-W13", "equipment_type": "Flowmeter", "manufacturer": "Siemens", "model_number": "MAG 5100W"},
    {"tag": "FM-C2", "equipment_type": "Flowmeter", "manufacturer": "Sage", "model_number": "Paramount 401"},
    {"tag": "FM-C3", "equipment_type": "Flowmeter", "manufacturer": "Sage", "model_number": "Paramount 401"},
]
stats = store_schedule_data(1717, 7, u6003, model_used="claude-sonnet-vision")
print(f"U6003 (1717): {stats}")

# E6001 (id=1381) - circuit schedule - panels + major equipment loads
# Focus on UNIQUE equipment tags not already captured by other electrical sheets
# Skip panels already captured by single-line diagrams (E6101/E6201/E6301)
# Store circuit-level loads that show equipment fed from specific panels
e6001_loads = [
    {"tag": "1SHATS", "equipment_type": "Automatic Transfer Switch", "voltage": "480/277V", "amperage": 4000, "phase_count": 3, "panel_source": "1TUTIL"},
    {"tag": "2SHATS", "equipment_type": "Automatic Transfer Switch", "voltage": "480/277V", "amperage": 4000, "phase_count": 3, "panel_source": "2TUTIL"},
    {"tag": "3HATS", "equipment_type": "Automatic Transfer Switch", "voltage": "480/277V", "amperage": 4000, "phase_count": 3, "panel_source": "3TUTIL"},
    # RCU sub-units from circuit schedule (A/B splits)
    {"tag": "RCU-13A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "1HH041", "circuit": "3"},
    {"tag": "RCU-13B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "1HH041", "circuit": "4"},
    {"tag": "RCU-1A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH021", "circuit": "1"},
    {"tag": "RCU-1B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH021", "circuit": "6"},
    {"tag": "RCU-2A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH021", "circuit": "2"},
    {"tag": "RCU-2B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH021", "circuit": "3"},
    {"tag": "RCU-3A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH021", "circuit": "4"},
    {"tag": "RCU-3B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH021", "circuit": "5"},
    {"tag": "RCU-4A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH033", "circuit": "4"},
    {"tag": "RCU-4B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH033", "circuit": "3"},
    {"tag": "RCU-5A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH031", "circuit": "3"},
    {"tag": "RCU-5B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH031", "circuit": "6"},
    {"tag": "RCU-6A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH033", "circuit": "1"},
    {"tag": "RCU-6B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH033", "circuit": "2"},
    {"tag": "RCU-7A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH031", "circuit": "5"},
    {"tag": "RCU-7B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH031", "circuit": "4"},
    {"tag": "RCU-8", "equipment_type": "Refrigeration Condensing Unit", "amperage": 86, "panel_source": "3HH031", "circuit": "7"},
    {"tag": "RCU-9A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH033", "circuit": "6"},
    {"tag": "RCU-9B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH033", "circuit": "7"},
    {"tag": "RCU-10A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH051", "circuit": "3"},
    {"tag": "RCU-10B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH051", "circuit": "4"},
    {"tag": "RCU-11A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH051", "circuit": "5"},
    {"tag": "RCU-11B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 224, "panel_source": "3HH051", "circuit": "6"},
    {"tag": "RCU-12A", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH051", "circuit": "1"},
    {"tag": "RCU-12B", "equipment_type": "Refrigeration Condensing Unit", "amperage": 155, "panel_source": "3HH051", "circuit": "2"},
    # HVAC equipment from circuit schedule
    {"tag": "AHU-1", "equipment_type": "Air Handling Unit", "amperage": 11, "panel_source": "2HH012"},
    {"tag": "AHU-2", "equipment_type": "Air Handling Unit", "amperage": 52, "panel_source": "2HH011"},
    {"tag": "AHU-3", "equipment_type": "Air Handling Unit", "amperage": 9, "panel_source": "2HH012"},
    {"tag": "AHU-4", "equipment_type": "Air Handling Unit", "amperage": 145, "panel_source": "2HH011"},
    {"tag": "AHU-5", "equipment_type": "Air Handling Unit", "amperage": 145, "panel_source": "2HH011"},
    {"tag": "AHU-6", "equipment_type": "Air Handling Unit", "amperage": 11, "panel_source": "2HH022"},
    {"tag": "AHU-7", "equipment_type": "Air Handling Unit", "amperage": 11, "panel_source": "2HH022"},
    {"tag": "ERV-1", "equipment_type": "Energy Recovery Ventilator", "amperage": 71, "panel_source": "2HH011"},
    {"tag": "ERV-2", "equipment_type": "Energy Recovery Ventilator", "amperage": 71, "panel_source": "2HH011"},
    {"tag": "ERV-3", "equipment_type": "Energy Recovery Ventilator", "amperage": 10, "panel_source": "2HH022"},
    {"tag": "CRAC-1", "equipment_type": "Computer Room Air Conditioner", "amperage": 20, "panel_source": "2HH022"},
    {"tag": "CRAC-2", "equipment_type": "Computer Room Air Conditioner", "amperage": 20, "panel_source": "2HH011"},
    {"tag": "EF-1", "equipment_type": "Exhaust Fan", "amperage": 3, "panel_source": "1HMCC041"},
    {"tag": "EF-2", "equipment_type": "Exhaust Fan", "amperage": 11, "panel_source": "1HMCC041"},
    {"tag": "EF-4", "equipment_type": "Exhaust Fan", "amperage": 2, "panel_source": "1HMCC041"},
    {"tag": "EF-8", "equipment_type": "Exhaust Fan", "amperage": 3, "panel_source": "1HMCC041"},
    {"tag": "EF-9", "equipment_type": "Exhaust Fan", "amperage": 3, "panel_source": "1HMCC041"},
    {"tag": "EF-13", "equipment_type": "Exhaust Fan", "amperage": 14, "panel_source": "1HMCC041"},
    {"tag": "RTU-1", "equipment_type": "Rooftop Unit", "amperage": 26, "panel_source": "3HH031"},
    {"tag": "RTU-2", "equipment_type": "Rooftop Unit", "amperage": 26, "panel_source": "2HH021"},
    {"tag": "RTU-3", "equipment_type": "Rooftop Unit", "amperage": 26, "panel_source": "1HH051"},
    {"tag": "UH-1", "equipment_type": "Unit Heater", "amperage": 6, "panel_source": "2HH021"},
    {"tag": "UH-2", "equipment_type": "Unit Heater", "amperage": 6, "panel_source": "1HH051"},
    {"tag": "ACCU-1", "equipment_type": "Accumulator", "amperage": 13, "panel_source": "2HH022"},
    {"tag": "ACCU-2", "equipment_type": "Accumulator", "amperage": 13, "panel_source": "1HH042"},
    {"tag": "JOCKEY PUMP", "equipment_type": "Motor", "amperage": 8, "panel_source": "1HH041"},
]
stats = store_schedule_data(1381, 7, e6001_loads, model_used="claude-sonnet-vision")
print(f"E6001 (1381): {stats}")

print("\nBatch 2 complete")
