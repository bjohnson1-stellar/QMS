"""
SharePoint Lists Sync for Welding Module

Pushes welding lookup data to SharePoint Lists for consumption by
Power Apps (Teams). Pulls form submissions back into QMS.

Authentication: Azure AD app registration with client credentials.
API: Microsoft Graph v1.0

Usage:
    qms welding sync-sharepoint --push          # Push all lists
    qms welding sync-sharepoint --push --list welders
    qms welding sync-sharepoint --pull           # Pull submissions
    qms welding sync-sharepoint --status         # Check sync state

Prerequisites:
    pip install msal requests
    Configure sharepoint section in config.yaml
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from qms.core import get_config_value, get_db, get_logger

logger = get_logger("qms.welding.sharepoint")

# ---------------------------------------------------------------------------
# Reference data (mirrors importer.py constants)
# ---------------------------------------------------------------------------

PROCESS_FULL_NAMES = {
    "SMAW": "Shielded Metal Arc Welding",
    "GTAW": "Gas Tungsten Arc Welding",
    "GMAW": "Gas Metal Arc Welding",
    "FCAW": "Flux-Cored Arc Welding",
    "SAW": "Submerged Arc Welding",
    "GTAW/SMAW": "GTAW Root / SMAW Fill",
}

POSITION_DATA = {
    "1G": {"type": "Groove", "qualifies": ["1G"]},
    "2G": {"type": "Groove", "qualifies": ["1G", "2G"]},
    "3G": {"type": "Groove", "qualifies": ["1G", "3G"]},
    "4G": {"type": "Groove", "qualifies": ["1G", "4G"]},
    "5G": {"type": "Groove", "qualifies": ["1G", "2G", "5G"]},
    "6G": {"type": "Groove", "qualifies": ["1G", "2G", "3G", "4G", "5G", "6G"]},
    "6GR": {"type": "Groove", "qualifies": ["1G", "2G", "3G", "4G", "5G", "6G", "6GR"]},
    "1F": {"type": "Fillet", "qualifies": ["1F"]},
    "2F": {"type": "Fillet", "qualifies": ["1F", "2F"]},
    "3F": {"type": "Fillet", "qualifies": ["1F", "2F", "3F"]},
    "4F": {"type": "Fillet", "qualifies": ["1F", "2F", "3F", "4F"]},
    "5F": {"type": "Fillet", "qualifies": ["1F", "2F", "3F", "4F", "5F"]},
}

BASE_MATERIALS = {
    "A53": {"p_number": 1, "type": "Carbon Steel"},
    "A106": {"p_number": 1, "type": "Carbon Steel"},
    "A333": {"p_number": 1, "type": "Carbon Steel"},
    "A516": {"p_number": 1, "type": "Carbon Steel"},
    "CS": {"p_number": 1, "type": "Carbon Steel"},
    "A312": {"p_number": 8, "type": "Stainless Steel"},
    "A358": {"p_number": 8, "type": "Stainless Steel"},
    "A240": {"p_number": 8, "type": "Stainless Steel"},
    "SS": {"p_number": 8, "type": "Stainless Steel"},
    "SS304": {"p_number": 8, "type": "Stainless Steel 304"},
    "SS316": {"p_number": 8, "type": "Stainless Steel 316"},
}

FILLER_METALS = {
    "6010": {"f_number": 3, "process": "SMAW", "aws_class": "E6010"},
    "6011": {"f_number": 3, "process": "SMAW", "aws_class": "E6011"},
    "7018": {"f_number": 4, "process": "SMAW", "aws_class": "E7018"},
    "8018": {"f_number": 4, "process": "SMAW", "aws_class": "E8018"},
    "8010": {"f_number": 3, "process": "SMAW", "aws_class": "E8010"},
    "ER70S": {"f_number": 6, "process": "GTAW", "aws_class": "ER70S-2/ER70S-6"},
    "ER70S2": {"f_number": 6, "process": "GTAW", "aws_class": "ER70S-2"},
    "ER70S6": {"f_number": 6, "process": "GTAW", "aws_class": "ER70S-6"},
    "ER80S": {"f_number": 6, "process": "GTAW", "aws_class": "ER80S-Ni1"},
    "ER308": {"f_number": 6, "process": "GTAW", "aws_class": "ER308L"},
    "ER309": {"f_number": 6, "process": "GTAW", "aws_class": "ER309L"},
    "ER316": {"f_number": 6, "process": "GTAW", "aws_class": "ER316L"},
}


# ---------------------------------------------------------------------------
# SharePoint List definitions
# ---------------------------------------------------------------------------

# Maps list name -> column definitions for creation
# SP column types: https://learn.microsoft.com/en-us/graph/api/resources/columndefinition
LIST_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "WeldActiveWelders": {
        "description": "Active welders from QMS registry",
        "columns": [
            {"name": "EmployeeNumber", "text": {}},
            {"name": "DisplayName", "text": {}},
            {"name": "FirstName", "text": {}},
            {"name": "LastName", "text": {}},
            {"name": "Department", "text": {}},
            {"name": "Supervisor", "text": {}},
            {"name": "BusinessUnit", "text": {}},
            {"name": "WelderStatus", "choice": {"choices": ["active", "inactive"]}},
        ],
    },
    "WeldProcesses": {
        "description": "Valid welding process types",
        "columns": [
            {"name": "FullName", "text": {}},
        ],
    },
    "WeldActiveWPS": {
        "description": "Active Welding Procedure Specifications",
        "columns": [
            {"name": "Revision", "text": {}},
            {"name": "WPSTitle", "text": {}},
            {"name": "WPSStatus", "choice": {"choices": ["draft", "active", "superseded"]}},
            {"name": "ApplicableCodes", "text": {"allowMultipleLines": True}},
            {"name": "IsSWPS", "boolean": {}},
        ],
    },
    "WeldPositions": {
        "description": "Welding test positions and qualification hierarchy",
        "columns": [
            {"name": "PositionType", "choice": {"choices": ["Groove", "Fillet"]}},
            {"name": "QualifiesFor", "text": {"allowMultipleLines": True}},
        ],
    },
    "WeldBaseMaterials": {
        "description": "Base material P-number reference",
        "columns": [
            {"name": "PNumber", "number": {}},
            {"name": "MaterialType", "text": {}},
        ],
    },
    "WeldFillerMetals": {
        "description": "Filler metal F-number reference",
        "columns": [
            {"name": "FNumber", "number": {}},
            {"name": "Process", "text": {}},
            {"name": "AWSClass", "text": {}},
        ],
    },
    "WeldWPQStatus": {
        "description": "Active welder performance qualifications",
        "columns": [
            {"name": "WelderStamp", "text": {}},
            {"name": "WelderName", "text": {}},
            {"name": "ProcessType", "text": {}},
            {"name": "PNumber", "number": {}},
            {"name": "FNumber", "number": {}},
            {"name": "PositionsQualified", "text": {"allowMultipleLines": True}},
            {"name": "TestDate", "dateTime": {"format": "dateOnly"}},
            {"name": "ExpirationDate", "dateTime": {"format": "dateOnly"}},
            {"name": "WPQStatus", "choice": {"choices": ["active", "expired", "lapsed"]}},
            {"name": "ContinuityStatus", "choice": {"choices": ["OK", "AT_RISK", "LAPSED"]}},
            {"name": "DaysRemaining", "number": {}},
        ],
    },
    "WeldCertFormSubmissions": {
        "description": "Welder certification form submissions from Power App",
        "columns": [
            {"name": "WelderStamp", "text": {}},
            {"name": "WelderName", "text": {}},
            {"name": "ProcessType", "text": {}},
            {"name": "WPSNumber", "text": {}},
            {"name": "TestPosition", "text": {}},
            {"name": "BaseMaterial", "text": {}},
            {"name": "FillerMetal", "text": {}},
            {"name": "TestDate", "dateTime": {"format": "dateOnly"}},
            {"name": "TestResult", "choice": {"choices": ["Pass", "Fail"]}},
            {"name": "BendTestResult", "choice": {"choices": ["Pass", "Fail", "N-A"]}},
            {"name": "VisualTestResult", "choice": {"choices": ["Pass", "Fail", "N-A"]}},
            {"name": "RTResult", "choice": {"choices": ["Pass", "Fail", "N-A"]}},
            {"name": "Examiner", "text": {}},
            {"name": "Witness", "text": {}},
            {"name": "ProjectNumber", "text": {}},
            {"name": "Notes", "text": {"allowMultipleLines": True}},
            {"name": "ImportedToQMS", "boolean": {}},
        ],
    },
}

# Friendly name -> list key mapping for CLI
LIST_ALIASES = {
    "welders": "WeldActiveWelders",
    "processes": "WeldProcesses",
    "wps": "WeldActiveWPS",
    "positions": "WeldPositions",
    "materials": "WeldBaseMaterials",
    "fillers": "WeldFillerMetals",
    "wpq-status": "WeldWPQStatus",
    "submissions": "WeldCertFormSubmissions",
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class SharePointAuth:
    """Handles Azure AD client-credentials authentication for Graph API."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    def get_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        if self._token and self._expires_at and datetime.now() < self._expires_at:
            return self._token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        resp = requests.post(url, data=data, timeout=30)
        resp.raise_for_status()
        token_data = resp.json()

        self._token = token_data["access_token"]
        self._expires_at = datetime.now() + timedelta(
            seconds=token_data.get("expires_in", 3600) - 60
        )
        return self._token

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
        }


# ---------------------------------------------------------------------------
# Graph API Client
# ---------------------------------------------------------------------------

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class SharePointClient:
    """Microsoft Graph API client for SharePoint list operations."""

    def __init__(self, auth: SharePointAuth, site_id: str):
        self.auth = auth
        self.site_id = site_id
        self._list_id_cache: Dict[str, str] = {}

    @classmethod
    def from_config(cls) -> "SharePointClient":
        """Create client from config.yaml sharepoint section."""
        tenant_id = get_config_value("sharepoint", "tenant_id", default="")
        client_id = get_config_value("sharepoint", "client_id", default="")
        client_secret = get_config_value("sharepoint", "client_secret", default="")
        site_id = get_config_value("sharepoint", "site_id", default="")
        site_name = get_config_value("sharepoint", "site_name", default="")

        if not all([tenant_id, client_id, client_secret]):
            raise ValueError(
                "SharePoint not configured. Add tenant_id, client_id, and "
                "client_secret to the 'sharepoint' section of config.yaml"
            )

        auth = SharePointAuth(tenant_id, client_id, client_secret)

        # Auto-discover site_id from site_name if not set
        if not site_id and site_name:
            site_id = cls._discover_site_id(auth, site_name)

        if not site_id:
            raise ValueError(
                "SharePoint site_id or site_name required in config.yaml"
            )

        return cls(auth, site_id)

    @staticmethod
    def _discover_site_id(auth: SharePointAuth, site_name: str) -> str:
        """Look up site ID from site display name."""
        url = f"{GRAPH_BASE}/sites?search={site_name}"
        resp = requests.get(url, headers=auth.headers, timeout=30)
        resp.raise_for_status()
        sites = resp.json().get("value", [])
        if not sites:
            raise ValueError(f"SharePoint site not found: {site_name}")
        return sites[0]["id"]

    # --- List CRUD ---

    def get_list_id(self, list_name: str) -> Optional[str]:
        """Get the ID of an existing list by name."""
        if list_name in self._list_id_cache:
            return self._list_id_cache[list_name]

        url = f"{GRAPH_BASE}/sites/{self.site_id}/lists"
        resp = requests.get(url, headers=self.auth.headers, timeout=30)
        resp.raise_for_status()

        for lst in resp.json().get("value", []):
            if lst.get("displayName") == list_name:
                self._list_id_cache[list_name] = lst["id"]
                return lst["id"]
        return None

    def create_list(self, list_name: str, schema: Dict[str, Any]) -> str:
        """Create a SharePoint list with the given schema. Returns list ID."""
        url = f"{GRAPH_BASE}/sites/{self.site_id}/lists"
        body = {
            "displayName": list_name,
            "description": schema.get("description", ""),
            "list": {"template": "genericList"},
        }
        resp = requests.post(
            url, headers=self.auth.headers, json=body, timeout=30
        )
        resp.raise_for_status()
        list_id = resp.json()["id"]
        self._list_id_cache[list_name] = list_id

        # Add custom columns
        for col_def in schema.get("columns", []):
            self._add_column(list_id, col_def)

        logger.info("Created SharePoint list: %s (%s)", list_name, list_id)
        return list_id

    def _add_column(self, list_id: str, col_def: Dict[str, Any]) -> None:
        """Add a column to a list."""
        url = f"{GRAPH_BASE}/sites/{self.site_id}/lists/{list_id}/columns"
        resp = requests.post(
            url, headers=self.auth.headers, json=col_def, timeout=30
        )
        resp.raise_for_status()

    def ensure_list(self, list_name: str, schema: Dict[str, Any]) -> str:
        """Get existing list or create it. Returns list ID."""
        list_id = self.get_list_id(list_name)
        if list_id:
            return list_id
        return self.create_list(list_name, schema)

    def clear_list_items(self, list_id: str) -> int:
        """Delete all items from a list. Returns count deleted."""
        deleted = 0
        while True:
            url = (
                f"{GRAPH_BASE}/sites/{self.site_id}/lists/{list_id}"
                f"/items?$top=100&$select=id"
            )
            resp = requests.get(url, headers=self.auth.headers, timeout=30)
            resp.raise_for_status()
            items = resp.json().get("value", [])
            if not items:
                break
            for item in items:
                del_url = (
                    f"{GRAPH_BASE}/sites/{self.site_id}/lists/{list_id}"
                    f"/items/{item['id']}"
                )
                requests.delete(del_url, headers=self.auth.headers, timeout=30)
                deleted += 1
        return deleted

    def add_items(self, list_id: str, items: List[Dict[str, Any]]) -> int:
        """Add items to a list. Returns count added."""
        url = f"{GRAPH_BASE}/sites/{self.site_id}/lists/{list_id}/items"
        added = 0
        for item_fields in items:
            body = {"fields": item_fields}
            resp = requests.post(
                url, headers=self.auth.headers, json=body, timeout=30
            )
            resp.raise_for_status()
            added += 1
        return added

    def get_items(
        self,
        list_id: str,
        filter_query: Optional[str] = None,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get items from a list with optional OData filter."""
        url = f"{GRAPH_BASE}/sites/{self.site_id}/lists/{list_id}/items"
        params: Dict[str, str] = {"$expand": "fields"}
        if filter_query:
            params["$filter"] = filter_query
        if select:
            params["$expand"] = f"fields($select={','.join(select)})"

        all_items = []
        while url:
            resp = requests.get(
                url, headers=self.auth.headers, params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            all_items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = {}  # nextLink includes params
        return all_items


# ---------------------------------------------------------------------------
# Data extraction from QMS database
# ---------------------------------------------------------------------------

def _get_active_welders(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Extract active welders for SharePoint sync."""
    rows = conn.execute(
        """SELECT welder_stamp, employee_number, display_name,
                  first_name, last_name, department, supervisor,
                  business_unit, status
           FROM weld_welder_registry
           WHERE status = 'active'
           ORDER BY last_name, first_name"""
    ).fetchall()
    return [
        {
            "Title": r["welder_stamp"] or "",
            "EmployeeNumber": r["employee_number"] or "",
            "DisplayName": r["display_name"] or "",
            "FirstName": r["first_name"] or "",
            "LastName": r["last_name"] or "",
            "Department": r["department"] or "",
            "Supervisor": r["supervisor"] or "",
            "BusinessUnit": r["business_unit"] or "",
            "WelderStatus": r["status"] or "active",
        }
        for r in rows
    ]


def _get_processes() -> List[Dict[str, Any]]:
    """Static process reference list."""
    return [
        {"Title": code, "FullName": PROCESS_FULL_NAMES[code]}
        for code in PROCESS_FULL_NAMES
    ]


def _get_active_wps(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Extract active WPS records for SharePoint sync."""
    rows = conn.execute(
        """SELECT wps_number, revision, title, status,
                  applicable_codes, is_swps
           FROM weld_wps
           WHERE status IN ('active', 'draft')
           ORDER BY wps_number"""
    ).fetchall()
    return [
        {
            "Title": r["wps_number"] or "",
            "Revision": r["revision"] or "",
            "WPSTitle": r["title"] or "",
            "WPSStatus": r["status"] or "draft",
            "ApplicableCodes": r["applicable_codes"] or "",
            "IsSWPS": bool(r["is_swps"]),
        }
        for r in rows
    ]


def _get_positions() -> List[Dict[str, Any]]:
    """Static position reference list."""
    return [
        {
            "Title": code,
            "PositionType": info["type"],
            "QualifiesFor": json.dumps(info["qualifies"]),
        }
        for code, info in POSITION_DATA.items()
    ]


def _get_base_materials() -> List[Dict[str, Any]]:
    """Static base material reference list."""
    return [
        {
            "Title": spec,
            "PNumber": info["p_number"],
            "MaterialType": info["type"],
        }
        for spec, info in BASE_MATERIALS.items()
    ]


def _get_filler_metals() -> List[Dict[str, Any]]:
    """Static filler metal reference list."""
    return [
        {
            "Title": code,
            "FNumber": info["f_number"],
            "Process": info["process"],
            "AWSClass": info["aws_class"],
        }
        for code, info in FILLER_METALS.items()
    ]


def _get_wpq_status(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Extract active WPQ records with continuity status."""
    rows = conn.execute(
        """SELECT
               wpq.wpq_number,
               wr.welder_stamp,
               wr.display_name,
               wpq.process_type,
               wpq.p_number,
               wpq.f_number,
               wpq.positions_qualified,
               wpq.test_date,
               wpq.current_expiration_date,
               wpq.status,
               CAST(JULIANDAY(wpq.current_expiration_date) - JULIANDAY(DATE('now'))
                    AS INTEGER) as days_remaining,
               CASE
                   WHEN wpq.current_expiration_date < DATE('now') THEN 'LAPSED'
                   WHEN wpq.current_expiration_date < DATE('now', '+30 days') THEN 'AT_RISK'
                   ELSE 'OK'
               END as continuity_status
           FROM weld_wpq wpq
           JOIN weld_welder_registry wr ON wpq.welder_id = wr.id
           WHERE wr.status = 'active'
           ORDER BY wr.last_name, wpq.process_type"""
    ).fetchall()
    items = []
    for r in rows:
        item = {
            "Title": r["wpq_number"] or "",
            "WelderStamp": r["welder_stamp"] or "",
            "WelderName": r["display_name"] or "",
            "ProcessType": r["process_type"] or "",
            "PositionsQualified": r["positions_qualified"] or "",
            "WPQStatus": r["status"] or "active",
            "ContinuityStatus": r["continuity_status"] or "OK",
        }
        if r["p_number"] is not None:
            item["PNumber"] = r["p_number"]
        if r["f_number"] is not None:
            item["FNumber"] = r["f_number"]
        if r["test_date"]:
            item["TestDate"] = r["test_date"]
        if r["current_expiration_date"]:
            item["ExpirationDate"] = r["current_expiration_date"]
        if r["days_remaining"] is not None:
            item["DaysRemaining"] = r["days_remaining"]
        items.append(item)
    return items


# Map list names to their data extraction functions
# Functions that need a db connection take (conn,), others take ()
_DATA_EXTRACTORS = {
    "WeldActiveWelders": ("db", _get_active_welders),
    "WeldProcesses": ("static", _get_processes),
    "WeldActiveWPS": ("db", _get_active_wps),
    "WeldPositions": ("static", _get_positions),
    "WeldBaseMaterials": ("static", _get_base_materials),
    "WeldFillerMetals": ("static", _get_filler_metals),
    "WeldWPQStatus": ("db", _get_wpq_status),
}


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------

def push_list(
    client: SharePointClient,
    list_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Push a single list to SharePoint.

    Clears existing items and replaces with current QMS data.

    Returns:
        Dict with keys: list_name, items_deleted, items_added, status
    """
    if list_name not in LIST_SCHEMAS:
        return {"list_name": list_name, "status": "error", "error": f"Unknown list: {list_name}"}

    schema = LIST_SCHEMAS[list_name]

    # Skip submissions list on push (it's write-back only)
    if list_name == "WeldCertFormSubmissions":
        return {"list_name": list_name, "status": "skipped", "reason": "submissions list is pull-only"}

    # Extract data
    source_type, extractor = _DATA_EXTRACTORS[list_name]
    if source_type == "db":
        with get_db(readonly=True) as conn:
            items = extractor(conn)
    else:
        items = extractor()

    result = {
        "list_name": list_name,
        "items_count": len(items),
        "status": "dry_run" if dry_run else "pending",
    }

    if dry_run:
        result["items_preview"] = items[:3] if items else []
        return result

    # Ensure list exists
    list_id = client.ensure_list(list_name, schema)

    # Clear and repopulate
    deleted = client.clear_list_items(list_id)
    added = client.add_items(list_id, items)

    result.update({
        "items_deleted": deleted,
        "items_added": added,
        "status": "success",
    })
    logger.info(
        "Synced %s: %d deleted, %d added", list_name, deleted, added
    )
    return result


def push_all(
    client: SharePointClient,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Push all lookup lists to SharePoint."""
    results = {}
    push_order = [
        "WeldProcesses",
        "WeldPositions",
        "WeldBaseMaterials",
        "WeldFillerMetals",
        "WeldActiveWelders",
        "WeldActiveWPS",
        "WeldWPQStatus",
    ]
    for list_name in push_order:
        results[list_name] = push_list(client, list_name, dry_run=dry_run)
    return results


def pull_submissions(
    client: SharePointClient,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Pull new form submissions from SharePoint into QMS.

    Reads items where ImportedToQMS is false, processes them,
    then marks them as imported.
    """
    list_id = client.get_list_id("WeldCertFormSubmissions")
    if not list_id:
        return {"status": "error", "error": "Submissions list not found in SharePoint"}

    items = client.get_items(
        list_id,
        filter_query="fields/ImportedToQMS eq false",
    )

    result = {
        "total_found": len(items),
        "imported": 0,
        "errors": [],
        "status": "dry_run" if dry_run else "pending",
    }

    if not items:
        result["status"] = "success"
        return result

    if dry_run:
        result["preview"] = [
            {
                "welder": i.get("fields", {}).get("WelderStamp", "?"),
                "process": i.get("fields", {}).get("ProcessType", "?"),
                "test_date": i.get("fields", {}).get("TestDate", "?"),
                "result": i.get("fields", {}).get("TestResult", "?"),
            }
            for i in items[:5]
        ]
        return result

    with get_db() as conn:
        for item in items:
            fields = item.get("fields", {})
            item_id = item.get("id")
            try:
                _import_submission(conn, fields)
                result["imported"] += 1

                # Mark as imported in SharePoint
                update_url = (
                    f"{GRAPH_BASE}/sites/{client.site_id}/lists/{list_id}"
                    f"/items/{item_id}/fields"
                )
                requests.patch(
                    update_url,
                    headers=client.auth.headers,
                    json={"ImportedToQMS": True},
                    timeout=30,
                )
            except Exception as e:
                error_msg = f"Item {item_id}: {e}"
                result["errors"].append(error_msg)
                logger.warning("Failed to import submission: %s", error_msg)

    result["status"] = "success"
    logger.info(
        "Pulled submissions: %d imported, %d errors",
        result["imported"],
        len(result["errors"]),
    )
    return result


def _import_submission(conn: sqlite3.Connection, fields: Dict[str, Any]) -> None:
    """Import a single form submission into the QMS database."""
    welder_stamp = fields.get("WelderStamp", "").strip()
    process_type = fields.get("ProcessType", "").strip()
    test_result = fields.get("TestResult", "").strip()
    test_date = fields.get("TestDate", "")

    if not welder_stamp or not process_type:
        raise ValueError(f"Missing required fields: stamp={welder_stamp}, process={process_type}")

    # Look up welder
    row = conn.execute(
        "SELECT id FROM weld_welder_registry WHERE welder_stamp = ?",
        (welder_stamp,),
    ).fetchone()
    if not row:
        raise ValueError(f"Welder not found: {welder_stamp}")

    welder_id = row["id"]

    # Build WPQ number
    wpq_number = f"{welder_stamp}-{process_type}"

    # Check for existing WPQ
    existing = conn.execute(
        "SELECT id FROM weld_wpq WHERE wpq_number = ?",
        (wpq_number,),
    ).fetchone()

    if test_date and isinstance(test_date, str):
        # Normalize date format
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                test_date = datetime.strptime(test_date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    expiration_date = ""
    if test_date:
        try:
            td = datetime.strptime(test_date, "%Y-%m-%d")
            expiration_date = (td + timedelta(days=180)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    p_number = None
    material = fields.get("BaseMaterial", "").strip()
    if material and material in BASE_MATERIALS:
        p_number = BASE_MATERIALS[material]["p_number"]

    f_number = None
    filler = fields.get("FillerMetal", "").strip()
    if filler and filler in FILLER_METALS:
        f_number = FILLER_METALS[filler]["f_number"]

    if existing:
        # Update existing WPQ
        conn.execute(
            """UPDATE weld_wpq SET
                   test_date = COALESCE(?, test_date),
                   current_expiration_date = COALESCE(?, current_expiration_date),
                   p_number = COALESCE(?, p_number),
                   f_number = COALESCE(?, f_number),
                   positions_qualified = COALESCE(?, positions_qualified),
                   status = 'active',
                   updated_at = CURRENT_TIMESTAMP
               WHERE wpq_number = ?""",
            (
                test_date or None,
                expiration_date or None,
                p_number,
                f_number,
                fields.get("TestPosition"),
                wpq_number,
            ),
        )
    else:
        # Create new WPQ
        conn.execute(
            """INSERT INTO weld_wpq
                   (wpq_number, welder_id, process_type, p_number, f_number,
                    positions_qualified, test_date, initial_expiration_date,
                    current_expiration_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)""",
            (
                wpq_number,
                welder_id,
                process_type,
                p_number,
                f_number,
                fields.get("TestPosition", ""),
                test_date,
                expiration_date,
                expiration_date,
            ),
        )

    logger.info("Imported submission: %s (%s)", wpq_number, test_result)


def get_sync_status(client: SharePointClient) -> Dict[str, Any]:
    """Check the current state of all synced lists."""
    status = {}
    for list_name in LIST_SCHEMAS:
        list_id = client.get_list_id(list_name)
        if list_id:
            items = client.get_items(list_id, select=["id"])
            status[list_name] = {
                "exists": True,
                "item_count": len(items),
            }
        else:
            status[list_name] = {"exists": False, "item_count": 0}
    return status


# ---------------------------------------------------------------------------
# Offline preview (no SharePoint connection needed)
# ---------------------------------------------------------------------------

def preview_sync_data(list_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Preview what data would be pushed to SharePoint.

    Works offline — reads from QMS database only.
    Useful for validating data before configuring SharePoint.

    Args:
        list_key: Specific list alias (e.g. 'welders') or None for all.

    Returns:
        Dict mapping list names to their item lists.
    """
    if list_key:
        list_name = LIST_ALIASES.get(list_key, list_key)
        if list_name not in _DATA_EXTRACTORS:
            return {"error": f"Unknown list: {list_key}"}
        source_type, extractor = _DATA_EXTRACTORS[list_name]
        if source_type == "db":
            with get_db(readonly=True) as conn:
                items = extractor(conn)
        else:
            items = extractor()
        return {list_name: items}

    # All lists
    result = {}
    with get_db(readonly=True) as conn:
        for list_name, (source_type, extractor) in _DATA_EXTRACTORS.items():
            if source_type == "db":
                result[list_name] = extractor(conn)
            else:
                result[list_name] = extractor()
    return result
