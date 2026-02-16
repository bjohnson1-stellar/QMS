"""
Seed ASME Section IX / QB lookup tables with reference data.

Populates weld_valid_* tables used for extraction validation and form generation.
Data sources: ASME BPVC Section IX (QW/QB articles), AWS B2.1, and existing
importer.py reference dictionaries.
"""

import sqlite3
from typing import Any, Dict, List, Tuple

from qms.core import get_db, get_logger

logger = get_logger("qms.welding.seed_lookups")


# ---------------------------------------------------------------------------
# ASME IX Welding Processes (QW-492)
# ---------------------------------------------------------------------------

PROCESSES: List[Tuple[str, str, str, str]] = [
    # (code, name, category, aws_letter)
    ("SMAW", "Shielded Metal Arc Welding", "welding", "S"),
    ("GTAW", "Gas Tungsten Arc Welding", "welding", "G"),
    ("GMAW", "Gas Metal Arc Welding", "welding", "GM"),
    ("GMAW-S", "GMAW - Short Circuit Transfer", "welding", "GM"),
    ("GMAW-P", "GMAW - Pulsed Transfer", "welding", "GM"),
    ("FCAW", "Flux Cored Arc Welding", "welding", "FC"),
    ("FCAW-G", "FCAW - Gas Shielded", "welding", "FC"),
    ("FCAW-S", "FCAW - Self Shielded", "welding", "FC"),
    ("SAW", "Submerged Arc Welding", "welding", "SA"),
    ("PAW", "Plasma Arc Welding", "welding", "PA"),
    ("ESW", "Electroslag Welding", "welding", "ES"),
    ("EGW", "Electrogas Welding", "welding", "EG"),
    ("OFW", "Oxyfuel Welding", "welding", "OF"),
    ("SW", "Stud Welding", "welding", "SW"),
    ("TB", "Torch Brazing", "brazing", "TB"),
    ("FB", "Furnace Brazing", "brazing", "FB"),
    ("IB", "Induction Brazing", "brazing", "IB"),
    ("RB", "Resistance Brazing", "brazing", "RB"),
    ("DB", "Dip Brazing", "brazing", "DB"),
    ("IRB", "Infrared Brazing", "brazing", "IRB"),
]

# ---------------------------------------------------------------------------
# P-Numbers (QW/QB-422) — Base metal groupings
# ---------------------------------------------------------------------------

P_NUMBERS: List[Tuple[int, int | None, str, str]] = [
    # (p_number, group_number, material_type, common_specs)
    (1, 1, "Carbon Steel", "A36, A53 Gr B, A106 Gr B, A516 Gr 70"),
    (1, 2, "Carbon Steel", "A333 Gr 6, A350 Gr LF2"),
    (1, 3, "Carbon Steel", "A516 Gr 55, A285 Gr C"),
    (1, 4, "Carbon Steel", "A105, A181 Cl 70"),
    (3, 1, "Alloy Steel (Cr ≤ ½%)", "A335 P1, A217 WC1"),
    (3, 2, "Alloy Steel (½-2% Cr)", "A335 P11, A387 Gr 11"),
    (3, 3, "Alloy Steel (2¼% Cr)", "A335 P22, A387 Gr 22"),
    (4, 1, "Alloy Steel (Cr-Mo)", "A335 P5, A213 T5"),
    (5, 1, "Alloy Steel 5A (4-6% Cr)", "A335 P5b, A213 T5b"),
    (5, 2, "Alloy Steel 5B (5-9% Cr)", "A213 T9"),
    (6, 1, "Martensitic Stainless", "A240 Type 410, A268 TP410"),
    (7, 1, "Ferritic Stainless", "A240 Type 405, A268 TP430"),
    (8, 1, "Austenitic Stainless (304)", "A240 Type 304, A312 TP304, A358 Type 304"),
    (8, 2, "Austenitic Stainless (316)", "A240 Type 316, A312 TP316"),
    (8, 3, "Austenitic Stainless (Other)", "A240 Type 317, A312 TP321, TP347"),
    (9, 1, "Nickel Alloy Steel (2-1/4 Ni)", "A203 Gr A/B"),
    (9, 2, "Nickel Alloy Steel (3-1/2 Ni)", "A203 Gr D/E"),
    (10, 1, "Mn-V Steel", "A225 Gr C"),
    (11, 1, "Low Alloy Steel (various)", "A333 Gr 1"),
    (21, 1, "Aluminum (1xxx)", "1060, 1100"),
    (22, 1, "Aluminum (3xxx)", "3003, 3004"),
    (23, 1, "Aluminum (5xxx, ≤4% Mg)", "5052, 5154"),
    (25, 1, "Aluminum (6xxx)", "6061, 6063"),
    (31, 1, "Copper", "C10200, C12200"),
    (32, 1, "Copper-Zinc (Brass)", "C26000, C27000"),
    (33, 1, "Copper-Silicon (Bronze)", "C65500"),
    (34, 1, "Copper-Nickel", "C70600, C71500"),
    (35, 1, "Copper-Aluminum", "C61400"),
    (41, 1, "Nickel Alloy", "Alloy 200/201"),
    (42, 1, "Nickel-Copper (Monel)", "Alloy 400, K-500"),
    (43, 1, "Nickel-Cr-Fe (Inconel)", "Alloy 600, 601, 625"),
    (44, 1, "Nickel-Mo (Hastelloy B)", "Alloy B-2"),
    (45, 1, "Nickel-Cr-Mo (Hastelloy C)", "Alloy C-276, C-22"),
    (51, 1, "Titanium", "Gr 1, Gr 2"),
    (52, 1, "Titanium Alloys", "Gr 5, Ti-6Al-4V"),
    (61, 1, "Zirconium", "Zr 702"),
    (62, 1, "Zirconium Alloys", "Zr 705"),
]

# ---------------------------------------------------------------------------
# F-Numbers (QW-432) — Filler metal groupings
# ---------------------------------------------------------------------------

F_NUMBERS: List[Tuple[int, str, str]] = [
    # (f_number, description, process_category)
    (1, "E60XX, E70XX electrodes (except low-hydrogen)", "SMAW"),
    (2, "E60XX, E70XX electrodes (low-hydrogen, iron powder)", "SMAW"),
    (3, "E60XX, E70XX electrodes (high cellulose)", "SMAW"),
    (4, "E70XX, E80XX electrodes (low-hydrogen)", "SMAW"),
    (5, "E9015, E9018, E10015-X, E10018-X, E11018-X, E12018-X electrodes", "SMAW"),
    (6, "ER70S-X, ER80S-X, ER308L, ER309L, ER316L solid wires", "GTAW/GMAW"),
    (21, "Bare aluminum (1xxx, 4xxx)", "GTAW/GMAW"),
    (22, "Bare aluminum (4043, 4047)", "GTAW/GMAW"),
    (23, "Bare aluminum (5183, 5356, 5556)", "GTAW/GMAW"),
    (31, "Copper and copper alloy bare wire", "GTAW/GMAW"),
    (32, "Copper-zinc alloy bare wire", "GTAW/GMAW"),
    (33, "Copper-nickel alloy bare wire", "GTAW/GMAW"),
    (34, "Copper-silicon alloy bare wire", "GTAW/GMAW"),
    (36, "Flux-cored copper alloy", "FCAW"),
    (41, "Nickel and Ni alloy bare wire", "GTAW/GMAW"),
    (43, "Ni-Cr-Fe alloy bare wire (Inconel)", "GTAW/GMAW"),
    (44, "Ni-Mo alloy bare wire (Hastelloy)", "GTAW/GMAW"),
    (45, "Ni-Cr-Mo alloy bare wire", "GTAW/GMAW"),
    (51, "Titanium bare wire", "GTAW/GMAW"),
    (61, "Zirconium bare wire", "GTAW/GMAW"),
]

# ---------------------------------------------------------------------------
# A-Numbers (QW-442) — Weld metal chemical analysis classification
# ---------------------------------------------------------------------------

A_NUMBERS: List[Tuple[int, str, str]] = [
    # (a_number, description, weld_deposit_type)
    (1, "Carbon Steel (C ≤ 0.20%)", "Mild steel"),
    (2, "Carbon-Molybdenum", "Low alloy"),
    (3, "Chrome (0.4-2%)-Molybdenum", "Low alloy"),
    (4, "Chrome (2-6%)-Molybdenum", "Low alloy"),
    (5, "Chrome (6-10.5%)-Molybdenum", "Low alloy"),
    (6, "Chrome-Martensitic (11-15%)", "Stainless"),
    (7, "Chrome-Ferritic (11-30%)", "Stainless"),
    (8, "Chrome-Nickel Austenitic (14.5-30% Cr)", "Stainless"),
    (9, "Chrome-Nickel Austenitic (25-30% Cr)", "Stainless"),
    (10, "Nickel up to 4%", "Low alloy"),
    (11, "Manganese-Molybdenum", "Low alloy"),
    (12, "Nickel-Chrome-Molybdenum", "Low alloy"),
]

# ---------------------------------------------------------------------------
# Positions (QW-461)
# ---------------------------------------------------------------------------

POSITIONS: List[Tuple[str, str, str, str]] = [
    # (code, description, joint_type, qualifies_for)
    ("1G", "Flat - Groove", "groove", "1G"),
    ("2G", "Horizontal - Groove", "groove", "1G, 2G"),
    ("3G", "Vertical - Groove", "groove", "1G, 3G"),
    ("4G", "Overhead - Groove", "groove", "1G, 4G"),
    ("5G", "Horizontal Fixed Pipe - Groove", "groove", "1G, 2G, 5G"),
    ("6G", "45° Fixed Pipe - Groove", "groove", "1G, 2G, 3G, 4G, 5G, 6G"),
    ("6GR", "Restricted 45° Fixed Pipe - Groove", "groove", "1G, 2G, 3G, 4G, 5G, 6G, 6GR"),
    ("1F", "Flat - Fillet", "fillet", "1F"),
    ("2F", "Horizontal - Fillet", "fillet", "1F, 2F"),
    ("3F", "Vertical - Fillet", "fillet", "1F, 2F, 3F"),
    ("4F", "Overhead - Fillet", "fillet", "1F, 2F, 3F, 4F"),
    ("5F", "Horizontal Fixed Pipe - Fillet", "fillet", "1F, 2F, 3F, 4F, 5F"),
]

# ---------------------------------------------------------------------------
# SFA Specifications (common)
# ---------------------------------------------------------------------------

SFA_SPECS: List[Tuple[str, str, str]] = [
    # (spec_number, title, filler_type)
    ("SFA-5.1", "Carbon Steel Covered Electrodes", "SMAW electrode"),
    ("SFA-5.4", "Stainless Steel Covered Electrodes", "SMAW electrode"),
    ("SFA-5.5", "Low-Alloy Steel Covered Electrodes", "SMAW electrode"),
    ("SFA-5.6", "Copper and Copper Alloy Covered Electrodes", "SMAW electrode"),
    ("SFA-5.8", "Filler Metals for Brazing and Braze Welding", "Brazing filler"),
    ("SFA-5.9", "Bare Stainless Steel Welding Electrodes and Rods", "Bare wire"),
    ("SFA-5.11", "Nickel and Nickel Alloy Covered Electrodes", "SMAW electrode"),
    ("SFA-5.14", "Nickel and Nickel Alloy Bare Welding Electrodes and Rods", "Bare wire"),
    ("SFA-5.17", "Carbon Steel Electrodes and Fluxes for SAW", "SAW electrode/flux"),
    ("SFA-5.18", "Carbon Steel Electrodes and Rods for GTAW/GMAW", "Bare wire"),
    ("SFA-5.20", "Carbon Steel Electrodes for FCAW", "Flux cored wire"),
    ("SFA-5.22", "Stainless Steel Electrodes for FCAW and Rods for GTAW", "Bare wire/flux cored"),
    ("SFA-5.23", "Low-Alloy Steel Electrodes and Fluxes for SAW", "SAW electrode/flux"),
    ("SFA-5.28", "Low-Alloy Steel Electrodes and Rods for GTAW/GMAW", "Bare wire"),
    ("SFA-5.29", "Low-Alloy Steel Electrodes for FCAW", "Flux cored wire"),
    ("SFA-5.36", "Carbon and Low-Alloy Steel Flux Cored Electrodes for FCAW/GMAW", "Flux cored wire"),
]

# ---------------------------------------------------------------------------
# AWS Classification examples
# ---------------------------------------------------------------------------

AWS_CLASSES: List[Tuple[str, str, int, int | None, str]] = [
    # (aws_class, sfa_spec, f_number, a_number, description)
    ("E6010", "SFA-5.1", 3, 1, "High-cellulose sodium — deep penetration"),
    ("E6011", "SFA-5.1", 3, 1, "High-cellulose potassium — AC capable"),
    ("E6013", "SFA-5.1", 2, 1, "Rutile-potassium — all-position"),
    ("E7014", "SFA-5.1", 2, 1, "Iron powder titania — flat/horizontal"),
    ("E7018", "SFA-5.1", 4, 1, "Low-hydrogen iron powder — structural"),
    ("E7024", "SFA-5.1", 2, 1, "Iron powder titania — high deposition"),
    ("E7028", "SFA-5.1", 4, 1, "Low-hydrogen iron powder — horizontal fillet"),
    ("E8018-B2", "SFA-5.5", 4, 3, "Low-hydrogen Cr-Mo — 1¼ Cr-½ Mo"),
    ("E8018-C1", "SFA-5.5", 4, 10, "Low-hydrogen Ni — 2½ Ni"),
    ("E9018-B3", "SFA-5.5", 4, 4, "Low-hydrogen Cr-Mo — 2¼ Cr-1 Mo"),
    ("E308L-16", "SFA-5.4", 4, 8, "Austenitic SS — 304L weld deposit"),
    ("E309L-16", "SFA-5.4", 4, 8, "Austenitic SS — 309L dissimilar metals"),
    ("E316L-16", "SFA-5.4", 4, 8, "Austenitic SS — 316L weld deposit"),
    ("ER70S-2", "SFA-5.18", 6, 1, "Carbon steel bare wire — triple deoxidized"),
    ("ER70S-6", "SFA-5.18", 6, 1, "Carbon steel bare wire — silicon/manganese"),
    ("ER80S-Ni1", "SFA-5.28", 6, 10, "Low-alloy wire — 1% Ni"),
    ("ER308L", "SFA-5.9", 6, 8, "Austenitic SS bare wire — 304L deposits"),
    ("ER309L", "SFA-5.9", 6, 8, "Austenitic SS bare wire — 309L dissimilar"),
    ("ER316L", "SFA-5.9", 6, 8, "Austenitic SS bare wire — 316L deposits"),
    ("E71T-1", "SFA-5.20", 6, 1, "Carbon steel FCAW — gas shielded"),
    ("E81T1-Ni1", "SFA-5.29", 6, 10, "Low-alloy FCAW — 1% Ni"),
]

# ---------------------------------------------------------------------------
# Current types, filler forms, joint types, groove types, bead types, gases
# ---------------------------------------------------------------------------

CURRENT_TYPES: List[Tuple[str, str, str]] = [
    ("DCEP", "DC Electrode Positive (reverse polarity)", "SMAW, GMAW, FCAW, SAW"),
    ("DCEN", "DC Electrode Negative (straight polarity)", "GTAW, SAW"),
    ("AC", "Alternating Current", "SMAW, GTAW, SAW"),
    ("DC", "Direct Current (polarity unspecified)", "all"),
    ("Pulsed", "Pulsed DC", "GTAW, GMAW"),
]

FILLER_FORMS: List[Tuple[str, str]] = [
    ("electrode", "Covered electrode (SMAW)"),
    ("bare_wire", "Bare solid wire (GTAW/GMAW)"),
    ("flux_cored", "Flux-cored tubular wire (FCAW)"),
    ("metal_cored", "Metal-cored tubular wire"),
    ("strip", "Strip electrode (SAW overlay)"),
    ("insert", "Consumable insert"),
    ("powder", "Metal powder additive"),
    ("rod", "Bare welding rod"),
]

JOINT_TYPES: List[Tuple[str, str, str]] = [
    ("butt", "Butt Joint", "groove"),
    ("corner", "Corner Joint", "groove/fillet"),
    ("tee", "T-Joint", "fillet"),
    ("lap", "Lap Joint", "fillet"),
    ("edge", "Edge Joint", "groove"),
    ("branch", "Branch Connection", "groove/fillet"),
    ("socket", "Socket Weld", "fillet"),
]

GROOVE_TYPES: List[Tuple[str, str]] = [
    ("V", "Single-V Groove"),
    ("double_V", "Double-V Groove"),
    ("U", "Single-U Groove"),
    ("double_U", "Double-U Groove"),
    ("J", "Single-J Groove"),
    ("double_J", "Double-J Groove"),
    ("bevel", "Single-Bevel Groove"),
    ("double_bevel", "Double-Bevel Groove"),
    ("square", "Square Groove"),
    ("flare_V", "Flare-V Groove"),
    ("flare_bevel", "Flare-Bevel Groove"),
]

BEAD_TYPES: List[Tuple[str, str]] = [
    ("stringer", "Stringer Bead (no appreciable weave)"),
    ("weave", "Weave Bead (oscillating motion)"),
]

GAS_TYPES: List[Tuple[str, str, str, str]] = [
    # (code, name, chemical_symbol, category)
    ("Ar", "Argon", "Ar", "inert"),
    ("He", "Helium", "He", "inert"),
    ("CO2", "Carbon Dioxide", "CO2", "active"),
    ("O2", "Oxygen", "O2", "active"),
    ("N2", "Nitrogen", "N2", "inert"),
    ("H2", "Hydrogen", "H2", "reducing"),
    ("Ar/CO2", "Argon-CO2 Mix (typically 75/25)", "Ar+CO2", "mixed"),
    ("Ar/O2", "Argon-Oxygen Mix (typically 98/2)", "Ar+O2", "mixed"),
    ("Ar/He", "Argon-Helium Mix", "Ar+He", "mixed"),
    ("Ar/H2", "Argon-Hydrogen Mix", "Ar+H2", "mixed"),
    ("tri-mix", "Argon-Helium-CO2 Mix", "Ar+He+CO2", "mixed"),
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def _insert_ignore(conn: sqlite3.Connection, table: str, columns: List[str],
                   rows: List[Tuple]) -> int:
    """INSERT OR IGNORE rows into table. Returns count inserted."""
    placeholders = ", ".join(["?"] * len(columns))
    col_str = ", ".join(columns)
    sql = f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({placeholders})"
    count = 0
    for row in rows:
        cursor = conn.execute(sql, row)
        count += cursor.rowcount
    return count


def seed_processes(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_processes",
                          ["code", "name", "category", "aws_letter"],
                          PROCESSES)


def seed_p_numbers(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_p_numbers",
                          ["p_number", "group_number", "material_type", "common_specs"],
                          P_NUMBERS)


def seed_f_numbers(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_f_numbers",
                          ["f_number", "description", "process_category"],
                          F_NUMBERS)


def seed_a_numbers(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_a_numbers",
                          ["a_number", "description", "weld_deposit_type"],
                          A_NUMBERS)


def seed_positions(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_positions",
                          ["code", "description", "joint_type", "qualifies_for"],
                          POSITIONS)


def seed_sfa_specs(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_sfa_specs",
                          ["spec_number", "title", "filler_type"],
                          SFA_SPECS)


def seed_aws_classes(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_aws_classes",
                          ["aws_class", "sfa_spec", "f_number", "a_number", "description"],
                          AWS_CLASSES)


def seed_current_types(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_current_types",
                          ["code", "description", "compatible_processes"],
                          CURRENT_TYPES)


def seed_filler_forms(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_filler_forms",
                          ["code", "description"],
                          FILLER_FORMS)


def seed_joint_types(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_joint_types",
                          ["code", "description", "category"],
                          JOINT_TYPES)


def seed_groove_types(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_groove_types",
                          ["code", "description"],
                          GROOVE_TYPES)


def seed_bead_types(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_bead_types",
                          ["code", "description"],
                          BEAD_TYPES)


def seed_gas_types(conn: sqlite3.Connection) -> int:
    return _insert_ignore(conn, "weld_valid_gas_types",
                          ["code", "name", "chemical_symbol", "category"],
                          GAS_TYPES)


def seed_all_lookups(conn: sqlite3.Connection | None = None, force: bool = False) -> Dict[str, int]:
    """
    Populate all ASME IX lookup tables.

    Args:
        conn: Database connection. Opens one if None.
        force: If True, delete existing data and re-seed.

    Returns:
        Dict mapping table name to count of rows inserted.
    """
    own_conn = conn is None
    if own_conn:
        db_ctx = get_db()
        conn = db_ctx.__enter__()

    try:
        seeders = [
            ("weld_valid_processes", seed_processes),
            ("weld_valid_p_numbers", seed_p_numbers),
            ("weld_valid_f_numbers", seed_f_numbers),
            ("weld_valid_a_numbers", seed_a_numbers),
            ("weld_valid_positions", seed_positions),
            ("weld_valid_sfa_specs", seed_sfa_specs),
            ("weld_valid_aws_classes", seed_aws_classes),
            ("weld_valid_current_types", seed_current_types),
            ("weld_valid_filler_forms", seed_filler_forms),
            ("weld_valid_joint_types", seed_joint_types),
            ("weld_valid_groove_types", seed_groove_types),
            ("weld_valid_bead_types", seed_bead_types),
            ("weld_valid_gas_types", seed_gas_types),
        ]

        results: Dict[str, int] = {}
        for table_name, seeder in seeders:
            if force:
                conn.execute(f"DELETE FROM {table_name}")
            count = seeder(conn)
            results[table_name] = count
            logger.info("Seeded %s: %d rows", table_name, count)

        conn.commit()
        total = sum(results.values())
        logger.info("Total seeded: %d rows across %d tables", total, len(results))
        return results

    finally:
        if own_conn:
            db_ctx.__exit__(None, None, None)


def get_valid_values(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    """
    Query all lookup tables and return valid values for extraction validation.

    Returns:
        Dict mapping category to list of valid values/codes.
    """
    result: Dict[str, List[str]] = {}

    queries = {
        "processes": "SELECT code FROM weld_valid_processes",
        "p_numbers": "SELECT DISTINCT p_number FROM weld_valid_p_numbers",
        "f_numbers": "SELECT DISTINCT f_number FROM weld_valid_f_numbers",
        "a_numbers": "SELECT a_number FROM weld_valid_a_numbers",
        "positions": "SELECT code FROM weld_valid_positions",
        "sfa_specs": "SELECT spec_number FROM weld_valid_sfa_specs",
        "aws_classes": "SELECT aws_class FROM weld_valid_aws_classes",
        "current_types": "SELECT code FROM weld_valid_current_types",
        "filler_forms": "SELECT code FROM weld_valid_filler_forms",
        "joint_types": "SELECT code FROM weld_valid_joint_types",
        "groove_types": "SELECT code FROM weld_valid_groove_types",
        "bead_types": "SELECT code FROM weld_valid_bead_types",
        "gas_types": "SELECT code FROM weld_valid_gas_types",
    }

    for key, sql in queries.items():
        try:
            rows = conn.execute(sql).fetchall()
            result[key] = [str(r[0]) for r in rows]
        except Exception:
            result[key] = []

    return result
