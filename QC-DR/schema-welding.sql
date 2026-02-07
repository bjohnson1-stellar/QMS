-- ============================================================================
-- WELDING PROGRAM MODULE - COMPLETE SCHEMA
-- ============================================================================
-- Supports: WPS, PQR, WPQ, BPS, BPQ, BPQR, Welder Registry, Continuity
-- ASME Section IX / AWS D1.1 compliant field structure
--
-- Created: 2026-02-05
-- ============================================================================

-- ============================================================================
-- 1. WELDER REGISTRY
-- ============================================================================
-- Master list of all welders/brazers with identification and status

CREATE TABLE IF NOT EXISTS weld_welder_registry (
    id INTEGER PRIMARY KEY,
    employee_number TEXT UNIQUE NOT NULL,          -- Company ID
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    middle_initial TEXT,

    -- Identification
    welder_stamp TEXT UNIQUE,                      -- Unique stamp mark
    ssn_last_four TEXT,                            -- Last 4 SSN for verification

    -- Employment
    hire_date DATE,
    termination_date DATE,
    status TEXT DEFAULT 'active',                  -- active, inactive, terminated
    department TEXT,
    supervisor TEXT,

    -- Contact
    email TEXT,
    phone TEXT,

    -- File paths (relative to Welder-Records/{employee_number}/)
    photo_path TEXT,                               -- photo.jpg
    signature_path TEXT,                           -- signature.png

    -- Notes
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_welder_stamp ON weld_welder_registry(welder_stamp);
CREATE INDEX IF NOT EXISTS idx_welder_status ON weld_welder_registry(status);
CREATE INDEX IF NOT EXISTS idx_welder_name ON weld_welder_registry(last_name, first_name);

-- ============================================================================
-- 2. WPS TABLES (Welding Procedure Specifications)
-- ============================================================================
-- QW-482 form structure - normalized for searchability

-- 2.1 WPS Header
CREATE TABLE IF NOT EXISTS weld_wps (
    id INTEGER PRIMARY KEY,
    wps_number TEXT UNIQUE NOT NULL,               -- WPS-001, AWS-B2.1-001, etc.
    revision TEXT DEFAULT '0',
    revision_date DATE,

    -- Type flags
    is_swps INTEGER DEFAULT 0,                     -- Standard WPS (pre-qualified, no PQR needed)
    swps_document_number TEXT,                     -- AWS B2.1 document reference

    -- Description
    title TEXT,
    description TEXT,

    -- Applicability
    applicable_codes TEXT,                         -- ASME IX, AWS D1.1, etc. (comma-separated)
    scope_of_work TEXT,                            -- What joints/applications this covers

    -- Status
    status TEXT DEFAULT 'draft',                   -- draft, active, superseded, void
    effective_date DATE,
    superseded_date DATE,
    superseded_by TEXT,                            -- WPS number that replaces this

    -- Approval
    prepared_by TEXT,
    prepared_date DATE,
    reviewed_by TEXT,
    reviewed_date DATE,
    approved_by TEXT,
    approved_date DATE,

    -- File reference
    file_path TEXT,                                -- Path to PDF

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_wps_number ON weld_wps(wps_number);
CREATE INDEX IF NOT EXISTS idx_wps_status ON weld_wps(status);
CREATE INDEX IF NOT EXISTS idx_wps_is_swps ON weld_wps(is_swps);

-- 2.2 WPS Welding Processes (multiple per WPS)
CREATE TABLE IF NOT EXISTS weld_wps_processes (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,            -- 1=root, 2=fill, 3=cap, etc.

    -- Process identification (QW-401)
    process_type TEXT NOT NULL,                    -- SMAW, GTAW, GMAW, FCAW, SAW, etc.
    process_variation TEXT,                        -- Manual, Semi-Auto, Auto, Machine

    -- Layer application
    layer_deposit TEXT,                            -- root, fill, cap, all

    UNIQUE(wps_id, process_sequence)
);

CREATE INDEX IF NOT EXISTS idx_wps_process_type ON weld_wps_processes(process_type);

-- 2.3 WPS Joint Design (QW-402)
CREATE TABLE IF NOT EXISTS weld_wps_joints (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,

    joint_type TEXT,                               -- Butt, Corner, Tee, Lap, Edge
    groove_type TEXT,                              -- V, U, J, Bevel, Square
    groove_angle_min REAL,
    groove_angle_max REAL,
    root_opening_min REAL,
    root_opening_max REAL,
    root_face_min REAL,
    root_face_max REAL,

    backing_type TEXT,                             -- None, Metal, Non-fusible, Consumable Insert
    backing_material TEXT,

    retainers TEXT,                                -- None, Copper, Ceramic, etc.

    -- Sketches stored as JSON array of descriptions or file paths
    joint_details_json TEXT
);

-- 2.4 WPS Base Metals (QW-403)
CREATE TABLE IF NOT EXISTS weld_wps_base_metals (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,              -- For dissimilar metal joints

    -- P-number grouping
    p_number INTEGER,
    group_number INTEGER,

    -- Actual specification
    material_spec TEXT,                            -- SA-516, A106, etc.
    material_grade TEXT,                           -- Gr.70, Gr.B, etc.
    material_type TEXT,                            -- Plate, Pipe, Fitting

    -- Thickness range qualified
    thickness_min REAL,
    thickness_max REAL,
    thickness_unit TEXT DEFAULT 'in',

    -- Diameter range (for pipe)
    diameter_min REAL,
    diameter_max REAL,
    diameter_unit TEXT DEFAULT 'in',

    -- S-number (if applicable)
    s_number INTEGER
);

CREATE INDEX IF NOT EXISTS idx_wps_base_metal_p ON weld_wps_base_metals(p_number, group_number);

-- 2.5 WPS Filler Metals (QW-404)
CREATE TABLE IF NOT EXISTS weld_wps_filler_metals (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,            -- Links to process

    -- F-number and A-number
    f_number INTEGER,
    a_number INTEGER,

    -- Specification
    sfa_spec TEXT,                                 -- SFA-5.1, SFA-5.18, etc.
    aws_class TEXT,                                -- E7018, ER70S-6, etc.

    -- Filler details
    filler_diameter TEXT,                          -- Can be range: "3/32 - 1/8"
    filler_form TEXT,                              -- Solid, Cored, Flux-Cored

    -- Flux (for SAW, ESW)
    flux_trade_name TEXT,
    flux_type TEXT,                                -- Active, Neutral
    flux_class TEXT,

    -- Consumable insert
    consumable_insert TEXT,
    insert_class TEXT,

    -- Supplementary filler
    supplementary_filler TEXT,
    powder_or_wire TEXT
);

CREATE INDEX IF NOT EXISTS idx_wps_filler_f ON weld_wps_filler_metals(f_number);
CREATE INDEX IF NOT EXISTS idx_wps_filler_a ON weld_wps_filler_metals(a_number);

-- 2.6 WPS Positions (QW-405)
CREATE TABLE IF NOT EXISTS weld_wps_positions (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,

    -- Groove positions
    groove_positions TEXT,                         -- 1G, 2G, 3G, 4G, 5G, 6G (comma-separated)

    -- Fillet positions
    fillet_positions TEXT,                         -- 1F, 2F, 3F, 4F, 5F (comma-separated)

    -- Progression
    progression TEXT,                              -- Uphill, Downhill, Either

    -- Notes
    position_notes TEXT
);

-- 2.7 WPS Preheat (QW-406)
CREATE TABLE IF NOT EXISTS weld_wps_preheat (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,

    preheat_temp_min REAL,
    preheat_temp_max REAL,
    temp_unit TEXT DEFAULT 'F',

    interpass_temp_max REAL,

    preheat_maintenance TEXT,                      -- Required during welding?

    -- Method
    preheat_method TEXT,                           -- Torch, Furnace, Induction, Resistance

    notes TEXT
);

-- 2.8 WPS PWHT (QW-407)
CREATE TABLE IF NOT EXISTS weld_wps_pwht (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,

    pwht_required INTEGER DEFAULT 0,

    temperature_min REAL,
    temperature_max REAL,
    temp_unit TEXT DEFAULT 'F',

    time_min REAL,                                 -- Hours at temperature
    time_max REAL,

    heating_rate_max REAL,                         -- Degrees per hour
    cooling_rate_max REAL,

    -- Method
    pwht_method TEXT,                              -- Furnace, Local, etc.

    -- Exemptions
    pwht_exemption TEXT,                           -- Code paragraph reference if exempt

    notes TEXT
);

-- 2.9 WPS Gas (QW-408)
CREATE TABLE IF NOT EXISTS weld_wps_gas (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,

    -- Shielding gas
    shielding_gas TEXT,                            -- Ar, CO2, 75Ar/25CO2, etc.
    shielding_flow_rate_min REAL,
    shielding_flow_rate_max REAL,
    flow_rate_unit TEXT DEFAULT 'CFH',

    -- Backing/trailing gas
    backing_gas TEXT,
    backing_flow_rate_min REAL,
    backing_flow_rate_max REAL,

    -- Trailing gas (for titanium, etc.)
    trailing_gas TEXT,
    trailing_flow_rate REAL
);

-- 2.10 WPS Electrical Parameters (QW-409)
CREATE TABLE IF NOT EXISTS weld_wps_electrical_params (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    pass_type TEXT,                                -- root, fill, cap, or specific pass numbers

    -- Current
    current_type TEXT,                             -- AC, DCEP, DCEN, Pulsed
    amperage_min REAL,
    amperage_max REAL,

    -- Voltage
    voltage_min REAL,
    voltage_max REAL,

    -- Travel speed
    travel_speed_min REAL,
    travel_speed_max REAL,
    travel_speed_unit TEXT DEFAULT 'in/min',

    -- Wire feed (for GMAW, FCAW, SAW)
    wire_feed_speed_min REAL,
    wire_feed_speed_max REAL,
    wire_feed_unit TEXT DEFAULT 'in/min',

    -- Heat input
    heat_input_min REAL,
    heat_input_max REAL,
    heat_input_unit TEXT DEFAULT 'kJ/in',

    -- Pulsing parameters (JSON for complex data)
    pulsing_params_json TEXT,

    -- Arc characteristics
    transfer_mode TEXT,                            -- Short-circuit, Globular, Spray, Pulsed-Spray

    notes TEXT
);

-- 2.11 WPS Technique (QW-410)
CREATE TABLE IF NOT EXISTS weld_wps_technique (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,

    -- Stringer vs weave
    bead_type TEXT,                                -- Stringer, Weave, Either
    weave_amplitude_max REAL,

    -- Layer info
    single_or_multi_pass TEXT,                     -- Single, Multi
    single_or_multi_layer TEXT,                    -- Single, Multi

    -- Electrode handling
    electrode_angle_min REAL,
    electrode_angle_max REAL,

    -- Cleaning
    interpass_cleaning TEXT,                       -- Wire brush, Grinding, None
    root_cleaning TEXT,

    -- Peening
    peening TEXT,                                  -- None, Hammer, Needle

    -- Contact tip to work distance (GMAW)
    ctwd_min REAL,
    ctwd_max REAL,

    -- Multiple electrodes
    multiple_electrodes INTEGER DEFAULT 0,
    electrode_spacing REAL,

    -- Oscillation (JSON for complex parameters)
    oscillation_json TEXT,

    -- Other technique details
    technique_details_json TEXT
);

-- 2.12 WPS Supporting PQRs
CREATE TABLE IF NOT EXISTS weld_wps_pqr_links (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    pqr_id INTEGER REFERENCES weld_pqr(id),
    pqr_number TEXT,                               -- For external PQR references

    -- What this PQR qualifies
    qualification_scope TEXT,                      -- What variables this PQR supports

    UNIQUE(wps_id, pqr_id)
);

-- ============================================================================
-- 3. PQR TABLES (Procedure Qualification Records)
-- ============================================================================
-- QW-483 form structure

-- 3.1 PQR Header
CREATE TABLE IF NOT EXISTS weld_pqr (
    id INTEGER PRIMARY KEY,
    pqr_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',

    -- Related WPS
    wps_number TEXT,                               -- WPS this qualifies

    -- Test coupon info
    coupon_id TEXT,
    test_date DATE,

    -- Witness
    witness_name TEXT,
    witness_company TEXT,
    witness_stamp TEXT,

    -- Laboratory
    lab_name TEXT,
    lab_report_number TEXT,

    -- Status
    status TEXT DEFAULT 'active',                  -- active, superseded, void

    -- Approval
    prepared_by TEXT,
    prepared_date DATE,
    reviewed_by TEXT,
    reviewed_date DATE,

    -- File reference
    file_path TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pqr_number ON weld_pqr(pqr_number);
CREATE INDEX IF NOT EXISTS idx_pqr_wps ON weld_pqr(wps_number);

-- 3.2 PQR Joint Design
CREATE TABLE IF NOT EXISTS weld_pqr_joints (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    joint_type TEXT,
    groove_type TEXT,
    groove_angle REAL,
    root_opening REAL,
    root_face REAL,
    backing_type TEXT,
    backing_material TEXT,

    -- Actual dimensions used
    actual_dimensions_json TEXT
);

-- 3.3 PQR Base Metals
CREATE TABLE IF NOT EXISTS weld_pqr_base_metals (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,

    p_number INTEGER,
    group_number INTEGER,
    material_spec TEXT,
    material_grade TEXT,

    -- Actual coupon dimensions
    thickness REAL,
    diameter REAL,                                 -- For pipe

    -- Heat/lot info
    heat_number TEXT,
    lot_number TEXT
);

CREATE INDEX IF NOT EXISTS idx_pqr_base_metal_p ON weld_pqr_base_metals(p_number, group_number);

-- 3.4 PQR Filler Metals
CREATE TABLE IF NOT EXISTS weld_pqr_filler_metals (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,

    f_number INTEGER,
    a_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,

    -- Actual filler used
    filler_diameter TEXT,
    trade_name TEXT,
    heat_lot TEXT,

    -- Flux
    flux_trade_name TEXT,
    flux_lot TEXT
);

CREATE INDEX IF NOT EXISTS idx_pqr_filler_f ON weld_pqr_filler_metals(f_number);

-- 3.5 PQR Positions
CREATE TABLE IF NOT EXISTS weld_pqr_positions (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    test_position TEXT,                            -- Position welded: 1G, 2G, etc.
    progression TEXT                               -- Uphill, Downhill
);

-- 3.6 PQR Preheat
CREATE TABLE IF NOT EXISTS weld_pqr_preheat (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    preheat_temp REAL,
    interpass_temp_max REAL,
    temp_unit TEXT DEFAULT 'F'
);

-- 3.7 PQR PWHT
CREATE TABLE IF NOT EXISTS weld_pqr_pwht (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    pwht_performed INTEGER DEFAULT 0,
    temperature REAL,
    time_at_temp REAL,                             -- Hours
    temp_unit TEXT DEFAULT 'F'
);

-- 3.8 PQR Gas
CREATE TABLE IF NOT EXISTS weld_pqr_gas (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,

    shielding_gas TEXT,
    shielding_flow_rate REAL,
    backing_gas TEXT,
    backing_flow_rate REAL
);

-- 3.9 PQR Electrical Parameters
CREATE TABLE IF NOT EXISTS weld_pqr_electrical (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    pass_number TEXT,                              -- "1", "2-5", "Cap", etc.

    process_type TEXT,
    current_type TEXT,
    amperage REAL,
    voltage REAL,
    travel_speed REAL,
    travel_speed_unit TEXT DEFAULT 'in/min',
    wire_feed_speed REAL,
    heat_input REAL,
    heat_input_unit TEXT DEFAULT 'kJ/in',

    filler_diameter TEXT,
    transfer_mode TEXT
);

-- 3.10 PQR Test Results - Tensile
CREATE TABLE IF NOT EXISTS weld_pqr_tensile_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,

    width REAL,
    thickness REAL,
    area REAL,

    ultimate_load REAL,
    ultimate_tensile_strength REAL,               -- PSI

    failure_location TEXT,                         -- Weld, HAZ, Base Metal

    acceptance_criteria TEXT,
    result TEXT                                    -- Pass, Fail
);

-- 3.11 PQR Test Results - Bend
CREATE TABLE IF NOT EXISTS weld_pqr_bend_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,

    bend_type TEXT,                                -- Face, Root, Side, Longitudinal
    mandrel_diameter REAL,
    bend_angle REAL,

    discontinuities TEXT,                          -- Description of any found
    max_discontinuity_size REAL,

    result TEXT                                    -- Pass, Fail
);

-- 3.12 PQR Test Results - Toughness (CVN)
CREATE TABLE IF NOT EXISTS weld_pqr_toughness_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,

    test_type TEXT,                                -- Charpy V-Notch, CTOD, etc.
    location TEXT,                                 -- Weld Metal, HAZ, Base Metal
    orientation TEXT,                              -- Transverse, Longitudinal

    test_temperature REAL,
    temp_unit TEXT DEFAULT 'F',

    energy_absorbed REAL,                          -- ft-lbs
    lateral_expansion REAL,                        -- mils
    shear_percent REAL,

    acceptance_criteria TEXT,
    result TEXT
);

-- 3.13 PQR Other Tests
CREATE TABLE IF NOT EXISTS weld_pqr_other_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    test_type TEXT,                                -- Macro, Hardness, Fillet Weld Break, RT, etc.
    specimen_number TEXT,
    description TEXT,

    results_json TEXT,                             -- Flexible storage for various test results

    acceptance_criteria TEXT,
    result TEXT
);

-- 3.14 PQR Personnel
CREATE TABLE IF NOT EXISTS weld_pqr_personnel (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,

    role TEXT,                                     -- Welder, Operator, Witness, Inspector
    name TEXT,
    stamp_or_id TEXT,
    company TEXT,
    date DATE
);

-- ============================================================================
-- 4. WPQ TABLES (Welder Performance Qualification)
-- ============================================================================
-- QW-484 form structure

CREATE TABLE IF NOT EXISTS weld_wpq (
    id INTEGER PRIMARY KEY,
    wpq_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',

    -- Welder identification
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    welder_name TEXT,                              -- Denormalized for quick access
    welder_stamp TEXT,

    -- WPS reference
    wps_id INTEGER REFERENCES weld_wps(id),
    wps_number TEXT,

    -- Qualification scope
    process_type TEXT NOT NULL,                    -- SMAW, GTAW, etc.

    -- Variables qualified
    p_number_base INTEGER,
    p_number_filler INTEGER,
    f_number INTEGER,

    thickness_qualified_min REAL,
    thickness_qualified_max REAL,
    diameter_qualified_min REAL,

    -- Positions qualified
    groove_positions_qualified TEXT,              -- 1G, 2G, etc. (comma-separated)
    fillet_positions_qualified TEXT,
    progression TEXT,

    -- Backing
    backing_type TEXT,                             -- With, Without

    -- Test date
    test_date DATE,

    -- Expiration (calculated from continuity)
    initial_expiration_date DATE,                 -- 6 months from test_date
    current_expiration_date DATE,                 -- Updated by continuity

    -- Status
    status TEXT DEFAULT 'active',                  -- active, expired, revoked

    -- Witness
    witness_name TEXT,
    witness_stamp TEXT,

    -- File reference
    file_path TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_wpq_welder ON weld_wpq(welder_id);
CREATE INDEX IF NOT EXISTS idx_wpq_process ON weld_wpq(process_type);
CREATE INDEX IF NOT EXISTS idx_wpq_status ON weld_wpq(status);
CREATE INDEX IF NOT EXISTS idx_wpq_expiration ON weld_wpq(current_expiration_date);
CREATE INDEX IF NOT EXISTS idx_wpq_p_number ON weld_wpq(p_number_base);
CREATE INDEX IF NOT EXISTS idx_wpq_f_number ON weld_wpq(f_number);

-- WPQ Test Results
CREATE TABLE IF NOT EXISTS weld_wpq_tests (
    id INTEGER PRIMARY KEY,
    wpq_id INTEGER NOT NULL REFERENCES weld_wpq(id) ON DELETE CASCADE,

    test_type TEXT NOT NULL,                       -- Visual, Bend, RT, UT, Macro
    specimen_number TEXT,

    -- For bend tests
    bend_type TEXT,                                -- Face, Root, Side

    -- Results
    results TEXT,
    acceptance_criteria TEXT,
    result TEXT,                                   -- Pass, Fail

    -- Examiner
    examiner_name TEXT,
    examiner_date DATE
);

-- ============================================================================
-- 5. BPS TABLES (Brazing Procedure Specification)
-- ============================================================================
-- QB-482 form structure

CREATE TABLE IF NOT EXISTS weld_bps (
    id INTEGER PRIMARY KEY,
    bps_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    revision_date DATE,

    title TEXT,
    description TEXT,

    -- Process
    brazing_process TEXT,                          -- TB, FB, IB, RB, DB, etc.

    -- Status
    status TEXT DEFAULT 'draft',
    effective_date DATE,

    -- Approval
    prepared_by TEXT,
    approved_by TEXT,
    approved_date DATE,

    file_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- BPS Joint Details
CREATE TABLE IF NOT EXISTS weld_bps_joints (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    joint_type TEXT,                               -- Lap, Butt, Scarf, etc.
    joint_clearance_min REAL,
    joint_clearance_max REAL,
    joint_overlap REAL,
    joint_details TEXT
);

-- BPS Base Metals
CREATE TABLE IF NOT EXISTS weld_bps_base_metals (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,

    p_number INTEGER,
    material_spec TEXT,
    material_form TEXT,                            -- Tube, Fitting, Plate
    thickness_range TEXT
);

-- BPS Filler Metals
CREATE TABLE IF NOT EXISTS weld_bps_filler_metals (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    f_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    filler_form TEXT,                              -- Wire, Ring, Paste, Foil
    filler_application TEXT                        -- Pre-placed, Face-fed
);

-- BPS Flux/Atmosphere
CREATE TABLE IF NOT EXISTS weld_bps_flux_atmosphere (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    flux_type TEXT,
    flux_application TEXT,

    atmosphere_type TEXT,                          -- Air, Vacuum, Inert gas, Reducing
    atmosphere_gas TEXT,
    dew_point_max REAL
);

-- BPS Positions
CREATE TABLE IF NOT EXISTS weld_bps_positions (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    positions_qualified TEXT,                      -- Flat, Horizontal, Vertical, All
    flow_direction TEXT                            -- Up, Down, Horizontal
);

-- BPS Post-Braze Heat Treatment
CREATE TABLE IF NOT EXISTS weld_bps_pwht (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    pbht_required INTEGER DEFAULT 0,
    temperature REAL,
    time_at_temp REAL,
    temp_unit TEXT DEFAULT 'F',
    notes TEXT
);

-- BPS Technique
CREATE TABLE IF NOT EXISTS weld_bps_technique (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,

    brazing_temp_min REAL,
    brazing_temp_max REAL,
    temp_unit TEXT DEFAULT 'F',

    time_at_temp_min REAL,
    time_at_temp_max REAL,

    heating_method TEXT,                           -- Torch, Furnace, Induction
    cooling_method TEXT,

    technique_details TEXT
);

-- ============================================================================
-- 6. BPQ TABLES (Brazing Procedure Qualification)
-- ============================================================================

CREATE TABLE IF NOT EXISTS weld_bpq (
    id INTEGER PRIMARY KEY,
    bpq_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',

    bps_number TEXT,                               -- BPS this qualifies

    test_date DATE,
    status TEXT DEFAULT 'active',

    -- Coupon details
    coupon_id TEXT,

    -- Witness
    witness_name TEXT,
    witness_company TEXT,

    -- Lab
    lab_name TEXT,
    lab_report_number TEXT,

    file_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- BPQ Base Metals
CREATE TABLE IF NOT EXISTS weld_bpq_base_metals (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,

    p_number INTEGER,
    material_spec TEXT,
    thickness REAL,
    heat_number TEXT
);

-- BPQ Filler Metals
CREATE TABLE IF NOT EXISTS weld_bpq_filler_metals (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,

    f_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    lot_number TEXT
);

-- BPQ Test Results
CREATE TABLE IF NOT EXISTS weld_bpq_tests (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,

    test_type TEXT,                                -- Tension, Peel, Section, Workmanship
    specimen_number TEXT,

    results_json TEXT,
    acceptance_criteria TEXT,
    result TEXT
);

-- ============================================================================
-- 7. BPQR (Brazer Performance Qualification Record)
-- ============================================================================

CREATE TABLE IF NOT EXISTS weld_bpqr (
    id INTEGER PRIMARY KEY,
    bpqr_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',

    -- Brazer identification
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    brazer_name TEXT,
    brazer_stamp TEXT,

    -- BPS reference
    bps_number TEXT,

    -- Qualification scope
    brazing_process TEXT,
    p_number_base INTEGER,
    f_number INTEGER,

    thickness_qualified_min REAL,
    thickness_qualified_max REAL,

    positions_qualified TEXT,

    -- Test date
    test_date DATE,

    -- Expiration
    initial_expiration_date DATE,
    current_expiration_date DATE,

    status TEXT DEFAULT 'active',

    -- Witness
    witness_name TEXT,
    witness_stamp TEXT,

    file_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_bpqr_welder ON weld_bpqr(welder_id);
CREATE INDEX IF NOT EXISTS idx_bpqr_status ON weld_bpqr(status);

-- ============================================================================
-- 8. CONTINUITY TRACKING
-- ============================================================================
-- Track welding activity to maintain 6-month qualification

CREATE TABLE IF NOT EXISTS weld_continuity_log (
    id INTEGER PRIMARY KEY,

    -- Welder
    welder_id INTEGER NOT NULL REFERENCES weld_welder_registry(id),

    -- Process used
    process_type TEXT NOT NULL,                    -- SMAW, GTAW, etc.

    -- Activity details
    activity_date DATE NOT NULL,
    project_number TEXT,
    wps_number TEXT,

    -- Description
    description TEXT,                              -- What was welded

    -- Verification
    verified_by TEXT,
    verification_date DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_continuity_welder ON weld_continuity_log(welder_id);
CREATE INDEX IF NOT EXISTS idx_continuity_date ON weld_continuity_log(activity_date);
CREATE INDEX IF NOT EXISTS idx_continuity_process ON weld_continuity_log(process_type);
CREATE INDEX IF NOT EXISTS idx_continuity_project ON weld_continuity_log(project_number);

-- ============================================================================
-- 9. DOCUMENT INTAKE & REVISION TRACKING
-- ============================================================================

-- Welding document intake log
CREATE TABLE IF NOT EXISTS weld_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,

    document_type TEXT,                            -- WPS, PQR, WPQ, BPS, BPQ, BPQR
    document_number TEXT,                          -- The actual doc number extracted
    document_id INTEGER,                           -- ID in target table

    action TEXT,                                   -- routed, duplicate, superseded, needs_review, failed
    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weld_intake_date ON weld_intake_log(created_at);
CREATE INDEX IF NOT EXISTS idx_weld_intake_type ON weld_intake_log(document_type);

-- Document revision history
CREATE TABLE IF NOT EXISTS weld_document_revisions (
    id INTEGER PRIMARY KEY,

    document_type TEXT NOT NULL,                   -- WPS, PQR, WPQ, BPS, BPQ, BPQR
    document_number TEXT NOT NULL,
    revision TEXT NOT NULL,

    -- What changed
    change_description TEXT,
    changed_by TEXT,
    change_date DATE,

    -- File references
    previous_revision TEXT,
    previous_file_path TEXT,
    new_file_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weld_rev_doc ON weld_document_revisions(document_type, document_number);

-- ============================================================================
-- 10. VIEWS
-- ============================================================================

-- View: Active WPS Summary
CREATE VIEW IF NOT EXISTS v_weld_wps_summary AS
SELECT
    w.id,
    w.wps_number,
    w.revision,
    w.title,
    w.is_swps,
    w.status,
    w.effective_date,
    GROUP_CONCAT(DISTINCT wp.process_type) as processes,
    GROUP_CONCAT(DISTINCT wbm.p_number || '-' || COALESCE(wbm.group_number, 0)) as p_numbers,
    GROUP_CONCAT(DISTINCT wfm.f_number) as f_numbers,
    GROUP_CONCAT(DISTINCT wfm.a_number) as a_numbers,
    GROUP_CONCAT(DISTINCT wpl.pqr_number) as supporting_pqrs,
    w.file_path
FROM weld_wps w
LEFT JOIN weld_wps_processes wp ON w.id = wp.wps_id
LEFT JOIN weld_wps_base_metals wbm ON w.id = wbm.wps_id
LEFT JOIN weld_wps_filler_metals wfm ON w.id = wfm.wps_id
LEFT JOIN weld_wps_pqr_links wpl ON w.id = wpl.wps_id
WHERE w.status = 'active'
GROUP BY w.id;

-- View: PQR Summary with Test Results
CREATE VIEW IF NOT EXISTS v_weld_pqr_summary AS
SELECT
    p.id,
    p.pqr_number,
    p.revision,
    p.wps_number,
    p.test_date,
    p.status,
    GROUP_CONCAT(DISTINCT pbm.p_number || '-' || COALESCE(pbm.group_number, 0)) as p_numbers,
    GROUP_CONCAT(DISTINCT pfm.f_number) as f_numbers,
    (SELECT COUNT(*) FROM weld_pqr_tensile_tests WHERE pqr_id = p.id AND result = 'Pass') as tensile_pass,
    (SELECT COUNT(*) FROM weld_pqr_tensile_tests WHERE pqr_id = p.id AND result = 'Fail') as tensile_fail,
    (SELECT COUNT(*) FROM weld_pqr_bend_tests WHERE pqr_id = p.id AND result = 'Pass') as bend_pass,
    (SELECT COUNT(*) FROM weld_pqr_bend_tests WHERE pqr_id = p.id AND result = 'Fail') as bend_fail,
    p.file_path
FROM weld_pqr p
LEFT JOIN weld_pqr_base_metals pbm ON p.id = pbm.pqr_id
LEFT JOIN weld_pqr_filler_metals pfm ON p.id = pfm.pqr_id
GROUP BY p.id;

-- View: Welder Qualification Status (per process)
CREATE VIEW IF NOT EXISTS v_weld_welder_qualification_status AS
SELECT
    wr.id as welder_id,
    wr.employee_number,
    wr.last_name || ', ' || wr.first_name as welder_name,
    wr.welder_stamp,
    wr.status as employment_status,
    wpq.process_type,
    wpq.wps_number,
    wpq.groove_positions_qualified,
    wpq.fillet_positions_qualified,
    wpq.p_number_base,
    wpq.f_number,
    wpq.thickness_qualified_min,
    wpq.thickness_qualified_max,
    wpq.test_date,
    wpq.current_expiration_date,
    wpq.status as qualification_status,
    CASE
        WHEN wpq.current_expiration_date < DATE('now') THEN 'EXPIRED'
        WHEN wpq.current_expiration_date < DATE('now', '+30 days') THEN 'EXPIRING'
        ELSE 'CURRENT'
    END as expiration_warning
FROM weld_welder_registry wr
LEFT JOIN weld_wpq wpq ON wr.id = wpq.welder_id
WHERE wr.status = 'active';

-- View: Expiring Qualifications (within 30 days)
CREATE VIEW IF NOT EXISTS v_weld_expiring_qualifications AS
SELECT
    wr.employee_number,
    wr.last_name || ', ' || wr.first_name as welder_name,
    wr.welder_stamp,
    wpq.wpq_number,
    wpq.process_type,
    wpq.wps_number,
    wpq.current_expiration_date,
    CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now')) AS INTEGER) as days_until_expiration
FROM weld_welder_registry wr
JOIN weld_wpq wpq ON wr.id = wpq.welder_id
WHERE wpq.status = 'active'
  AND wpq.current_expiration_date BETWEEN DATE('now') AND DATE('now', '+30 days')
ORDER BY wpq.current_expiration_date;

-- View: Full Qualification Matrix
CREATE VIEW IF NOT EXISTS v_weld_qualification_matrix AS
SELECT
    wr.employee_number,
    wr.last_name || ', ' || wr.first_name as welder_name,
    wr.welder_stamp,
    wpq.process_type,
    wpq.p_number_base as p_number,
    wpq.f_number,
    wpq.thickness_qualified_min || ' - ' || wpq.thickness_qualified_max as thickness_range,
    wpq.groove_positions_qualified as groove_pos,
    wpq.fillet_positions_qualified as fillet_pos,
    CASE WHEN wpq.backing_type = 'Without' THEN 'Open Root' ELSE 'Backing' END as backing,
    wpq.current_expiration_date as expires,
    wpq.status
FROM weld_welder_registry wr
JOIN weld_wpq wpq ON wr.id = wpq.welder_id
WHERE wr.status = 'active'
ORDER BY wr.last_name, wr.first_name, wpq.process_type;

-- View: Find WPS by Material (P-number)
CREATE VIEW IF NOT EXISTS v_weld_wps_by_material AS
SELECT
    w.wps_number,
    w.revision,
    w.title,
    w.status,
    wbm.p_number,
    wbm.group_number,
    wbm.material_spec,
    wbm.thickness_min || ' - ' || wbm.thickness_max as thickness_range,
    GROUP_CONCAT(DISTINCT wp.process_type) as processes
FROM weld_wps w
JOIN weld_wps_base_metals wbm ON w.id = wbm.wps_id
LEFT JOIN weld_wps_processes wp ON w.id = wp.wps_id
WHERE w.status = 'active'
GROUP BY w.id, wbm.id
ORDER BY wbm.p_number, w.wps_number;

-- View: Recent Welding Activity
CREATE VIEW IF NOT EXISTS v_weld_recent_activity AS
SELECT
    'WPS' as doc_type,
    wps_number as doc_number,
    revision,
    updated_at as activity_date,
    status,
    'Updated' as action
FROM weld_wps
WHERE updated_at > DATE('now', '-30 days')
UNION ALL
SELECT
    'PQR' as doc_type,
    pqr_number as doc_number,
    revision,
    updated_at as activity_date,
    status,
    'Updated' as action
FROM weld_pqr
WHERE updated_at > DATE('now', '-30 days')
UNION ALL
SELECT
    'WPQ' as doc_type,
    wpq_number as doc_number,
    revision,
    updated_at as activity_date,
    status,
    'Updated' as action
FROM weld_wpq
WHERE updated_at > DATE('now', '-30 days')
ORDER BY activity_date DESC;

-- View: Welder Continuity Status
CREATE VIEW IF NOT EXISTS v_weld_continuity_status AS
SELECT
    wr.employee_number,
    wr.last_name || ', ' || wr.first_name as welder_name,
    wr.welder_stamp,
    cl.process_type,
    MAX(cl.activity_date) as last_activity,
    DATE(MAX(cl.activity_date), '+6 months') as continuity_expires,
    CASE
        WHEN DATE(MAX(cl.activity_date), '+6 months') < DATE('now') THEN 'LAPSED'
        WHEN DATE(MAX(cl.activity_date), '+6 months') < DATE('now', '+30 days') THEN 'AT RISK'
        ELSE 'CURRENT'
    END as continuity_status,
    COUNT(*) as activity_count_6mo
FROM weld_welder_registry wr
LEFT JOIN weld_continuity_log cl ON wr.id = cl.welder_id
    AND cl.activity_date > DATE('now', '-6 months')
WHERE wr.status = 'active'
GROUP BY wr.id, cl.process_type
ORDER BY wr.last_name, wr.first_name, cl.process_type;

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMPS
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS tr_weld_wps_updated
AFTER UPDATE ON weld_wps
BEGIN
    UPDATE weld_wps SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_weld_pqr_updated
AFTER UPDATE ON weld_pqr
BEGIN
    UPDATE weld_pqr SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_weld_wpq_updated
AFTER UPDATE ON weld_wpq
BEGIN
    UPDATE weld_wpq SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_weld_bps_updated
AFTER UPDATE ON weld_bps
BEGIN
    UPDATE weld_bps SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_weld_bpq_updated
AFTER UPDATE ON weld_bpq
BEGIN
    UPDATE weld_bpq SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_weld_bpqr_updated
AFTER UPDATE ON weld_bpqr
BEGIN
    UPDATE weld_bpqr SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ============================================================================
-- END OF WELDING MODULE SCHEMA
-- ============================================================================
