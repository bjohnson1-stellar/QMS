---
tags: [architecture, equipment, pattern, pipeline]
created: 2026-03-25
---

# Equipment Three-Tier Pattern

> **Type → Variant → Instance**: a three-tier hierarchy that models equipment from submittal through lifecycle without schema changes.

## How It Works in Practice

### Submittal Phase
- Engineer submits one package for "Evaporator Model ABC" → links to `equipment_types`
- Separate shop drawing submittals for LH and RH configs → links to `equipment_variants`
- Approval at type level cascades to all 12 instances automatically

### Receiving
- EC-3 arrives on site → receiving inspection links to `equipment_instances` (EC-3 specifically)
- Serial number recorded, condition documented
- EC-3 advances from "Approved" to "Received"

### Installation
- EC-3 installed → installation inspection links to instance
- Inspector verifies: correct variant (left-hand) in correct location, per shop drawing
- EC-3 advances to "Installed"

### Lifecycle Rollup
- "How are our evaporators doing?" → query all 12 instances, show stage distribution
- "Is the evaporator submittal approved?" → one check at type level covers all 12
- "Which units still need startup?" → filter instances by stage

## Edge Cases

| Scenario | How It Works |
|----------|-------------|
| All 12 same model, no variants | Type + 12 instances (variant is null) |
| 6 left, 6 right | Type + 2 variants + 12 instances |
| Same model, different voltages per location | Type + voltage variants + instances |
| Manufacturer substitution mid-project | New type record, link new instances to it, old instances keep original type |
| One unit replaced under warranty | New instance with same tag, old instance archived with "replaced" status |
| Spare unit procured but not installed | Instance with stage "stored", no location assigned |

## Scalability

This three-tier pattern scales from "12 identical evaporators" down to "1 unique chiller" (type + 1 instance, no variants) and up to "200 VAV boxes in 8 configurations" without any schema changes.

## Related Notes
- [[Architecture Overview]]
- [[Database Overview]]
