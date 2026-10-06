# ARCHIVED — 2026-10-06

QMS was built as an in-house quality management system for the MEP division.
It is shelved because IT will not permit distributing self-built software
inside the company. The code is kept as a parts bin for future projects.

## What moved out

- **`data/quality.db` is no longer live here.** The Quality Manual build
  (`D:\QM-Obsidian\_Build`) still depends on it, so a verified copy now lives at
  `D:\QM-Obsidian\_Data\quality.db` and every script, agent doc and the sqlite
  MCP server point there. The copy in `data/` is a frozen snapshot as of
  2026-09-08, along with ~170 historical `.bak-*` files (4.3 GB).
- **`docs/SIS-QMS-vault/`** is the former `D:\SIS-QMS` Obsidian vault: module
  notes, architecture overview and ADRs written 2026-02-10/11. It documents
  11 of the 19 packages; api, auth, blog, imports, licenses, quality,
  timetracker and tray have no notes.

## Unmerged work on branches

| Branch | Contents not on `main` |
|---|---|
| `claude/customer-profile-system-bOqFQ` | customers module: schema, CLI, API, dashboard templates |
| `claude/investigate-session-context-A2l0s` | `welding/sharepoint.py` (SharePoint Lists sync for the Power App weld-cert forms), weld-cert workflow and SharePoint integration plans |
| `claude/review-changes-mlft7fuad8sjhdg9-mCDN4` | `NEXT_STEPS.md` plan |

These branches use the pre-flattening layout (`qms/welding/...`).

## What was switched off

- Tray auto-start: the Startup script is now `SIS QMS Tray.vbs.disabled` in this folder.
- The `qms` editable pip install was removed (`pip uninstall qms`).
- The NSSM Windows service `QMS` still exists, stopped and set to Manual.
  Removing it needs an elevated prompt: `nssm remove QMS confirm`.

## Reviving it

From the folder this lives in: `pip install -e .`, then `python -m qms tray`.
Copy the `.vbs.disabled` file back into `shell:startup` (without `.disabled`)
to auto-start again. Point `config.yaml` at whichever `quality.db` should be live.
