-- =============================================================================
-- QMS Pipeline Schema
-- Generated: 2026-02-09
-- =============================================================================

-- =============================================================================
-- 1. CORE EXTRACTION TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS sheets (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    discipline TEXT,
    file_name TEXT,
    file_path TEXT,
    drawing_number TEXT,
    title TEXT,
    revision TEXT,
    revision_sequence INTEGER DEFAULT 1,
    is_current INTEGER DEFAULT 1,
    supersedes INTEGER REFERENCES sheets(id),
    superseded_by INTEGER REFERENCES sheets(id),
    drawing_type TEXT,
    complexity TEXT,
    extracted_at TEXT,
    extraction_model TEXT,
    quality_score REAL,
    file_hash TEXT,
    file_size INTEGER,
    page_count INTEGER,
    drawing_category TEXT,
    UNIQUE(project_id, drawing_number, revision)
);

CREATE TABLE IF NOT EXISTS disciplines (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    folder_path TEXT,
    normalized_name TEXT,
    sheet_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS discipline_defaults (
    id INTEGER PRIMARY KEY,
    name TEXT,
    common_names TEXT,
    drawing_prefixes TEXT
);

CREATE TABLE IF NOT EXISTS lines (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    line_number TEXT NOT NULL,
    size TEXT,
    material TEXT,
    spec_class TEXT,
    from_location TEXT,
    to_location TEXT,
    service TEXT,
    confidence REAL DEFAULT 1.0,
    pipe_material TEXT,
    pipe_spec TEXT,
    refrigerant TEXT,
    normalized_size TEXT
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    description TEXT,
    equipment_type TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS instruments (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    instrument_type TEXT,
    loop_number TEXT,
    confidence REAL DEFAULT 1.0,
    service TEXT,
    description TEXT,
    location TEXT,
    drawing_number TEXT,
    extraction_notes TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS welds (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    weld_id TEXT,
    weld_type TEXT,
    size TEXT,
    joint_type TEXT,
    nde_required TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    conflict_type TEXT,
    severity TEXT,
    item TEXT,
    details TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipment_master (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    tag TEXT NOT NULL,
    description TEXT,
    equipment_type TEXT,
    system TEXT,
    location TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, tag)
);

CREATE TABLE IF NOT EXISTS equipment_appearances (
    id INTEGER PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipment_master(id),
    sheet_id INTEGER REFERENCES sheets(id),
    confidence REAL DEFAULT 1.0,
    context TEXT,
    UNIQUE(equipment_id, sheet_id)
);

-- =============================================================================
-- 2. SPECIFICATIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS specifications (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    spec_number TEXT NOT NULL,
    title TEXT,
    spec_type TEXT,
    revision TEXT,
    revision_date TEXT,
    file_name TEXT,
    file_path TEXT,
    page_count INTEGER,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
    extraction_model TEXT,
    quality_score REAL,
    UNIQUE(project_id, spec_number, revision)
);

CREATE TABLE IF NOT EXISTS spec_sections (
    id INTEGER PRIMARY KEY,
    spec_id INTEGER REFERENCES specifications(id),
    section_number TEXT,
    section_title TEXT,
    page_number INTEGER,
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spec_items (
    id INTEGER PRIMARY KEY,
    section_id INTEGER REFERENCES spec_sections(id),
    spec_id INTEGER REFERENCES specifications(id),
    item_type TEXT NOT NULL,
    item_key TEXT NOT NULL,
    size_range TEXT,
    material TEXT,
    material_grade TEXT,
    schedule TEXT,
    rating TEXT,
    end_connection TEXT,
    details TEXT,
    raw_text TEXT,
    page_number INTEGER,
    confidence REAL DEFAULT 1.0,
    UNIQUE(spec_id, item_type, item_key)
);

CREATE TABLE IF NOT EXISTS master_spec_items (
    id INTEGER PRIMARY KEY,
    item_type TEXT NOT NULL,
    item_key TEXT NOT NULL,
    material TEXT,
    material_grade TEXT,
    schedule TEXT,
    rating TEXT,
    end_connection TEXT,
    size_range TEXT,
    details TEXT,
    project_count INTEGER DEFAULT 1,
    first_seen_project INTEGER REFERENCES projects(id),
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    consistency_score REAL DEFAULT 1.0,
    UNIQUE(item_type, item_key)
);

CREATE TABLE IF NOT EXISTS spec_variations (
    id INTEGER PRIMARY KEY,
    master_item_id INTEGER REFERENCES master_spec_items(id),
    project_id INTEGER REFERENCES projects(id),
    spec_id INTEGER REFERENCES specifications(id),
    field_name TEXT NOT NULL,
    master_value TEXT,
    project_value TEXT,
    variation_type TEXT,
    significance TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(master_item_id, project_id, field_name)
);

CREATE TABLE IF NOT EXISTS spec_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    action TEXT,
    project_id INTEGER REFERENCES projects(id),
    spec_id INTEGER REFERENCES specifications(id),
    detected_project_number TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 3. EXTRACTION QA & PROCESSING
-- =============================================================================

CREATE TABLE IF NOT EXISTS extraction_flags (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    field TEXT,
    issue TEXT,
    severity TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    model TEXT NOT NULL,
    run_type TEXT,
    items_extracted INTEGER,
    flags_raised INTEGER,
    duration_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extraction_misses (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    extraction_model TEXT,
    found_by TEXT,
    missed_item_type TEXT,
    missed_item TEXT,
    severity TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shadow_reviews (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    extraction_model TEXT,
    review_model TEXT DEFAULT 'opus',
    items_checked INTEGER,
    items_correct INTEGER,
    items_missed INTEGER,
    items_wrong INTEGER,
    accuracy REAL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gold_standard (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    drawing_type TEXT,
    complexity TEXT,
    verified_extraction TEXT,
    verified_by TEXT,
    verified_at TEXT,
    UNIQUE(sheet_id)
);

CREATE TABLE IF NOT EXISTS accuracy_log (
    id INTEGER PRIMARY KEY,
    model TEXT,
    drawing_type TEXT,
    period_start TEXT,
    period_end TEXT,
    sheets_checked INTEGER,
    accuracy REAL,
    miss_rate REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routing_changes (
    id INTEGER PRIMARY KEY,
    drawing_type TEXT,
    old_model TEXT,
    new_model TEXT,
    reason TEXT,
    accuracy_before REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    project_id INTEGER REFERENCES projects(id),
    task TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    action TEXT,
    project_id INTEGER REFERENCES projects(id),
    sheet_id INTEGER REFERENCES sheets(id),
    old_revision TEXT,
    new_revision TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS revision_deltas (
    id INTEGER PRIMARY KEY,
    old_sheet_id INTEGER REFERENCES sheets(id),
    new_sheet_id INTEGER REFERENCES sheets(id),
    delta_type TEXT,
    item_type TEXT,
    item_id TEXT,
    old_value TEXT,
    new_value TEXT,
    significance TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extraction_notes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    note_type TEXT,
    description TEXT,
    confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drawing_category_config (
    category TEXT PRIMARY KEY,
    expect_lines INTEGER DEFAULT 0,
    expect_equipment INTEGER DEFAULT 0,
    expect_instruments INTEGER DEFAULT 0,
    expect_welds INTEGER DEFAULT 0,
    extraction_strategy TEXT,
    skip_extraction INTEGER DEFAULT 0
);

-- =============================================================================
-- 4. DISCIPLINE: ELECTRICAL
-- =============================================================================

CREATE TABLE IF NOT EXISTS electrical_transformers (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    kva_rating INTEGER,
    primary_voltage TEXT,
    secondary_voltage TEXT,
    phases INTEGER,
    wires INTEGER,
    frequency INTEGER,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_switchgear (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    equipment_type TEXT,
    voltage TEXT,
    current_rating INTEGER,
    frame_size INTEGER,
    trip_rating INTEGER,
    short_circuit_rating INTEGER,
    short_circuit_amps INTEGER,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_motors (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    tag TEXT NOT NULL,
    hp_rating INTEGER,
    voltage TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_abbreviations (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    abbreviation TEXT NOT NULL,
    definition TEXT,
    category TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_symbols (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    symbol_code TEXT NOT NULL,
    description TEXT,
    category TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_panels (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    panel_name TEXT NOT NULL,
    location TEXT,
    voltage TEXT,
    phases INTEGER,
    wires INTEGER,
    bus_rating TEXT,
    fed_from TEXT,
    enclosure_type TEXT,
    aic_rating TEXT,
    total_connected_current REAL,
    total_demand_current REAL,
    total_connected_kva REAL,
    total_demand_kva REAL,
    demand_factor REAL,
    panel_notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_circuits (
    id INTEGER PRIMARY KEY,
    panel_id INTEGER REFERENCES electrical_panels(id),
    sheet_id INTEGER REFERENCES sheets(id),
    circuit_number TEXT NOT NULL,
    circuit_description TEXT,
    equipment_tag TEXT,
    location TEXT,
    num_poles INTEGER,
    breaker_frame INTEGER,
    breaker_trip INTEGER,
    wire_size TEXT,
    conduit_size TEXT,
    load_kva REAL,
    load_amps REAL,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_breakers (
    id INTEGER PRIMARY KEY,
    panel_id INTEGER REFERENCES electrical_panels(id),
    sheet_id INTEGER REFERENCES sheets(id),
    circuit_number TEXT NOT NULL,
    description TEXT,
    poles INTEGER,
    frame_size INTEGER,
    trip_size INTEGER,
    wire_size TEXT,
    conduit_size TEXT,
    kva REAL,
    amps_a REAL,
    amps_b REAL,
    amps_c REAL,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_lighting_fixtures (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    fixture_type TEXT NOT NULL,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    circuit_number TEXT,
    switch_tag TEXT,
    qty INTEGER DEFAULT 1,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_switches (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    switch_tag TEXT NOT NULL,
    switch_type TEXT,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    controls_fixtures TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_sensors (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    sensor_type TEXT NOT NULL,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    controls_circuit TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS electrical_emergency_fixtures (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    fixture_type TEXT NOT NULL,
    circuit_number TEXT,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_receptacles (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    receptacle_tag TEXT,
    receptacle_type TEXT,
    voltage TEXT,
    amperage TEXT,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    circuit_number TEXT,
    panel_fed_from TEXT,
    gfci BOOLEAN DEFAULT 0,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_junction_boxes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    box_tag TEXT,
    box_type TEXT,
    location TEXT,
    grid_location TEXT,
    mounting_height TEXT,
    circuit_number TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_conduit (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    circuit_tag TEXT NOT NULL,
    conduit_size TEXT,
    conduit_type TEXT,
    wire_count INTEGER,
    wire_sizes TEXT,
    ground_wire_size TEXT,
    from_location TEXT,
    to_location TEXT,
    routing_notes TEXT,
    mounting_height TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_disconnects (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    disconnect_tag TEXT NOT NULL,
    disconnect_type TEXT,
    amperage TEXT,
    voltage TEXT,
    fused BOOLEAN,
    enclosure_type TEXT,
    serves_equipment TEXT,
    location TEXT,
    grid_location TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_motor_connections (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    equipment_tag TEXT NOT NULL,
    motor_hp REAL,
    voltage TEXT,
    phases INTEGER,
    circuit_tag TEXT,
    conduit_info TEXT,
    disconnect_tag TEXT,
    location TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS electrical_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    equipment_type TEXT,
    location TEXT,
    area TEXT,
    voltage TEXT,
    amperage TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);

-- =============================================================================
-- 5. DISCIPLINE: PLUMBING
-- =============================================================================

CREATE TABLE IF NOT EXISTS plumbing_fixtures (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    fixture_type TEXT NOT NULL,
    manufacturer TEXT,
    model TEXT,
    description TEXT,
    waste_size TEXT,
    vent_size TEXT,
    dcw_size TEXT,
    dhw_size TEXT,
    qty INTEGER DEFAULT 1,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS plumbing_risers (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    pipe_size TEXT NOT NULL,
    pipe_type TEXT,
    from_location TEXT,
    to_location TEXT,
    fixture_tag TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS plumbing_locations (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    item_tag TEXT NOT NULL,
    item_type TEXT,
    location TEXT,
    room_number TEXT,
    room_name TEXT,
    grid_location TEXT,
    pipe_size TEXT,
    pipe_material TEXT,
    invert_elevation TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS plumbing_pipes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    pipe_size TEXT NOT NULL,
    pipe_type TEXT,
    service TEXT,
    from_location TEXT,
    to_location TEXT,
    invert_elevation TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS plumbing_cleanouts (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    cleanout_tag TEXT NOT NULL,
    cleanout_type TEXT,
    location TEXT,
    pipe_size TEXT,
    confidence REAL DEFAULT 1.0
);

-- =============================================================================
-- 6. DISCIPLINE: MECHANICAL / HVAC
-- =============================================================================

CREATE TABLE IF NOT EXISTS mechanical_equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    equipment_mark TEXT NOT NULL,
    equipment_type TEXT,
    area_served TEXT,
    manufacturer TEXT,
    model TEXT,
    cfm INTEGER,
    airflow_cfm INTEGER,
    hp REAL,
    bhp REAL,
    voltage TEXT,
    phase TEXT,
    frequency TEXT,
    electrical_spec TEXT,
    mca REAL,
    mocp INTEGER,
    rpm INTEGER,
    static_pressure REAL,
    weight_lbs REAL,
    capacity_tons REAL,
    capacity_mbh REAL,
    heating_kw REAL,
    qty INTEGER DEFAULT 1,
    notes TEXT,
    specifications TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mechanical_ventilation (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    system_tag TEXT NOT NULL,
    room_number TEXT,
    room_name TEXT,
    room_area_sf INTEGER,
    occupancy_category TEXT,
    supply_cfm INTEGER,
    outdoor_air_cfm INTEGER,
    outdoor_air_percent REAL,
    people_count INTEGER,
    vav_minimum_percent INTEGER,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS air_flow_paths (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    equipment_tag TEXT NOT NULL,
    flow_type TEXT,
    flow_cfm INTEGER,
    source_location TEXT,
    destination_location TEXT,
    mode TEXT,
    confidence REAL DEFAULT 1.0
);

-- =============================================================================
-- 7. DISCIPLINE: REFRIGERATION
-- =============================================================================

CREATE TABLE IF NOT EXISTS refrigeration_pipe_stands (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    stand_number TEXT NOT NULL,
    model TEXT,
    base_type TEXT,
    upright_type TEXT,
    cross_member_1 TEXT,
    cross_member_2 TEXT,
    dimension_a REAL,
    dimension_b REAL,
    dimension_c REAL,
    dimension_d REAL,
    weight_lbs REAL,
    is_anchored INTEGER DEFAULT 0,
    notes TEXT,
    confidence REAL DEFAULT 0.95,
    UNIQUE(sheet_id, stand_number)
);

CREATE TABLE IF NOT EXISTS refrigeration_duct_stands (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    stand_number TEXT NOT NULL,
    model TEXT,
    base_type TEXT,
    upright_type TEXT,
    cross_member_1 TEXT,
    cross_member_2 TEXT,
    dimension_a REAL,
    dimension_b REAL,
    dimension_c REAL,
    dimension_d REAL,
    weight_lbs REAL,
    is_anchored INTEGER DEFAULT 0,
    notes TEXT,
    confidence REAL DEFAULT 0.95,
    UNIQUE(sheet_id, stand_number)
);

-- =============================================================================
-- 8. DISCIPLINE: SUPPORTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS support_details (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    detail_type TEXT,
    detail_label TEXT,
    member_type TEXT,
    member_size TEXT,
    max_load_lbs INTEGER,
    width_or_span_ft REAL,
    rod_size TEXT,
    back_to_back TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS supports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    support_tag TEXT NOT NULL,
    support_type TEXT,
    structural_section TEXT,
    description TEXT,
    confidence REAL DEFAULT 0.7,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);

CREATE TABLE IF NOT EXISTS support_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    support_tag TEXT NOT NULL,
    support_type TEXT,
    location_description TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);

-- =============================================================================
-- 9. DISCIPLINE: UTILITY
-- =============================================================================

CREATE TABLE IF NOT EXISTS utility_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    equipment_mark TEXT NOT NULL,
    equipment_type TEXT,
    location TEXT,
    manufacturer TEXT,
    model TEXT,
    capacity TEXT,
    design_pressure TEXT,
    dimensions TEXT,
    weight_lbs INTEGER,
    operating_weight_lbs INTEGER,
    power_voltage TEXT,
    power_hp REAL,
    qty INTEGER DEFAULT 1,
    gpm REAL,
    temperature_in REAL,
    temperature_out REAL,
    pressure_drop_psi REAL,
    steam_pressure_psi REAL,
    flow_rate_lbs_hr REAL,
    inlet_size TEXT,
    outlet_size TEXT,
    specifications TEXT,
    notes TEXT,
    contact_info TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);

-- =============================================================================
-- 10. DISCIPLINE: FIRE PROTECTION & LIFE SAFETY
-- =============================================================================

CREATE TABLE IF NOT EXISTS fire_zones (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    zone_designation TEXT NOT NULL,
    zone_area TEXT,
    room_names TEXT,
    room_numbers TEXT,
    storage_height TEXT,
    storage_type TEXT,
    ceiling_type TEXT,
    grid_bounds TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_equipment (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    equipment_type TEXT NOT NULL,
    location TEXT,
    zone_served TEXT,
    size TEXT,
    system_type TEXT,
    quantity INTEGER,
    area_designation TEXT,
    grid_location TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_systems (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    system_name TEXT NOT NULL,
    system_type TEXT,
    riser_area TEXT,
    pipe_size TEXT,
    zone_count INTEGER,
    zones_served TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_piping (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    line_type TEXT,
    size TEXT,
    from_location TEXT,
    to_location TEXT,
    description TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_valves (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    valve_type TEXT,
    size TEXT,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_notes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    note_number TEXT,
    note_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fire_protection_symbols (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    symbol_code TEXT NOT NULL,
    description TEXT,
    category TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS life_safety_exits (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    exit_designation TEXT,
    exit_width TEXT,
    exit_type TEXT,
    location TEXT,
    is_accessible INTEGER DEFAULT 0,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_safety_egress_paths (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    from_location TEXT,
    to_location TEXT,
    travel_distance TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_safety_occupancy (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    room_number TEXT,
    room_name TEXT,
    occupant_load INTEGER,
    occupancy_type TEXT,
    area TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_safety_fire_barriers (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    barrier_type TEXT,
    rating TEXT,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_safety_features (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    feature_type TEXT,
    location TEXT,
    description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS life_safety_notes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    note_number TEXT,
    note_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 11. DISCIPLINE: ENVIRONMENTAL
-- =============================================================================

CREATE TABLE IF NOT EXISTS environmental_zones (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    room_number TEXT,
    room_name TEXT,
    zone_type TEXT,
    zone_classification TEXT,
    floor_finish_notes TEXT,
    wall_finish_notes TEXT,
    ceiling_finish_notes TEXT,
    grid_location TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS environmental_notes (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    zone_classification TEXT,
    category TEXT,
    note_text TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 12. DISCIPLINE: CIVIL & SURVEY
-- =============================================================================

CREATE TABLE IF NOT EXISTS civil_demolition_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    area_id TEXT,
    demolition_type TEXT,
    description TEXT,
    location TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_erosion_control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    control_id TEXT,
    measure_type TEXT,
    description TEXT,
    location TEXT,
    installation_sequence INTEGER,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_site_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    limit_type TEXT,
    description TEXT,
    area_acres REAL,
    perimeter_length REAL,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_construction_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    sequence_number INTEGER,
    phase TEXT,
    activity TEXT,
    description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_control_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    dimension_type TEXT,
    value REAL,
    unit TEXT DEFAULT 'ft',
    from_point TEXT,
    to_point TEXT,
    description TEXT,
    grid_reference TEXT,
    is_radius INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_reference_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    point_id TEXT,
    point_type TEXT,
    x_coordinate REAL,
    y_coordinate REAL,
    elevation REAL,
    description TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_dimension_control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    dimension_type TEXT,
    dimension_value REAL,
    dimension_units TEXT DEFAULT 'feet',
    from_point TEXT,
    to_point TEXT,
    description TEXT,
    grid_reference TEXT,
    angle_degrees REAL,
    radius_value REAL,
    coordinate_x REAL,
    coordinate_y REAL,
    elevation REAL,
    reference_type TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_grid_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    grid_id TEXT,
    grid_type TEXT,
    orientation TEXT,
    coordinate REAL,
    description TEXT,
    confidence REAL DEFAULT 0.95,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_control_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    point_id TEXT,
    point_type TEXT,
    x_coordinate REAL,
    y_coordinate REAL,
    elevation REAL,
    description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_spot_elevations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    location_description TEXT,
    elevation REAL,
    elevation_type TEXT,
    grid_reference TEXT,
    x_coordinate REAL,
    y_coordinate REAL,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_contours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    contour_type TEXT,
    elevation REAL,
    interval REAL,
    notes TEXT,
    confidence REAL DEFAULT 0.85,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_drainage_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    feature_id TEXT,
    feature_type TEXT,
    rim_elevation REAL,
    invert_elevation REAL,
    invert_elevation_in REAL,
    invert_elevation_out REAL,
    size TEXT,
    material TEXT,
    slope_percent REAL,
    flow_direction TEXT,
    grid_reference TEXT,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_grading_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    note_type TEXT,
    note_text TEXT,
    location_reference TEXT,
    applies_to TEXT,
    confidence REAL DEFAULT 0.95,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_grading_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    area_id TEXT,
    area_type TEXT,
    description TEXT,
    min_elevation REAL,
    max_elevation REAL,
    slope_ratio TEXT,
    area_sqft REAL,
    notes TEXT,
    confidence REAL DEFAULT 0.85,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_slopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    slope_id TEXT,
    slope_type TEXT,
    slope_ratio TEXT,
    top_elevation REAL,
    bottom_elevation REAL,
    height REAL,
    length REAL,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.85,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_utility_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    line_type TEXT NOT NULL,
    size TEXT,
    material TEXT,
    specification TEXT,
    from_location TEXT,
    to_location TEXT,
    length_ft REAL,
    depth_ft REAL,
    slope_percent REAL,
    grid_reference TEXT,
    location_description TEXT,
    owner TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_manholes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    manhole_id TEXT,
    manhole_type TEXT,
    rim_elevation REAL,
    invert_in_elevation REAL,
    invert_out_elevation REAL,
    depth_ft REAL,
    diameter TEXT,
    material TEXT,
    grid_reference TEXT,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_valves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    valve_id TEXT,
    valve_type TEXT,
    size TEXT,
    line_type TEXT,
    buried_depth_ft REAL,
    grid_reference TEXT,
    location_description TEXT,
    owner TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS civil_utility_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER REFERENCES sheets(id),
    connection_id TEXT,
    connection_type TEXT,
    size TEXT,
    utility_type TEXT,
    connects_from TEXT,
    connects_to TEXT,
    grid_reference TEXT,
    location_description TEXT,
    notes TEXT,
    confidence REAL DEFAULT 0.9,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Survey Tables

CREATE TABLE IF NOT EXISTS survey_property_boundaries (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    owner TEXT,
    area_acres REAL,
    description TEXT,
    recording_reference TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_easements (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    easement_type TEXT,
    width_ft REAL,
    beneficiary TEXT,
    recording_reference TEXT,
    description TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_utilities (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    utility_type TEXT,
    description TEXT,
    owner TEXT,
    location_description TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_benchmarks (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    benchmark_id TEXT,
    elevation REAL,
    datum TEXT,
    description TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_contours (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    elevation_min REAL,
    elevation_max REAL,
    contour_interval REAL,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_site_features (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    feature_type TEXT,
    description TEXT,
    elevation REAL,
    location_description TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS survey_jurisdiction (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    jurisdiction_name TEXT,
    boundary_description TEXT,
    confidence REAL DEFAULT 1.0
);

-- =============================================================================
-- 13. GENERAL DRAWING DATA
-- =============================================================================

CREATE TABLE IF NOT EXISTS detail_drawings (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    detail_number TEXT NOT NULL,
    detail_title TEXT NOT NULL,
    detail_scale TEXT,
    description TEXT,
    material_specifications TEXT,
    dimensions TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0,
    UNIQUE(sheet_id, detail_number)
);

CREATE TABLE IF NOT EXISTS drawing_details (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    detail_id TEXT NOT NULL,
    detail_title TEXT,
    detail_type TEXT,
    description TEXT,
    materials TEXT,
    dimensions TEXT,
    notes TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS drawing_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER,
    drawing_number TEXT,
    note_type TEXT,
    note_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id)
);

CREATE TABLE IF NOT EXISTS drawing_abbreviations (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    abbreviation TEXT NOT NULL,
    full_text TEXT NOT NULL,
    category TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS design_criteria (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    criteria_type TEXT NOT NULL,
    parameter TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT,
    condition TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS insulation_specs (
    id INTEGER PRIMARY KEY,
    sheet_id INTEGER REFERENCES sheets(id),
    spec_name TEXT NOT NULL,
    location_type TEXT,
    ambient_temp_f INTEGER,
    ambient_rh_percent INTEGER,
    wind_velocity_mph REAL,
    material_type TEXT,
    outer_surface TEXT,
    emissivity REAL,
    design_criteria TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS insulation_thickness (
    id INTEGER PRIMARY KEY,
    spec_id INTEGER REFERENCES insulation_specs(id),
    pipe_size TEXT NOT NULL,
    temp_range TEXT NOT NULL,
    thickness_inches REAL,
    confidence REAL DEFAULT 1.0
);

-- =============================================================================
-- 14. DOCUMENT INTAKE LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_intake_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    document_type TEXT,
    handler TEXT,
    action TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS onedrive_sync_log (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_path TEXT,
    source_folder TEXT,
    destination_path TEXT,
    file_size INTEGER,
    action TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
