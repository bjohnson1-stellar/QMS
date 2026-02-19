"""
Direct extraction of Freshpet refrigeration drawings R7005, R7006, R7006A.
Data extracted via visual analysis of PDFs.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Extracted data from R7005.1-REFRIGERATION-P&ID-Rev.1.pdf
R7005_DATA = {
    "lines": [
        # Hot suction discharge lines to condensers
        {"line_number": "10\"-HSD-CS22-CU5157", "size": "10\"", "material": "CS", "spec_class": "22", "service": "Hot Suction Discharge", "from_location": "Compressor Units", "to_location": "Condensers RE:PID-3410", "refrigerant": "NH3", "confidence": 0.95},

        # Relief valve lines
        {"line_number": "1\"-RV-CS22-CU5143", "size": "1\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "from_location": "PSV", "to_location": "Vent Header", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "1\"-RV-CS22-CU5147", "size": "1\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "from_location": "PSV", "to_location": "Vent Header", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "1\"-RV-CS22-CU5151", "size": "1\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "from_location": "PSV", "to_location": "Vent Header", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "1\"-RV-CS22-CU5155", "size": "1\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "from_location": "PSV", "to_location": "Vent Header", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "5\"-RV-CS22-CU5156", "size": "5\"", "material": "CS", "spec_class": "22", "service": "Relief Valve Header", "from_location": "Branch lines", "to_location": "Vent Header RE:PID-3466", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3/4\"-RV-CS22-CU5144", "size": "3/4\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "confidence": 0.90},
        {"line_number": "3/4\"-RV-CS22-CU5148", "size": "3/4\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "confidence": 0.90},
        {"line_number": "3/4\"-RV-CS22-CU5152", "size": "3/4\"", "material": "CS", "spec_class": "22", "service": "Relief Valve", "confidence": 0.90},

        # Temperature suction lines
        {"line_number": "3\"-TSS-CS22-CU5173", "size": "3\"", "material": "CS", "spec_class": "22", "service": "Temperature Suction", "from_location": "Various", "to_location": "CU-HSC-003 RE:PID-3422", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "4\"-TSR-CS22-CU0316", "size": "4\"", "material": "CS", "spec_class": "22", "service": "Temperature Suction Return", "from_location": "CU-HSC-003 RE:PID-3422", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3\"-TSS-CS22-CU5159", "size": "3\"", "material": "CS", "spec_class": "22", "service": "Temperature Suction", "to_location": "CU-HSC-004 RE:PID-3423", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "4\"-TSR-CS22-CU0320", "size": "4\"", "material": "CS", "spec_class": "22", "service": "Temperature Suction Return", "from_location": "CU-HSC-004 RE:PID-3423", "refrigerant": "NH3", "confidence": 0.95},

        # Hot suction lines
        {"line_number": "8\"-HSS-CS22-CU5172-P3", "size": "8\"", "material": "CS", "spec_class": "22", "service": "Hot Suction", "to_location": "CU-HSC-003 RE:PID-3422", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "6\"-HSD-CS22-CU0319", "size": "6\"", "material": "CS", "spec_class": "22", "service": "Hot Suction Discharge", "from_location": "CU-HSC-003 RE:PID-3422", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "8\"-HSS-CS22-CU5160-P3", "size": "8\"", "material": "CS", "spec_class": "22", "service": "Hot Suction", "to_location": "CU-HSC-004 RE:PID-3423", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "6\"-HSD-CS22-CU0323", "size": "6\"", "material": "CS", "spec_class": "22", "service": "Hot Suction Discharge", "from_location": "CU-HSC-004 RE:PID-3423", "refrigerant": "NH3", "confidence": 0.95},

        # Equalizer lines
        {"line_number": "2\"-ES-CS22-CU5171-P3", "size": "2\"", "material": "CS", "spec_class": "22", "service": "Equalizer", "to_location": "CU-HSC-003 RE:PID-3422", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "2\"-ES-CS22-CU5161-P3", "size": "2\"", "material": "CS", "spec_class": "22", "service": "Equalizer", "to_location": "CU-HSC-004 RE:PID-3423", "refrigerant": "NH3", "confidence": 0.95},

        # Cross-reference to R7006
        {"line_number": "10\"HSD-CS300 84-1002", "size": "10\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "from_location": "R7006", "refrigerant": "NH3", "confidence": 0.90},
        {"line_number": "4\"TSR-CS300 66-1001", "size": "4\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction Return", "from_location": "CU-HSC-009 R-7006C", "refrigerant": "NH3", "confidence": 0.90},
        {"line_number": "4\"TSR-CS300 66-1000", "size": "4\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction Return", "from_location": "CU-HSC-010 R-7006C", "refrigerant": "NH3", "confidence": 0.90},
        {"line_number": "3\"TSS-CS300 67-1001", "size": "3\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction", "to_location": "CU-HSC-009 R-7006C", "refrigerant": "NH3", "confidence": 0.90},
        {"line_number": "3\"TSS-CS300 67-1000", "size": "3\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction", "to_location": "CU-HSC-010 R-7006C", "refrigerant": "NH3", "confidence": 0.90},
    ],
    "equipment": [],
    "instruments": [
        # Pressure safety valves
        {"tag": "PSV-CU004", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU005", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU006", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU007", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU008", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU009", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},
        {"tag": "PSV-CU010", "instrument_type": "Pressure Safety Valve", "service": "300 PSIG SET", "description": "1/2\" Relief to vent header", "confidence": 0.95},

        # Flow indicators with switches
        {"tag": "FI-CU004", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU004", "confidence": 0.95},
        {"tag": "FS-CU004", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU004", "confidence": 0.95},
        {"tag": "FI-CU005", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU005", "confidence": 0.95},
        {"tag": "FS-CU005", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU005", "confidence": 0.95},
        {"tag": "FI-CU006", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU006", "confidence": 0.95},
        {"tag": "FS-CU006", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU006", "confidence": 0.95},
        {"tag": "FI-CU007", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU007", "confidence": 0.95},
        {"tag": "FS-CU007", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU007", "confidence": 0.95},
        {"tag": "FI-CU008", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU008", "confidence": 0.95},
        {"tag": "FS-CU008", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU008", "confidence": 0.95},
        {"tag": "FI-CU009", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU009", "confidence": 0.95},
        {"tag": "FS-CU009", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU009", "confidence": 0.95},
        {"tag": "FI-CU010", "instrument_type": "Flow Indicator", "service": "24VDC", "description": "With flow switch FS-CU010", "confidence": 0.95},
        {"tag": "FS-CU010", "instrument_type": "Flow Switch", "service": "ZSC/O", "description": "Associated with FI-CU010", "confidence": 0.95},
    ]
}

# Extracted data from R7006.1-REFRIGERATION-P&ID-Rev.1.pdf
R7006_DATA = {
    "lines": [
        # Main headers
        {"line_number": "10\"HSD-CS300 84-1002", "size": "10\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "8\"MSS-CS300 55-1001", "size": "8\"", "material": "CS", "spec_class": "300", "service": "Main Suction", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "8\"MSS-CS300 55-1002", "size": "8\"", "material": "CS", "spec_class": "300", "service": "Main Suction", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "16\"MSS-CS300 55-1000", "size": "16\"", "material": "CS", "spec_class": "300", "service": "Main Suction", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "6\"HSD-CS300 84-1001", "size": "6\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "6\"HSD-CS300 84-1000", "size": "6\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "8\"HSD-CS300 84-1004", "size": "8\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "8\"HSD-CS300 84-1003", "size": "8\"", "material": "CS", "spec_class": "300", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.95},

        # Temperature suction lines
        {"line_number": "3\"TSS-CS300 67-1000", "size": "3\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3\"TSS-CS300 67-1001", "size": "3\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "4\"TSR-CS300 66-1001", "size": "4\"", "material": "CS", "spec_class": "300", "service": "Temperature Suction Return", "refrigerant": "NH3", "confidence": 0.95},

        # Relief valve lines
        {"line_number": "2\"RV-CS300 91-1000", "size": "2\"", "material": "CS", "spec_class": "300", "service": "Relief Valve", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "2\"RV-CS300 91-1001", "size": "2\"", "material": "CS", "spec_class": "300", "service": "Relief Valve", "refrigerant": "NH3", "confidence": 0.95},

        # Equalizer and purge lines
        {"line_number": "3\"ES-CS300 32-1002", "size": "3\"", "material": "CS", "spec_class": "300", "service": "Equalizer", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "6\"ES-CS300 32-1001", "size": "6\"", "material": "CS", "spec_class": "300", "service": "Equalizer", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3/4\"PRG-CS300 85-1000", "size": "3/4\"", "material": "CS", "spec_class": "300", "service": "Purge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3/4\"PRG-CS300 85-1001", "size": "3/4\"", "material": "CS", "spec_class": "300", "service": "Purge", "refrigerant": "NH3", "confidence": 0.95},
        {"line_number": "3/4\"PRG-CS300 85-1002", "size": "3/4\"", "material": "CS", "spec_class": "300", "service": "Purge", "refrigerant": "NH3", "confidence": 0.95},

        # Cooling water lines
        {"line_number": "16\"CRWR-PPR160 22-1000", "size": "16\"", "material": "PPR", "spec_class": "160", "service": "Cooling Water Return", "confidence": 0.95},
        {"line_number": "8\"CRWS-PPR160 23-1000", "size": "8\"", "material": "PPR", "spec_class": "160", "service": "Cooling Water Supply", "confidence": 0.95},
        {"line_number": "12\"CD-CS300 61-1000", "size": "12\"", "material": "CS", "spec_class": "300", "service": "Condensate Drain", "confidence": 0.95},
    ],
    "equipment": [
        {"tag": "CU-HSC-007", "equipment_type": "Compressor Unit - Hot Suction Compressor", "description": "NH3 compressor with oil separator and motor", "confidence": 0.95},
        {"tag": "CU-HSC-008", "equipment_type": "Compressor Unit - Hot Suction Compressor", "description": "NH3 compressor with oil separator and motor", "confidence": 0.95},
        {"tag": "CU-EC-005A", "equipment_type": "Evaporative Condenser", "description": "NH3 evaporative condenser unit A", "confidence": 0.95},
        {"tag": "CU-EC-005B", "equipment_type": "Evaporative Condenser", "description": "NH3 evaporative condenser unit B", "confidence": 0.95},
    ],
    "instruments": [
        # Compressor instrumentation for CU-HSC-007
        {"tag": "PI4 CU-HSC-007", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "HV1 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV3 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV5 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV7 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV20 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV21 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV22 CU-HSC-007", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV8 CU-HSC-007", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV9 CU-HSC-007", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV23 CU-HSC-007", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV6 CU-HSC-007", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "STR2 CU-HSC-007", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},
        {"tag": "STR18 CU-HSC-007", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},

        # Compressor instrumentation for CU-HSC-008
        {"tag": "PI4 CU-HSC-008", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "PI15 CU-HSC-008", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "HV1 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV3 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV5 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV7 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV10 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV14 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV16 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV19 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV20 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV21 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV22 CU-HSC-008", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV8 CU-HSC-008", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV9 CU-HSC-008", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "PSV23 CU-HSC-008", "instrument_type": "Pressure Safety Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV6 CU-HSC-008", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV13 CU-HSC-008", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV17 CU-HSC-008", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "STR2 CU-HSC-008", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},
        {"tag": "STR18 CU-HSC-008", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},

        # Condenser instrumentation for CU-EC-005A
        {"tag": "PI10 CU-EC-005A", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "HV1 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV3 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV4 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV5 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV8 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV9 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV11 CU-EC-005A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV2 CU-EC-005A", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV7 CU-EC-005A", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "STR6 CU-EC-005A", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},

        # Condenser instrumentation for CU-EC-005B
        {"tag": "PI10 CU-EC-005B", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "PI14 CU-EC-005B", "instrument_type": "Pressure Indicator", "service": "H2O", "confidence": 0.90},
        {"tag": "PI19 CU-EC-005B", "instrument_type": "Pressure Indicator", "service": "NH3", "confidence": 0.90},
        {"tag": "HV1 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV3 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV4 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV5 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV8 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV9 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV11 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV12 CU-EC-005B", "instrument_type": "Hand Valve", "service": "H2O", "confidence": 0.90},
        {"tag": "HV13 CU-EC-005B", "instrument_type": "Hand Valve", "service": "H2O", "confidence": 0.90},
        {"tag": "HV15 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV16 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV18 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV22 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV24 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV25 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV27 CU-EC-005B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV2 CU-EC-005B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV7 CU-EC-005B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV17 CU-EC-005B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV23 CU-EC-005B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "STR6 CU-EC-005B", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},
        {"tag": "STR20 CU-EC-005B", "instrument_type": "Strainer", "service": "NH3", "confidence": 0.90},
    ]
}

# Extracted data from R7006A.1-REFRIGERATION-PLAN-Rev.1.pdf
R7006A_DATA = {
    "lines": [
        # Lines visible on plan
        {"line_number": "8\" HSD", "size": "8\"", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.85},
        {"line_number": "6\" HSD", "size": "6\"", "service": "Hot Suction Discharge", "refrigerant": "NH3", "confidence": 0.85},
        {"line_number": "4\" CD", "size": "4\"", "service": "Condensate Drain", "confidence": 0.85},
    ],
    "equipment": [
        {"tag": "CU-EC-007A", "equipment_type": "Evaporative Condenser", "description": "NH3 evaporative condenser unit 007A with valves", "confidence": 0.95},
        {"tag": "CU-EC-007B", "equipment_type": "Evaporative Condenser", "description": "NH3 evaporative condenser unit 007B with valves", "confidence": 0.95},
    ],
    "instruments": [
        # Condenser 007A valves
        {"tag": "HV1 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV2 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV8 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV9 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV10 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV11 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV12 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV13 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV14 CU-EC-007A", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV1 CU-EC-007A", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV7 CU-EC-007A", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},

        # Condenser 007B valves
        {"tag": "HV1 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV2 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV3 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV4 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV6 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV8 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV9 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV10 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV11 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV12 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV13 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV14 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV15 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV16 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV17 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "HV18 CU-EC-007B", "instrument_type": "Hand Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV1 CU-EC-007B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV2 CU-EC-007B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
        {"tag": "CV5 CU-EC-007B", "instrument_type": "Control Valve", "service": "NH3", "description": "Locked open", "confidence": 0.90},
        {"tag": "CV7 CU-EC-007B", "instrument_type": "Control Valve", "service": "NH3", "confidence": 0.90},
    ]
}


def save_to_database(sheet_id: int, extraction_data: dict, db_path: Path, model_used: str, drawing_number: str) -> tuple:
    """Save extracted data to database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Save lines
    lines_inserted = 0
    for line in extraction_data.get("lines", []):
        try:
            cursor.execute("""
                INSERT INTO lines (sheet_id, line_number, size, material, spec_class,
                                  refrigerant, service, from_location, to_location, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                line.get("line_number", "UNKNOWN"),
                line.get("size"),
                line.get("material"),
                line.get("spec_class"),
                line.get("refrigerant"),
                line.get("service"),
                line.get("from_location"),
                line.get("to_location"),
                line.get("confidence", 0.7)
            ))
            lines_inserted += 1
        except Exception as e:
            print(f"  Warning: Could not insert line {line.get('line_number')}: {e}")

    # Save equipment
    equipment_inserted = 0
    for equip in extraction_data.get("equipment", []):
        try:
            cursor.execute("""
                INSERT INTO equipment (sheet_id, tag, description, equipment_type, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sheet_id,
                equip.get("tag", "UNKNOWN"),
                equip.get("description"),
                equip.get("equipment_type"),
                equip.get("confidence", 0.7)
            ))
            equipment_inserted += 1
        except Exception as e:
            print(f"  Warning: Could not insert equipment {equip.get('tag')}: {e}")

    # Save instruments
    instruments_inserted = 0
    for inst in extraction_data.get("instruments", []):
        try:
            cursor.execute("""
                INSERT INTO instruments (sheet_id, tag, instrument_type, service,
                                        loop_number, description, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sheet_id,
                inst.get("tag", "UNKNOWN"),
                inst.get("instrument_type"),
                inst.get("service"),
                inst.get("loop_number"),
                inst.get("description"),
                inst.get("confidence", 0.7)
            ))
            instruments_inserted += 1
        except Exception as e:
            print(f"  Warning: Could not insert instrument {inst.get('tag')}: {e}")

    # Calculate quality score
    all_items = (
        extraction_data.get("lines", []) +
        extraction_data.get("equipment", []) +
        extraction_data.get("instruments", [])
    )
    if all_items:
        quality_score = sum(item.get("confidence", 0.7) for item in all_items) / len(all_items)
    else:
        quality_score = 0.0

    # Update sheet status
    cursor.execute("""
        UPDATE sheets
        SET extracted_at = ?,
            extraction_model = ?,
            quality_score = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), model_used, quality_score, sheet_id))

    conn.commit()
    conn.close()

    return lines_inserted, equipment_inserted, instruments_inserted, quality_score


def main():
    """Main extraction script."""

    db_path = Path("data/quality.db")

    print("=" * 80)
    print("Freshpet Refrigeration Drawing Extraction")
    print("=" * 80)
    print("Project: 07609-Freshpet")
    print("Extraction Method: Direct visual analysis")
    print("Database: {}".format(db_path))
    print()

    sheets = [
        (634, "R7005.1", R7005_DATA, "P&ID"),
        (635, "R7006.1", R7006_DATA, "P&ID"),
        (636, "R7006A.1", R7006A_DATA, "Plan"),
    ]

    results = []

    for sheet_id, drawing_number, data, drawing_type in sheets:
        print(f"\nProcessing Sheet {sheet_id}: {drawing_number} ({drawing_type})")
        print("-" * 80)

        try:
            lines_count, equipment_count, instruments_count, quality = save_to_database(
                sheet_id, data, db_path, "sonnet", drawing_number
            )

            result = {
                "sheet_id": sheet_id,
                "drawing_number": drawing_number,
                "status": "success",
                "lines_extracted": lines_count,
                "equipment_extracted": equipment_count,
                "instruments_extracted": instruments_count,
                "quality_score": quality,
                "total_items": lines_count + equipment_count + instruments_count
            }

            print(f"  Lines: {lines_count}")
            print(f"  Equipment: {equipment_count}")
            print(f"  Instruments: {instruments_count}")
            print(f"  Quality Score: {quality:.2f}")
            print(f"  Status: SUCCESS")

            results.append(result)

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "sheet_id": sheet_id,
                "drawing_number": drawing_number,
                "status": "failed",
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    total_lines = sum(r.get("lines_extracted", 0) for r in results)
    total_equipment = sum(r.get("equipment_extracted", 0) for r in results)
    total_instruments = sum(r.get("instruments_extracted", 0) for r in results)

    for result in results:
        status = "SUCCESS" if result["status"] == "success" else "FAILED"
        print(f"\n{result['drawing_number']}: {status}")
        if result["status"] == "success":
            print(f"  Lines: {result['lines_extracted']}")
            print(f"  Equipment: {result['equipment_extracted']}")
            print(f"  Instruments: {result['instruments_extracted']}")
            print(f"  Quality: {result['quality_score']:.2f}")
        else:
            print(f"  Error: {result.get('error', 'Unknown')}")

    print(f"\nTotal Extracted Across All Sheets:")
    print(f"  Lines: {total_lines}")
    print(f"  Equipment: {total_equipment}")
    print(f"  Instruments: {total_instruments}")
    print(f"  Total Items: {total_lines + total_equipment + total_instruments}")
    print()


if __name__ == "__main__":
    main()
