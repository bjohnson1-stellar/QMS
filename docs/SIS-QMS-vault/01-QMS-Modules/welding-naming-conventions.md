---
document: WP-003
title: Welding Document Naming Conventions
status: Active
revision: 0
effective_date: 2026-02-18
module: welding
tags: [welding-program, naming-convention, controlled-document]
created: 2026-02-18
---

# Welding Document Naming Conventions

Formal reference: `data/quality-documents/Procedures/WP-003-Welding-Document-Naming-Conventions.md`

## WPS Format

`{Material}-{Seq}-P{num}-{Process}[-Modifier]`

| Code | Material |
|------|----------|
| CS | Carbon Steel |
| SS | Stainless Steel |
| DM | Dissimilar Metal (uses P8_P1 underscore) |

## PQR Format

New: mirrors WPS number. Legacy formats retained for historical records.

## WPQ Format

`{Stamp}-{WPS_Number}` when WPS known, else `{Stamp}-{Process}`

## Stamp Format

`{LastInitial}{NN}` - no dash, zero-padded (e.g., B01, B15, M22)

## WPS-PQR Cross-Reference

| WPS | PQR(s) |
|-----|--------|
| CS-01-P1-SMAW | A53-NPS6-6G-6010-7018-3, A333-NPS6-6G-6010-7018 |
| CS-02-P1-GTAW/SMAW | A106-NPS2-6G-ER70S-7018, A106-NPS6-6G-ER70S-7018 |
| CS-03-P1-GTAW | CS-03-P1-GTAW |
| CS-04-P1-SMAW-Low Temp | A333-NPS6-6G-8010-8018 |
| CS-05-P1-GTAW/SMAW-Low Temp | A333-NPS2-6G-ER80S-8018, A333-NPS6-6G-ER80S-E8018 |
| DM-01-P8_P1-GTAW | 1-6G-12 |
| SS-01-P8-GTAW | SS-01-P8-GTAW |

## Normalization Rules

Applied by `_normalize_wpq_number()` in `welding/migrations.py`:

1. Strip whitespace, uppercase
2. `=` to `-`
3. `_` to `-` (except P8_P1)
4. Collapse `--`, strip trailing `-`
5. Process separators to `/` (GTAW_SMAW to GTAW/SMAW)

## Related

- [[welding]] - Module overview
- [[automation]] - JSON request intake
