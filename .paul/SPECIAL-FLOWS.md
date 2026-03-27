# Special Flows

## Project-Level Skills

| Skill | Work Type | Priority | Trigger |
|-------|-----------|----------|---------|
| /frontend-design | Web UI pages and components — observation forms, import wizards, dashboard views | optional | When building new web pages, forms, or dashboard components for the observation workflow |

## Phase Overrides

None configured.

## Obsidian Sync Requirements

When the extraction workflow or calibration process changes, the corresponding Obsidian document MUST be updated to stay in sync.

| Source (Claude memory/code) | Obsidian Document | Sync Trigger |
|----------------------------|-------------------|--------------|
| `memory/multi-pass-extraction.md` | `D:\QM-Obsidian\Module 4\SIS-4.12.001 Drawing Review - AI Equipment Extraction.md` | Any change to extraction phases, calibration approach, QA tables, or feedback loop |

**Sync rules:**
- After modifying extraction workflow in memory or code, update the Obsidian SOP to match
- Update the `last_synchronized` field in the Obsidian document's frontmatter
- The Obsidian document is written for human readers (non-developers) — translate technical changes into procedure language
- Do NOT add code snippets or Python to the Obsidian document — describe the process, not the implementation

## Templates & Assets

| Asset | Location | Usage |
|-------|----------|-------|
| Integration planning doc | .planning/procore-integration.md | When beneficial — contains config structure, data flow, Procore observation fields, open questions, and existing implementation details |
| Drawing review SOP | D:\QM-Obsidian\Module 4\SIS-4.12.001 Drawing Review - AI Equipment Extraction.md | Human-readable extraction procedure — sync when workflow changes |

---
*Created: 2026-02-25*
*Updated: 2026-03-27 — Added Obsidian sync requirements for extraction workflow*
