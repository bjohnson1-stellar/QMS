-- =============================================================================
-- QMS Welding Schema
-- ASME IX / AWS welding program: WPS, PQR, WPQ, BPS, BPQ/BPQR,
-- welder registry, continuity, production welds, NDT, notifications
-- =============================================================================

-- =========== WELDER REGISTRY ===========

CREATE TABLE IF NOT EXISTS weld_welder_registry (
    id INTEGER PRIMARY KEY,
    employee_number TEXT UNIQUE NOT NULL,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    middle_initial TEXT,
    welder_stamp TEXT UNIQUE,
    ssn_last_four TEXT,
    hire_date DATE,
    termination_date DATE,
    status TEXT DEFAULT 'active',
    department TEXT,
    supervisor TEXT,
    email TEXT,
    phone TEXT,
    photo_path TEXT,
    signature_path TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    preferred_name TEXT,
    display_name TEXT,
    business_unit TEXT,
    business_unit_id INTEGER REFERENCES business_units(id),
    running_total_welds INTEGER DEFAULT 0,
    total_welds_tested INTEGER DEFAULT 0,
    welds_passed INTEGER DEFAULT 0,
    welds_failed INTEGER DEFAULT 0,
    excel_row_hash TEXT,
    employee_id TEXT REFERENCES employees(id)
);

-- =========== WPS (Welding Procedure Specification) ===========

CREATE TABLE IF NOT EXISTS weld_wps (
    id INTEGER PRIMARY KEY,
    wps_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    revision_date DATE,
    is_swps INTEGER DEFAULT 0,
    swps_document_number TEXT,
    title TEXT,
    description TEXT,
    applicable_codes TEXT,
    scope_of_work TEXT,
    status TEXT DEFAULT 'draft',
    effective_date DATE,
    superseded_date DATE,
    superseded_by TEXT,
    prepared_by TEXT,
    prepared_date DATE,
    reviewed_by TEXT,
    reviewed_date DATE,
    approved_by TEXT,
    approved_date DATE,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_processes (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    process_type TEXT NOT NULL,
    process_variation TEXT,
    layer_deposit TEXT,
    UNIQUE(wps_id, process_sequence)
);

CREATE TABLE IF NOT EXISTS weld_wps_joints (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    joint_type TEXT,
    groove_type TEXT,
    groove_angle_min REAL,
    groove_angle_max REAL,
    root_opening_min REAL,
    root_opening_max REAL,
    root_face_min REAL,
    root_face_max REAL,
    backing_type TEXT,
    backing_material TEXT,
    retainers TEXT,
    joint_details_json TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_base_metals (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,
    p_number INTEGER,
    group_number INTEGER,
    material_spec TEXT,
    material_grade TEXT,
    material_type TEXT,
    thickness_min REAL,
    thickness_max REAL,
    thickness_unit TEXT DEFAULT 'in',
    diameter_min REAL,
    diameter_max REAL,
    diameter_unit TEXT DEFAULT 'in',
    s_number INTEGER
);

CREATE TABLE IF NOT EXISTS weld_wps_filler_metals (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    f_number INTEGER,
    a_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    filler_diameter TEXT,
    filler_form TEXT,
    flux_trade_name TEXT,
    flux_type TEXT,
    flux_class TEXT,
    consumable_insert TEXT,
    insert_class TEXT,
    supplementary_filler TEXT,
    powder_or_wire TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_positions (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    groove_positions TEXT,
    fillet_positions TEXT,
    progression TEXT,
    position_notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_preheat (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    preheat_temp_min REAL,
    preheat_temp_max REAL,
    temp_unit TEXT DEFAULT 'F',
    interpass_temp_max REAL,
    preheat_maintenance TEXT,
    preheat_method TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_pwht (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    pwht_required INTEGER DEFAULT 0,
    temperature_min REAL,
    temperature_max REAL,
    temp_unit TEXT DEFAULT 'F',
    time_min REAL,
    time_max REAL,
    heating_rate_max REAL,
    cooling_rate_max REAL,
    pwht_method TEXT,
    pwht_exemption TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_gas (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    shielding_gas TEXT,
    shielding_flow_rate_min REAL,
    shielding_flow_rate_max REAL,
    flow_rate_unit TEXT DEFAULT 'CFH',
    backing_gas TEXT,
    backing_flow_rate_min REAL,
    backing_flow_rate_max REAL,
    trailing_gas TEXT,
    trailing_flow_rate REAL
);

CREATE TABLE IF NOT EXISTS weld_wps_electrical_params (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    pass_type TEXT,
    current_type TEXT,
    amperage_min REAL,
    amperage_max REAL,
    voltage_min REAL,
    voltage_max REAL,
    travel_speed_min REAL,
    travel_speed_max REAL,
    travel_speed_unit TEXT DEFAULT 'in/min',
    wire_feed_speed_min REAL,
    wire_feed_speed_max REAL,
    wire_feed_unit TEXT DEFAULT 'in/min',
    heat_input_min REAL,
    heat_input_max REAL,
    heat_input_unit TEXT DEFAULT 'kJ/in',
    pulsing_params_json TEXT,
    transfer_mode TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_technique (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    bead_type TEXT,
    weave_amplitude_max REAL,
    single_or_multi_pass TEXT,
    single_or_multi_layer TEXT,
    electrode_angle_min REAL,
    electrode_angle_max REAL,
    interpass_cleaning TEXT,
    root_cleaning TEXT,
    peening TEXT,
    ctwd_min REAL,
    ctwd_max REAL,
    multiple_electrodes INTEGER DEFAULT 0,
    electrode_spacing REAL,
    oscillation_json TEXT,
    technique_details_json TEXT
);

CREATE TABLE IF NOT EXISTS weld_wps_pqr_links (
    id INTEGER PRIMARY KEY,
    wps_id INTEGER NOT NULL REFERENCES weld_wps(id) ON DELETE CASCADE,
    pqr_id INTEGER REFERENCES weld_pqr(id),
    pqr_number TEXT,
    qualification_scope TEXT,
    UNIQUE(wps_id, pqr_id)
);

-- =========== PQR (Procedure Qualification Record) ===========

CREATE TABLE IF NOT EXISTS weld_pqr (
    id INTEGER PRIMARY KEY,
    pqr_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    wps_number TEXT,
    coupon_id TEXT,
    test_date DATE,
    witness_name TEXT,
    witness_company TEXT,
    witness_stamp TEXT,
    lab_name TEXT,
    lab_report_number TEXT,
    status TEXT DEFAULT 'active',
    prepared_by TEXT,
    prepared_date DATE,
    reviewed_by TEXT,
    reviewed_date DATE,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

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
    actual_dimensions_json TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_base_metals (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,
    p_number INTEGER,
    group_number INTEGER,
    material_spec TEXT,
    material_grade TEXT,
    thickness REAL,
    diameter REAL,
    heat_number TEXT,
    lot_number TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_filler_metals (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    f_number INTEGER,
    a_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    filler_diameter TEXT,
    trade_name TEXT,
    heat_lot TEXT,
    flux_trade_name TEXT,
    flux_lot TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_positions (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    test_position TEXT,
    progression TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_preheat (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    preheat_temp REAL,
    interpass_temp_max REAL,
    temp_unit TEXT DEFAULT 'F'
);

CREATE TABLE IF NOT EXISTS weld_pqr_pwht (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    pwht_performed INTEGER DEFAULT 0,
    temperature REAL,
    time_at_temp REAL,
    temp_unit TEXT DEFAULT 'F'
);

CREATE TABLE IF NOT EXISTS weld_pqr_gas (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    shielding_gas TEXT,
    shielding_flow_rate REAL,
    backing_gas TEXT,
    backing_flow_rate REAL
);

CREATE TABLE IF NOT EXISTS weld_pqr_electrical (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    process_sequence INTEGER DEFAULT 1,
    pass_number TEXT,
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

CREATE TABLE IF NOT EXISTS weld_pqr_tensile_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,
    width REAL,
    thickness REAL,
    area REAL,
    ultimate_load REAL,
    ultimate_tensile_strength REAL,
    failure_location TEXT,
    acceptance_criteria TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_bend_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,
    bend_type TEXT,
    mandrel_diameter REAL,
    bend_angle REAL,
    discontinuities TEXT,
    max_discontinuity_size REAL,
    result TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_toughness_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    specimen_number TEXT,
    test_type TEXT,
    location TEXT,
    orientation TEXT,
    test_temperature REAL,
    temp_unit TEXT DEFAULT 'F',
    energy_absorbed REAL,
    lateral_expansion REAL,
    shear_percent REAL,
    acceptance_criteria TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_other_tests (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    test_type TEXT,
    specimen_number TEXT,
    description TEXT,
    results_json TEXT,
    acceptance_criteria TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS weld_pqr_personnel (
    id INTEGER PRIMARY KEY,
    pqr_id INTEGER NOT NULL REFERENCES weld_pqr(id) ON DELETE CASCADE,
    role TEXT,
    name TEXT,
    stamp_or_id TEXT,
    company TEXT,
    date DATE
);

-- =========== WPQ (Welder Performance Qualification) ===========

CREATE TABLE IF NOT EXISTS weld_wpq (
    id INTEGER PRIMARY KEY,
    wpq_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    welder_name TEXT,
    welder_stamp TEXT,
    wps_id INTEGER REFERENCES weld_wps(id),
    wps_number TEXT,
    process_type TEXT NOT NULL,
    p_number_base INTEGER,
    p_number_filler INTEGER,
    f_number INTEGER,
    thickness_qualified_min REAL,
    thickness_qualified_max REAL,
    diameter_qualified_min REAL,
    groove_positions_qualified TEXT,
    fillet_positions_qualified TEXT,
    progression TEXT,
    backing_type TEXT,
    test_date DATE,
    initial_expiration_date DATE,
    current_expiration_date DATE,
    status TEXT DEFAULT 'active',
    witness_name TEXT,
    witness_stamp TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    welder_employee_id TEXT REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS weld_wpq_tests (
    id INTEGER PRIMARY KEY,
    wpq_id INTEGER NOT NULL REFERENCES weld_wpq(id) ON DELETE CASCADE,
    test_type TEXT NOT NULL,
    specimen_number TEXT,
    bend_type TEXT,
    results TEXT,
    acceptance_criteria TEXT,
    result TEXT,
    examiner_name TEXT,
    examiner_date DATE
);

-- =========== BPS (Brazing Procedure Specification) ===========

CREATE TABLE IF NOT EXISTS weld_bps (
    id INTEGER PRIMARY KEY,
    bps_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    revision_date DATE,
    title TEXT,
    description TEXT,
    brazing_process TEXT,
    status TEXT DEFAULT 'draft',
    effective_date DATE,
    prepared_by TEXT,
    approved_by TEXT,
    approved_date DATE,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_joints (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    joint_type TEXT,
    joint_clearance_min REAL,
    joint_clearance_max REAL,
    joint_overlap REAL,
    joint_details TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_base_metals (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,
    p_number INTEGER,
    material_spec TEXT,
    material_form TEXT,
    thickness_range TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_filler_metals (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    f_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    filler_form TEXT,
    filler_application TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_flux_atmosphere (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    flux_type TEXT,
    flux_application TEXT,
    atmosphere_type TEXT,
    atmosphere_gas TEXT,
    dew_point_max REAL
);

CREATE TABLE IF NOT EXISTS weld_bps_positions (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    positions_qualified TEXT,
    flow_direction TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_pwht (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    pbht_required INTEGER DEFAULT 0,
    temperature REAL,
    time_at_temp REAL,
    temp_unit TEXT DEFAULT 'F',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_bps_technique (
    id INTEGER PRIMARY KEY,
    bps_id INTEGER NOT NULL REFERENCES weld_bps(id) ON DELETE CASCADE,
    brazing_temp_min REAL,
    brazing_temp_max REAL,
    temp_unit TEXT DEFAULT 'F',
    time_at_temp_min REAL,
    time_at_temp_max REAL,
    heating_method TEXT,
    cooling_method TEXT,
    technique_details TEXT
);

-- =========== BPQ / BPQR (Brazing Performance Qualification) ===========

CREATE TABLE IF NOT EXISTS weld_bpq (
    id INTEGER PRIMARY KEY,
    bpq_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    bps_number TEXT,
    test_date DATE,
    status TEXT DEFAULT 'active',
    coupon_id TEXT,
    witness_name TEXT,
    witness_company TEXT,
    lab_name TEXT,
    lab_report_number TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_bpq_base_metals (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,
    metal_sequence INTEGER DEFAULT 1,
    p_number INTEGER,
    material_spec TEXT,
    thickness REAL,
    heat_number TEXT
);

CREATE TABLE IF NOT EXISTS weld_bpq_filler_metals (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,
    f_number INTEGER,
    sfa_spec TEXT,
    aws_class TEXT,
    lot_number TEXT
);

CREATE TABLE IF NOT EXISTS weld_bpq_tests (
    id INTEGER PRIMARY KEY,
    bpq_id INTEGER NOT NULL REFERENCES weld_bpq(id) ON DELETE CASCADE,
    test_type TEXT,
    specimen_number TEXT,
    results_json TEXT,
    acceptance_criteria TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS weld_bpqr (
    id INTEGER PRIMARY KEY,
    bpqr_number TEXT UNIQUE NOT NULL,
    revision TEXT DEFAULT '0',
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    brazer_name TEXT,
    brazer_stamp TEXT,
    bps_number TEXT,
    brazing_process TEXT,
    p_number_base INTEGER,
    f_number INTEGER,
    thickness_qualified_min REAL,
    thickness_qualified_max REAL,
    positions_qualified TEXT,
    test_date DATE,
    initial_expiration_date DATE,
    current_expiration_date DATE,
    status TEXT DEFAULT 'active',
    witness_name TEXT,
    witness_stamp TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    welder_employee_id TEXT REFERENCES employees(id)
);

-- =========== CONTINUITY & PRODUCTION ===========

CREATE TABLE IF NOT EXISTS weld_continuity_events (
    id INTEGER PRIMARY KEY,
    welder_id INTEGER NOT NULL REFERENCES weld_welder_registry(id),
    welder_employee_id TEXT REFERENCES employees(id),
    event_type TEXT NOT NULL,
    event_date DATE NOT NULL,
    week_ending DATE,
    project_number TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(welder_id, event_type, project_number, week_ending)
);

CREATE INDEX IF NOT EXISTS idx_continuity_events_welder ON weld_continuity_events(welder_id);
CREATE INDEX IF NOT EXISTS idx_continuity_events_date ON weld_continuity_events(event_date);
CREATE INDEX IF NOT EXISTS idx_continuity_events_week ON weld_continuity_events(week_ending);

CREATE TABLE IF NOT EXISTS weld_continuity_event_processes (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES weld_continuity_events(id) ON DELETE CASCADE,
    process_type TEXT NOT NULL,
    wpq_id INTEGER REFERENCES weld_wpq(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, process_type)
);

CREATE INDEX IF NOT EXISTS idx_continuity_ep_event ON weld_continuity_event_processes(event_id);

CREATE TABLE IF NOT EXISTS weld_continuity_log (
    id INTEGER PRIMARY KEY,
    welder_id INTEGER NOT NULL REFERENCES weld_welder_registry(id),
    process_type TEXT NOT NULL,
    activity_date DATE NOT NULL,
    project_number TEXT,
    wps_number TEXT,
    description TEXT,
    verified_by TEXT,
    verification_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    welder_employee_id TEXT REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS weld_production_welds (
    id INTEGER PRIMARY KEY,
    welder_id INTEGER NOT NULL REFERENCES weld_welder_registry(id),
    weld_number TEXT,
    project_number TEXT,
    process_type TEXT NOT NULL,
    wps_number TEXT,
    pipe_size TEXT,
    position TEXT,
    weld_date DATE NOT NULL,
    status TEXT DEFAULT 'complete',
    counts_for_continuity INTEGER DEFAULT 1,
    week_ending DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    notes TEXT,
    welder_employee_id TEXT REFERENCES employees(id),
    UNIQUE(welder_id, project_number, week_ending) ON CONFLICT REPLACE
);

CREATE TABLE IF NOT EXISTS weld_ndt_results (
    id INTEGER PRIMARY KEY,
    production_weld_id INTEGER REFERENCES weld_production_welds(id),
    welder_id INTEGER REFERENCES weld_welder_registry(id),
    ndt_type TEXT NOT NULL,
    test_date DATE NOT NULL,
    result TEXT NOT NULL,
    report_number TEXT,
    defect_type TEXT,
    examiner_name TEXT,
    examiner_level TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    welder_employee_id TEXT REFERENCES employees(id)
);

-- =========== NOTIFICATIONS ===========

CREATE TABLE IF NOT EXISTS weld_notification_rules (
    id INTEGER PRIMARY KEY,
    rule_name TEXT UNIQUE NOT NULL,
    notification_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    days_before INTEGER NOT NULL,
    priority TEXT DEFAULT 'normal',
    repeat_interval_days INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weld_notifications (
    id INTEGER PRIMARY KEY,
    notification_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    rule_id INTEGER REFERENCES weld_notification_rules(id),
    priority TEXT DEFAULT 'normal',
    due_date DATE,
    days_until_due INTEGER,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP,
    resolved_by TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, rule_id, status) ON CONFLICT REPLACE
);

-- =========== INTAKE & DOCUMENT CONTROL ===========

CREATE TABLE IF NOT EXISTS weld_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    document_type TEXT,
    document_number TEXT,
    document_id INTEGER,
    action TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weld_document_revisions (
    id INTEGER PRIMARY KEY,
    document_type TEXT NOT NULL,
    document_number TEXT NOT NULL,
    revision TEXT NOT NULL,
    change_description TEXT,
    changed_by TEXT,
    change_date DATE,
    previous_revision TEXT,
    previous_file_path TEXT,
    new_file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========== WELD CERT REQUESTS ===========

CREATE TABLE IF NOT EXISTS weld_cert_requests (
    id              INTEGER PRIMARY KEY,
    wcr_number      TEXT UNIQUE NOT NULL,
    welder_id       INTEGER REFERENCES weld_welder_registry(id),
    employee_number TEXT,
    welder_name     TEXT,
    welder_stamp    TEXT,
    project_number  TEXT,
    project_name    TEXT,
    request_date    TEXT,
    submitted_by    TEXT,
    submitted_at    TEXT,
    status          TEXT NOT NULL DEFAULT 'pending_approval',
    is_new_welder   INTEGER DEFAULT 0,
    notes           TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    source_file     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wcr_status ON weld_cert_requests(status);
CREATE INDEX IF NOT EXISTS idx_wcr_welder ON weld_cert_requests(welder_id);
CREATE INDEX IF NOT EXISTS idx_wcr_project ON weld_cert_requests(project_number);

CREATE TABLE IF NOT EXISTS weld_cert_request_coupons (
    id              INTEGER PRIMARY KEY,
    wcr_id          INTEGER NOT NULL REFERENCES weld_cert_requests(id) ON DELETE CASCADE,
    coupon_number   INTEGER NOT NULL,
    process         TEXT,
    position        TEXT,
    wps_number      TEXT,
    base_material   TEXT,
    filler_metal    TEXT,
    thickness       TEXT,
    diameter        TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    test_result     TEXT,
    visual_result   TEXT,
    bend_result     TEXT,
    rt_result       TEXT,
    failure_reason  TEXT,
    tested_by       TEXT,
    tested_at       TEXT,
    wpq_id          INTEGER REFERENCES weld_wpq(id),
    retest_wcr_id   INTEGER REFERENCES weld_cert_requests(id),
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(wcr_id, coupon_number)
);

CREATE INDEX IF NOT EXISTS idx_wcr_coupon_wcr ON weld_cert_request_coupons(wcr_id);
CREATE INDEX IF NOT EXISTS idx_wcr_coupon_status ON weld_cert_request_coupons(status);

-- =========== LOOKUP TABLES (ASME IX Reference Data) ===========

CREATE TABLE IF NOT EXISTS weld_valid_processes (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'welding',
    aws_letter TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_p_numbers (
    id INTEGER PRIMARY KEY,
    p_number INTEGER NOT NULL,
    group_number INTEGER,
    material_type TEXT NOT NULL,
    common_specs TEXT,
    notes TEXT,
    UNIQUE(p_number, group_number)
);

CREATE TABLE IF NOT EXISTS weld_valid_f_numbers (
    id INTEGER PRIMARY KEY,
    f_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    process_category TEXT,
    notes TEXT,
    UNIQUE(f_number, process_category)
);

CREATE TABLE IF NOT EXISTS weld_valid_a_numbers (
    id INTEGER PRIMARY KEY,
    a_number INTEGER UNIQUE NOT NULL,
    description TEXT NOT NULL,
    weld_deposit_type TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_positions (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    joint_type TEXT,
    qualifies_for TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_sfa_specs (
    id INTEGER PRIMARY KEY,
    spec_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    filler_type TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_aws_classes (
    id INTEGER PRIMARY KEY,
    aws_class TEXT NOT NULL,
    sfa_spec TEXT,
    f_number INTEGER,
    a_number INTEGER,
    description TEXT,
    UNIQUE(aws_class, sfa_spec)
);

CREATE TABLE IF NOT EXISTS weld_valid_current_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    compatible_processes TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_filler_forms (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_joint_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_groove_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_bead_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weld_valid_gas_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    chemical_symbol TEXT,
    category TEXT,
    notes TEXT
);

-- =========== EXTRACTION AUDIT LOG ===========

CREATE TABLE IF NOT EXISTS weld_extraction_log (
    id INTEGER PRIMARY KEY,
    form_type TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_path TEXT,
    identifier TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    confidence REAL,
    primary_model TEXT,
    secondary_model TEXT,
    shadow_model TEXT,
    disagreements_json TEXT,
    extracted_data_json TEXT,
    validation_issues_json TEXT,
    parent_record_id INTEGER,
    child_records_json TEXT,
    processed_by TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_extraction_log_form ON weld_extraction_log(form_type);
CREATE INDEX IF NOT EXISTS idx_extraction_log_status ON weld_extraction_log(status);
CREATE INDEX IF NOT EXISTS idx_extraction_log_identifier ON weld_extraction_log(identifier);

-- =========== FORM TEMPLATE REGISTRY ===========

CREATE TABLE IF NOT EXISTS weld_form_templates (
    id INTEGER PRIMARY KEY,
    form_type TEXT NOT NULL,
    format TEXT NOT NULL,
    variant TEXT,
    file_path TEXT NOT NULL,
    description TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(form_type, format, variant)
);
