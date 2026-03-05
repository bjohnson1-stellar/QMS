"""
License schema migrations — incremental column additions.

Called from core/db.py migrate_all().
"""

import sqlite3
import uuid


def _gen_id() -> str:
    return str(uuid.uuid4())


def run_license_migrations(conn: sqlite3.Connection):
    """Add columns that don't exist yet in state_licenses."""
    # Get existing columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(state_licenses)").fetchall()}

    if "reciprocal_state" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN reciprocal_state TEXT")

    if "association_date" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN association_date TEXT")

    if "disassociation_date" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN disassociation_date TEXT")

    if "business_entity" not in cols:
        conn.execute("ALTER TABLE state_licenses ADD COLUMN business_entity TEXT")
        # Backfill from holder_name for existing rows
        conn.execute(
            "UPDATE state_licenses SET business_entity = holder_name "
            "WHERE business_entity IS NULL"
        )

    # Remove NOT NULL + CHECK on holder_type (SQLite requires table rebuild)
    _relax_holder_type_constraint(conn)

    # Phase 2 tables
    _create_phase2_tables(conn)
    _seed_license_boards(conn)
    _seed_scope_categories(conn)

    conn.commit()


def _relax_holder_type_constraint(conn: sqlite3.Connection):
    """Rebuild state_licenses to make holder_type nullable (no CHECK)."""
    # Check if holder_type still has NOT NULL constraint
    for row in conn.execute("PRAGMA table_info(state_licenses)").fetchall():
        # row: (cid, name, type, notnull, dflt_value, pk)
        if row[1] == "holder_type" and row[3] == 1:  # notnull=1
            break
    else:
        return  # Already relaxed

    # Get current column order
    col_info = conn.execute("PRAGMA table_info(state_licenses)").fetchall()
    col_names = [r[1] for r in col_info]

    conn.execute("PRAGMA foreign_keys = OFF")

    # Drop dependent view first
    conn.execute("DROP VIEW IF EXISTS v_expiring_licenses")

    conn.execute("""
        CREATE TABLE state_licenses_new (
            id              TEXT PRIMARY KEY,
            holder_type     TEXT,
            employee_id     TEXT,
            business_entity TEXT,
            state_code      TEXT NOT NULL,
            license_type    TEXT NOT NULL,
            license_number  TEXT NOT NULL,
            holder_name     TEXT NOT NULL DEFAULT '',
            issued_date     TEXT,
            expiration_date TEXT,
            status          TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','expired','pending','revoked','disassociation')),
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            created_by      TEXT,
            reciprocal_state TEXT,
            association_date TEXT,
            disassociation_date TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Copy data — map columns that exist in both old and new
    new_cols = [
        "id", "holder_type", "employee_id", "business_entity", "state_code",
        "license_type", "license_number", "holder_name", "issued_date",
        "expiration_date", "status", "notes", "created_at", "updated_at",
        "created_by", "reciprocal_state", "association_date", "disassociation_date",
    ]
    shared = [c for c in new_cols if c in col_names]
    cols_csv = ", ".join(shared)

    conn.execute(f"INSERT INTO state_licenses_new ({cols_csv}) SELECT {cols_csv} FROM state_licenses")
    conn.execute("DROP TABLE state_licenses")
    conn.execute("ALTER TABLE state_licenses_new RENAME TO state_licenses")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_state_code ON state_licenses(state_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_status ON state_licenses(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_licenses_expiration ON state_licenses(expiration_date)")

    # Recreate the view
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_expiring_licenses AS
        SELECT sl.*,
            CASE
                WHEN sl.expiration_date IS NULL THEN NULL
                ELSE CAST(julianday(sl.expiration_date) - julianday('now') AS INTEGER)
            END AS days_until_expiry
        FROM state_licenses sl
        WHERE sl.status = 'active'
    """)

    conn.execute("PRAGMA foreign_keys = ON")


# ---------------------------------------------------------------------------
# Phase 2 — new tables, seed data
# ---------------------------------------------------------------------------

def _create_phase2_tables(conn: sqlite3.Connection):
    """Create Phase 2 tables if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_license_boards (
            state_code  TEXT PRIMARY KEY,
            board_name  TEXT NOT NULL,
            website_url TEXT,
            phone       TEXT,
            notes       TEXT,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scope_categories (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_scope_map (
            license_id TEXT NOT NULL,
            scope_id   TEXT NOT NULL,
            PRIMARY KEY (license_id, scope_id),
            FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE,
            FOREIGN KEY (scope_id) REFERENCES scope_categories(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ce_requirements (
            id                    TEXT PRIMARY KEY,
            state_code            TEXT NOT NULL,
            license_type          TEXT NOT NULL,
            hours_required        REAL NOT NULL,
            period_months         INTEGER NOT NULL,
            provider_requirements TEXT,
            notes                 TEXT,
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
            created_by            TEXT,
            UNIQUE(state_code, license_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ce_credits (
            id               TEXT PRIMARY KEY,
            employee_id      TEXT NOT NULL,
            license_id       TEXT NOT NULL,
            provider         TEXT,
            course_name      TEXT NOT NULL,
            hours            REAL NOT NULL,
            completion_date  TEXT NOT NULL,
            certificate_file TEXT,
            status           TEXT NOT NULL DEFAULT 'approved'
                             CHECK (status IN ('approved', 'pending', 'rejected')),
            notes            TEXT,
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
            created_by       TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ce_credits_license ON ce_credits(license_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ce_credits_employee ON ce_credits(employee_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ce_requirements_state ON ce_requirements(state_code)")


def _seed_license_boards(conn: sqlite3.Connection):
    """Seed state licensing board data (skip if already populated)."""
    existing = conn.execute("SELECT COUNT(*) FROM state_license_boards").fetchone()[0]
    if existing > 0:
        return

    boards = [
        ("AL", "Alabama Licensing Board for General Contractors", "https://genconbd.alabama.gov", "(334) 272-5030"),
        ("AK", "Alaska Division of Corporations, Business and Professional Licensing", "https://www.commerce.alaska.gov/web/cbpl", "(907) 465-2550"),
        ("AZ", "Arizona Registrar of Contractors", "https://roc.az.gov", "(602) 542-1525"),
        ("AR", "Arkansas Contractors Licensing Board", "https://www.aclb.arkansas.gov", "(501) 372-4661"),
        ("CA", "California Contractors State License Board", "https://www.cslb.ca.gov", "(800) 321-2752"),
        ("CO", "Colorado Department of Regulatory Agencies", "https://dora.colorado.gov", "(303) 894-7855"),
        ("CT", "Connecticut Department of Consumer Protection", "https://portal.ct.gov/DCP", "(860) 713-6100"),
        ("DE", "Delaware Division of Professional Regulation", "https://dpr.delaware.gov", "(302) 744-4500"),
        ("FL", "Florida Department of Business and Professional Regulation", "https://www.myfloridalicense.com", "(850) 487-1395"),
        ("GA", "Georgia Division of Professional Licensing", "https://sos.ga.gov/PLB", "(404) 424-9966"),
        ("HI", "Hawaii Professional and Vocational Licensing Division", "https://cca.hawaii.gov/pvl", "(808) 586-3000"),
        ("ID", "Idaho Division of Building Safety", "https://dbs.idaho.gov", "(208) 334-3950"),
        ("IL", "Illinois Department of Financial and Professional Regulation", "https://idfpr.illinois.gov", "(888) 473-4858"),
        ("IN", "Indiana Professional Licensing Agency", "https://www.in.gov/pla", "(317) 234-2086"),
        ("IA", "Iowa Division of Labor Services", "https://www.iowadivisionoflabor.gov", "(515) 725-5619"),
        ("KS", "Kansas Attorney General — Contractor Registration", "https://ag.ks.gov", "(785) 296-3751"),
        ("KY", "Kentucky Department of Housing, Buildings and Construction", "https://dhbc.ky.gov", "(502) 573-0365"),
        ("LA", "Louisiana State Licensing Board for Contractors", "https://www.lslbc.louisiana.gov", "(225) 765-2301"),
        ("ME", "Maine Department of Professional and Financial Regulation", "https://www.maine.gov/pfr", "(207) 624-8603"),
        ("MD", "Maryland Home Improvement Commission", "https://www.dllr.state.md.us/license/mhic", "(410) 230-6309"),
        ("MA", "Massachusetts Division of Professional Licensure", "https://www.mass.gov/dpl", "(617) 701-8600"),
        ("MI", "Michigan Licensing and Regulatory Affairs", "https://www.michigan.gov/lara", "(517) 241-9288"),
        ("MN", "Minnesota Department of Labor and Industry", "https://www.dli.mn.gov", "(651) 284-5005"),
        ("MS", "Mississippi State Board of Contractors", "https://www.msboc.us", "(601) 354-6161"),
        ("MO", "Missouri Division of Professional Registration", "https://pr.mo.gov", "(573) 751-0293"),
        ("MT", "Montana Department of Labor and Industry", "https://bsd.dli.mt.gov", "(406) 444-6880"),
        ("NE", "Nebraska Department of Labor", "https://dol.nebraska.gov", "(402) 471-2239"),
        ("NV", "Nevada State Contractors Board", "https://www.nscb.nv.gov", "(775) 688-1141"),
        ("NH", "New Hampshire Joint Board of Licensure and Certification", "https://www.oplc.nh.gov", "(603) 271-2219"),
        ("NJ", "New Jersey Division of Consumer Affairs", "https://www.njconsumeraffairs.gov", "(973) 504-6200"),
        ("NM", "New Mexico Regulation and Licensing Department", "https://www.rld.nm.gov", "(505) 476-4500"),
        ("NY", "New York Department of State — Division of Licensing Services", "https://dos.ny.gov", "(518) 474-4429"),
        ("NC", "North Carolina Licensing Board for General Contractors", "https://www.nclbgc.org", "(919) 571-4183"),
        ("ND", "North Dakota Secretary of State — Contractor Licensing", "https://sos.nd.gov", "(701) 328-2900"),
        ("OH", "Ohio Construction Industry Licensing Board", "https://com.ohio.gov/cilo", "(614) 644-3493"),
        ("OK", "Oklahoma Construction Industries Board", "https://cib.ok.gov", "(405) 521-6550"),
        ("OR", "Oregon Construction Contractors Board", "https://www.oregon.gov/ccb", "(503) 378-4621"),
        ("PA", "Pennsylvania Attorney General — Contractor Registration", "https://www.attorneygeneral.gov", "(717) 787-3391"),
        ("RI", "Rhode Island Contractors Registration Board", "https://crb.ri.gov", "(401) 462-9645"),
        ("SC", "South Carolina Contractors Licensing Board", "https://llr.sc.gov/clb", "(803) 896-4686"),
        ("SD", "South Dakota Department of Labor and Regulation", "https://dlr.sd.gov", "(605) 773-3101"),
        ("TN", "Tennessee Board for Licensing Contractors", "https://www.tn.gov/commerce/regboards/contractors.html", "(615) 741-8307"),
        ("TX", "Texas Department of Licensing and Regulation", "https://www.tdlr.texas.gov", "(512) 463-6599"),
        ("UT", "Utah Division of Occupational and Professional Licensing", "https://dopl.utah.gov", "(801) 530-6628"),
        ("VT", "Vermont Office of Professional Regulation", "https://sos.vermont.gov/opr", "(802) 828-1505"),
        ("VA", "Virginia Department of Professional and Occupational Regulation", "https://www.dpor.virginia.gov", "(804) 367-8511"),
        ("WA", "Washington Department of Labor and Industries", "https://lni.wa.gov", "(360) 902-5226"),
        ("WV", "West Virginia Division of Labor", "https://labor.wv.gov", "(304) 558-7890"),
        ("WI", "Wisconsin Department of Safety and Professional Services", "https://dsps.wi.gov", "(608) 266-2112"),
        ("WY", "Wyoming Department of Fire Prevention and Electrical Safety", "https://wsfm.wyo.gov", "(307) 777-7288"),
        ("DC", "District of Columbia Department of Consumer and Regulatory Affairs", "https://dcra.dc.gov", "(202) 442-4400"),
    ]
    conn.executemany(
        "INSERT INTO state_license_boards (state_code, board_name, website_url, phone) "
        "VALUES (?, ?, ?, ?)",
        boards,
    )


def _seed_scope_categories(conn: sqlite3.Connection):
    """Seed core construction discipline scope categories."""
    existing = conn.execute("SELECT COUNT(*) FROM scope_categories").fetchone()[0]
    if existing > 0:
        return

    scopes = [
        ("Plumbing", 1),
        ("HVAC", 2),
        ("Mechanical", 3),
        ("Electrical", 4),
        ("Refrigeration", 5),
        ("Fire Protection", 6),
        ("General Contractor", 7),
        ("Utilities", 8),
        ("Process Piping", 9),
    ]
    conn.executemany(
        "INSERT INTO scope_categories (id, name, sort_order) VALUES (?, ?, ?)",
        [(_gen_id(), name, order) for name, order in scopes],
    )
