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

    # Phase 3 seed data
    _seed_ce_requirements(conn)

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
            lookup_url  TEXT,
            phone       TEXT,
            notes       TEXT,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT
        )
    """)
    # Add lookup_url column if migrating from Phase 2 initial
    board_cols = {r[1] for r in conn.execute("PRAGMA table_info(state_license_boards)").fetchall()}
    if "lookup_url" not in board_cols:
        conn.execute("ALTER TABLE state_license_boards ADD COLUMN lookup_url TEXT")
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_portal_credentials (
            id          TEXT PRIMARY KEY,
            license_id  TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            portal_url  TEXT,
            username    TEXT NOT NULL,
            password_enc TEXT NOT NULL,
            notes       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(license_id, user_id),
            FOREIGN KEY (license_id) REFERENCES state_licenses(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_portal_creds_user ON license_portal_credentials(user_id)")


def _seed_license_boards(conn: sqlite3.Connection):
    """Seed state licensing board data with verified portal + lookup URLs."""
    existing = conn.execute("SELECT COUNT(*) FROM state_license_boards").fetchone()[0]
    if existing > 0:
        # Upsert to fix URLs on existing installs
        _upsert_board_data(conn)
        return
    _upsert_board_data(conn)


def _upsert_board_data(conn: sqlite3.Connection):
    """Insert or update all 51 board records with researched URLs."""
    # (state_code, board_name, website_url, lookup_url, phone, notes)
    boards = [
        ("AL", "Alabama Licensing Board for General Contractors",
         "https://genconbd.alabama.gov", "https://genconbd.alabama.gov/database-sql/roster.aspx",
         "(334) 272-5030", "GC board. Separate boards: Plumbing (pgfb.alabama.gov), HVAC (hacr.alabama.gov), Electrical (aecb.alabama.gov)"),
        ("AK", "Alaska Division of Corporations, Business and Professional Licensing",
         "https://www.commerce.alaska.gov/web/cbpl/ProfessionalLicensing/ConstructionContractors",
         "https://www.commerce.alaska.gov/cbp/main/search/professional",
         "(907) 465-2050", None),
        ("AZ", "Arizona Registrar of Contractors",
         "https://roc.az.gov", "https://azroc.my.site.com/AZRoc/s/contractor-search",
         "(602) 542-1525", None),
        ("AR", "Arkansas Contractors Licensing Board",
         "https://labor.arkansas.gov/licensing/arkansas-contractors-licensing-board/",
         "https://labor.arkansas.gov/licensing/arkansas-contractors-licensing-board/find-a-licensed-contractor/",
         "(501) 372-4661", None),
        ("CA", "California Contractors State License Board",
         "https://www.cslb.ca.gov", "https://www.cslb.ca.gov/onlineservices/checklicenseII/checklicense.aspx",
         "(800) 321-2752", "Single board: A-General, B-Building, C-10 Electrical, C-20 HVAC, C-36 Plumbing, C-38 Refrigeration"),
        ("CO", "Colorado Department of Regulatory Agencies",
         "https://dora.colorado.gov", "https://apps2.colorado.gov/dora/licensing/lookup/licenselookup.aspx",
         "(303) 894-7855", "State licenses electricians and plumbers only. GC licensing is local/municipal."),
        ("CT", "Connecticut Department of Consumer Protection",
         "https://portal.ct.gov/dcp", "https://www.elicense.ct.gov/Lookup/LicenseLookup.aspx",
         "(860) 713-6100", None),
        ("DE", "Delaware Division of Professional Regulation",
         "https://delpros.delaware.gov", "https://delpros.delaware.gov/OH_VerifyLicense",
         "(302) 430-7739", "Contractors >$50K need state license. Specialty trades through Div. of Professional Regulation."),
        ("FL", "Florida Department of Business and Professional Regulation",
         "https://www2.myfloridalicense.com", "https://www.myfloridalicense.com/wl11.asp?mode=2&search=Name&SID=&brd=&typ=",
         "(850) 487-1395", "Both state-certified and county-registered contractors."),
        ("GA", "Georgia Secretary of State — Professional Licensing",
         "https://sos.ga.gov/licensing-division-georgia-secretary-states-office",
         "https://verify.sos.ga.gov/Verification",
         "(404) 463-5600", "Separate divisions: GC Board, Master Plumbers, Conditioned Air (HVAC), Electrical, Low Voltage."),
        ("HI", "Hawaii Contractors License Board",
         "https://cca.hawaii.gov/pvl/boards/contractor/", "https://mypvl.dcca.hawaii.gov/public-license-search/",
         "(844) 808-3222", None),
        ("ID", "Idaho Division of Occupational and Professional Licenses",
         "https://dopl.idaho.gov/con/", "https://dopl.idaho.gov/license-search/",
         "(208) 334-3233", "No state GC license. State licenses electrical, HVAC, plumbing, public works, fire sprinkler."),
        ("IL", "Illinois Department of Financial and Professional Regulation",
         "https://idfpr.illinois.gov", "https://online-dfpr.micropact.com/lookup/licenselookup.aspx",
         "(888) 473-4858", "Roofing via IDFPR. Plumbing via IDPH. No state GC or HVAC license."),
        ("IN", "Indiana Professional Licensing Agency",
         "https://www.in.gov/pla", "https://mylicense.in.gov/everification/",
         "(317) 234-2086", "State licenses plumbers. GC, HVAC, electrician licensing is local/municipal."),
        ("IA", "Iowa Department of Inspections, Appeals, and Licensing",
         "https://dial.iowa.gov/licenses/building/contractors", "https://dial.iowa.gov/i-need/records",
         "(515) 725-9030", "Plumbing/Mechanical Board separate. Electrical via State Fire Marshal."),
        ("KS", "Kansas Professional License Verification",
         "https://prolicenseverify.ks.gov/", "https://prolicenseverify.ks.gov/",
         "(785) 296-7278", "Most trades licensed at city/county level. State Board of Technical Professions covers engineers/architects."),
        ("KY", "Kentucky Department of Housing, Buildings and Construction",
         "https://dhbc.ky.gov", "https://ky.joportal.com/license/search",
         "(502) 573-2002", "Licenses electrical, plumbing, HVAC, boiler, fire protection. No state GC license."),
        ("LA", "Louisiana State Licensing Board for Contractors",
         "https://lslbc.louisiana.gov", "https://arlspublic.lslbc.louisiana.gov/Public/Search",
         "(225) 765-2301", "Single board covers all contractor classifications."),
        ("ME", "Maine Office of Professional and Occupational Regulation",
         "https://www.maine.gov/pfr", "https://www.maine.gov/pfr/consumer/licensee-search",
         "(207) 624-8603", "State licenses electricians, plumbers. Mechanical tradesperson for HVAC. No state GC license."),
        ("MD", "Maryland Home Improvement Commission",
         "https://labor.maryland.gov/license/mhic/", "https://labor.maryland.gov/pq/",
         "(410) 230-6309", "MHIC for home improvement. Plumber/HVAC master licenses are separate boards under Dept. of Labor."),
        ("MA", "Massachusetts Division of Professional Licensure",
         "https://www.mass.gov/dpl", "https://madpl.mylicense.com/Verification/",
         "(617) 701-8600", "Separate boards: Construction Supervisor, Plumber/Gas Fitter, Electricians. HIC registration separate."),
        ("MI", "Michigan Dept. of Licensing and Regulatory Affairs — Bureau of Construction Codes",
         "https://www.michigan.gov/lara/bureau-list/bcc", "https://aca-prod.accela.com/LARA/GeneralProperty/PropertyLookUp.aspx?isLicensee=Y",
         "(517) 241-9316", "Licenses residential builders, maintenance/alteration contractors, electricians, plumbers, mechanical."),
        ("MN", "Minnesota Department of Labor and Industry",
         "https://www.dli.mn.gov/license", "https://www.dli.mn.gov/license-and-registration-lookup",
         "(651) 284-5034", None),
        ("MS", "Mississippi State Board of Contractors",
         "https://msboc.us", "https://www.msboc.us/contractors/",
         "(601) 354-6161", "Covers GC and subcontractors. Separate plumbing board."),
        ("MO", "Missouri Division of Professional Registration",
         "https://pr.mo.gov", "https://mopro.mo.gov/license/s/license-search",
         "(573) 751-0293", "Only electricians licensed statewide. GC, plumber, HVAC all licensed at city/county level."),
        ("MT", "Montana Department of Labor and Industry — Professional Boards",
         "https://boards.bsd.dli.mt.gov/", "https://ebizws.mt.gov/PUBLICPORTAL/searchform?mylist=licenses",
         "(406) 444-6880", "Plumbers, electricians via separate boards under DLI. GC registered (not licensed)."),
        ("NE", "Nebraska Department of Labor — Contractor Registration",
         "https://dol.nebraska.gov/conreg", "https://dol.nebraska.gov/conreg/Search",
         "(402) 471-2239", "Contractor registration via DOL. Plumber/mechanical via DHHS."),
        ("NV", "Nevada State Contractors Board",
         "https://www.nvcontractorsboard.com/",
         "https://app.nvcontractorsboard.com/Clients/nvscb/Public/ContractorListing/ListingSearch.aspx",
         "(702) 486-1100", "Single board for all contractor classifications."),
        ("NH", "New Hampshire Office of Professional Licensure and Certification",
         "https://www.oplc.nh.gov", "https://www.oplc.nh.gov/license-lookup",
         "(603) 271-2152", "Electricians Board and Mechanical Safety Board both under OPLC."),
        ("NJ", "New Jersey Division of Consumer Affairs",
         "https://www.njconsumeraffairs.gov", "https://newjersey.mylicense.com/verification/Search.aspx",
         "(973) 504-6200", "HIC through Home Elevation Contractor program. Separate boards for plumbers, electricians."),
        ("NM", "New Mexico Construction Industries Division",
         "https://www.rld.nm.gov/construction-industries/", "https://nmrldlpi.my.site.com/bcd/s/rld-public-search",
         "(505) 476-4700", "CID handles all trades: GB-2/GB-98, EE-98 electrical, MM-98 mechanical, MF-98 plumbing."),
        ("NY", "New York Department of State — Division of Licensing Services",
         "https://dos.ny.gov/licensing-services", "https://dos.ny.gov/licensee-search",
         "(518) 474-4429", "No statewide GC license. Licensing is municipal. NYC DOB: a810-bisweb.nyc.gov"),
        ("NC", "North Carolina Licensing Board for General Contractors",
         "https://nclbgc.org", "https://portal.nclbgc.org/Public/Search",
         "(919) 571-4183", "Separate board for Plumbing/HVAC/Fire Sprinkler: nclicensing.org"),
        ("ND", "North Dakota Secretary of State — Contractor Licensing",
         "https://www.sos.nd.gov/business/licensing-registration/contractors",
         "https://firststop.sos.nd.gov/search/contractor",
         "(701) 328-3665", "Classes A-D by project value. Plumber/electrician licensing separate."),
        ("OH", "Ohio Construction Industry Licensing Board",
         "https://elicense4.com.ohio.gov/", "https://elicense4.com.ohio.gov/Lookup/LicenseLookup.aspx",
         "(614) 644-3493", "Licenses electrical, HVAC, hydronics, plumbing, refrigeration. No state GC license."),
        ("OK", "Oklahoma Construction Industries Board",
         "https://oklahoma.gov/cib.html",
         "https://okcibv7prod.glsuite.us/GLSuiteWeb/Clients/OKCIB/Public/LicenseeSearch/LicenseeSearch.aspx",
         "(405) 521-6550", "Covers electrical, mechanical, plumbing, roofing, alarm."),
        ("OR", "Oregon Construction Contractors Board",
         "https://www.oregon.gov/ccb", "https://search.ccb.state.or.us/search/",
         "(503) 378-4621", "CCB for contractors. Building Codes Division for specialty trades (plumber, electrician)."),
        ("PA", "Pennsylvania Attorney General — Home Improvement Contractor Registration",
         "https://www.attorneygeneral.gov/resources/home-improvement-contractor-registration/",
         "https://hicsearch.attorneygeneral.gov/",
         "(888) 520-6680", "No statewide trade licensing for plumbers/electricians/HVAC — all municipal. State only registers HIC."),
        ("RI", "Rhode Island Contractors Registration and Licensing Board",
         "https://crb.ri.gov", "https://crb.ri.gov/search/contractor-search",
         "(401) 921-1590", None),
        ("SC", "South Carolina Contractors Licensing Board",
         "https://llr.sc.gov/clb", "https://verify.llronline.com/LicLookup/Contractors/Contractor.aspx?div=69",
         "(803) 896-4686", "Under LLR. Covers GC, mechanical, construction managers, alarm, fire sprinkler, boiler."),
        ("SD", "South Dakota Department of Labor and Regulation",
         "https://dlr.sd.gov/plumbing/default.aspx", None,
         "(605) 773-3429", "Only electricians and plumbers state-licensed. No state GC license. No centralized lookup portal."),
        ("TN", "Tennessee Board for Licensing Contractors",
         "https://www.tn.gov/commerce/regboards/contractors.html", "https://verify.tn.gov",
         "(615) 741-8307", "License required for projects >= $25,000."),
        ("TX", "Texas Department of Licensing and Regulation",
         "https://www.tdlr.texas.gov", "https://www.tdlr.texas.gov/LicenseSearch/",
         "(512) 463-6599", "TDLR: electricians, HVAC/refrigeration. Plumbing separate board: tsbpe.texas.gov. No state GC license."),
        ("UT", "Utah Division of Occupational and Professional Licensing",
         "https://dopl.utah.gov", "https://secure.utah.gov/llv/search/index.html",
         "(801) 530-6628", "Single agency for all construction trades."),
        ("VT", "Vermont Division of Fire Safety",
         "https://firesafety.vermont.gov/licensing", "https://sos.vermont.gov/opr/find-a-professional/",
         "(802) 479-7564", "Electricians/plumbers via Fire Safety. Other professionals via OPR. No state GC license."),
        ("VA", "Virginia Department of Professional and Occupational Regulation — Board for Contractors",
         "https://www.dpor.virginia.gov/Boards/Contractors/", "https://www.dpor.virginia.gov/LicenseLookup",
         "(804) 367-8511", "Class A (>$120K), B ($10K-$120K), C (subcontractors)."),
        ("WA", "Washington State Department of Labor and Industries",
         "https://lni.wa.gov", "https://secure.lni.wa.gov/verify/",
         "(360) 902-5226", "Single system for contractor registration AND tradesperson certification."),
        ("WV", "West Virginia Contractor Licensing Board",
         "https://wvclboard.wv.gov/", "https://wvclboard.wv.gov/verify/",
         "(304) 380-9423", None),
        ("WI", "Wisconsin Department of Safety and Professional Services",
         "https://dsps.wi.gov", "https://licensesearch.wi.gov/",
         "(608) 266-2112", "Single agency for all trades: electrical, plumbing, HVAC."),
        ("WY", "Wyoming State Fire Marshal",
         "https://wsfm.wyo.gov", "https://wyelectrician.imagetrendlicense.com/lms/public/portal",
         "(307) 777-7288", "Only electricians state-licensed. Plumbing, HVAC, GC all municipal."),
        ("DC", "District of Columbia Dept. of Licensing and Consumer Protection",
         "https://dlcp.dc.gov", "https://govservices.dcra.dc.gov/oplaportal/Home/GetLicenseSearchDetails",
         "(202) 671-4500", "GC needs business license (Class A-E). Specialty trades need separate OPL license."),
    ]
    for row in boards:
        conn.execute(
            """INSERT INTO state_license_boards
                   (state_code, board_name, website_url, lookup_url, phone, notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(state_code) DO UPDATE SET
                   board_name = excluded.board_name,
                   website_url = excluded.website_url,
                   lookup_url = excluded.lookup_url,
                   phone = excluded.phone,
                   notes = COALESCE(excluded.notes, state_license_boards.notes),
                   updated_at = datetime('now')""",
            row,
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


def _seed_ce_requirements(conn: sqlite3.Connection):
    """Seed researched CE hour requirements for key MEP contractor states.

    Uses INSERT OR IGNORE with UNIQUE(state_code, license_type) so
    re-running migration doesn't duplicate rows.
    """
    # (state_code, license_type, hours_required, period_months, notes)
    requirements = [
        ("FL", "Mechanical Contractor", 14, 24,
         "1hr workplace safety, 1hr workers comp, 1hr business"),
        ("FL", "Plumbing Contractor", 14, 24,
         "1hr workplace safety, 1hr workers comp, 1hr business"),
        ("TX", "Master Plumber", 8, 12, "Annual renewal"),
        ("TX", "Journeyman Plumber", 8, 12, "Annual renewal"),
        ("GA", "Conditioned Air Contractor", 6, 24, None),
        ("AL", "Master Plumber", 6, 12, None),
        ("NC", "Plumbing/Heating/Fire Sprinkler", 8, 12, None),
        ("SC", "Mechanical Contractor", 4, 24, None),
        ("LA", "Master Plumber", 6, 12, None),
    ]
    for state, lic_type, hours, period, notes in requirements:
        conn.execute(
            """INSERT OR IGNORE INTO ce_requirements
                   (id, state_code, license_type, hours_required, period_months,
                    notes, created_at, updated_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'system')""",
            (_gen_id(), state, lic_type, hours, period, notes),
        )
