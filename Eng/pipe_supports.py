"""
Pipe Weights, Support Stands, and Slope Module
================================================

Extracted from: PipeWeights.xlsx, Stand_WorksheetPipe.xlsx, Stand_WorksheetDuct.xlsx

Calculates:
- Pipe weight (empty, with refrigerant, with insulation)
- Support stand selection (cross member capacity, upright sizing)
- Pipe slope calculations (BOI, drop per distance)
- Support spacing per ASME B31.5

Key data from PipeWeights.xlsx:
    Pipe weights for NH3, R-22, R-404, CO2 systems
    Carbon steel and stainless steel weights per schedule
    Duct weights

Key data from Stand_WorksheetPipe.xlsx:
    Cross member load ratings by span
    Stand model numbering (base, upright, cross member)
    Slope calculation with stand spacing
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


# ==============================================================================
# PIPE WEIGHT DATA - CARBON STEEL (lb/ft)
# From PipeWeights.xlsx "Pipe Weights (Carbon Steel)" and "Carbon v SS" sheets
# {NPS: {schedule: weight_lb_per_ft_empty}}
# ==============================================================================

CARBON_STEEL_PIPE_WEIGHT = {
    # NPS: {schedule: lb/ft empty}
    0.5:  {"40": 0.85, "80": 1.09, "10": 0.67},
    0.75: {"40": 1.13, "80": 1.47, "10": 0.86},
    1.0:  {"40": 1.68, "80": 2.17, "10": 1.40},
    1.25: {"40": 2.27, "80": 3.00, "10": 1.81},
    1.5:  {"40": 2.72, "80": 3.63, "10": 2.09},
    2.0:  {"40": 3.65, "80": 5.02, "10": 2.64},
    2.5:  {"40": 5.79, "80": 7.66, "10": 3.53},
    3.0:  {"40": 7.58, "80": 10.25, "10": 4.33},
    3.5:  {"40": 9.11, "80": 12.51, "10": 5.06},
    4.0:  {"40": 10.79, "80": 14.98, "10": 5.61},
    5.0:  {"40": 14.62, "80": 20.78, "10": 7.77},
    6.0:  {"40": 18.97, "80": 28.57, "10": 9.29},
    8.0:  {"40": 28.55, "80": 43.39, "10": 13.40},
    10.0: {"40": 40.48, "80": 64.43, "10": 18.65},
    12.0: {"40": 49.56, "80": 88.63, "STD": 49.56, "10": 22.18},
    14.0: {"40": 63.44, "STD": 54.57, "10": 27.73},
    16.0: {"40": 82.77, "STD": 62.58, "10": 31.75},
    18.0: {"40": 104.76, "STD": 70.59, "10": 35.76},
    20.0: {"40": 122.91, "STD": 78.60, "10": 43.77},
    24.0: {"40": 171.17, "STD": 94.62, "10": 63.41},
}

STAINLESS_STEEL_PIPE_WEIGHT = {
    # NPS: {schedule: lb/ft empty} - Sch 10S / 40S
    0.5:  {"10S": 0.67, "40S": 1.09},
    0.75: {"10S": 0.86, "40S": 1.13},
    1.0:  {"10S": 1.40, "40S": 1.68},
    1.25: {"10S": 1.81, "40S": 2.27},
    1.5:  {"10S": 2.09, "40S": 2.72},
    2.0:  {"10S": 2.64, "40S": 3.65},
    2.5:  {"10S": 3.53, "40S": 5.79},
    3.0:  {"10S": 4.33, "40S": 7.58},
    4.0:  {"10S": 5.61, "40S": 10.79},
    5.0:  {"10S": 7.77, "40S": 14.62},
    6.0:  {"10S": 9.29, "40S": 18.97},
    8.0:  {"10S": 13.40, "40S": 28.55},
    10.0: {"10S": 18.65, "40S": 40.48},
    12.0: {"10S": 22.18, "40S": 49.56},
    16.0: {"10S": 31.75, "40S": 82.77},
    20.0: {"10S": 43.77, "40S": 122.91},
}


# ==============================================================================
# REFRIGERANT CONTENT WEIGHTS (lb/ft of pipe)
# From PipeWeights.xlsx - content weights based on pipe service
# ==============================================================================

# Liquid density (lb/ft³) at typical operating conditions
REFRIGERANT_DENSITY = {
    "NH3": 37.68,    # at ~28°F
    "R-22": 74.54,
    "R-404": 64.17,
    "CO2": 57.50,
}

# Pipe ID data (inches) for common schedules
PIPE_ID = {
    # NPS: (Sch 40 ID, Sch 80 ID, Sch 10 ID)
    0.5:  (0.622, 0.546, 0.674),
    0.75: (0.824, 0.742, 0.884),
    1.0:  (1.049, 0.957, 1.097),
    1.25: (1.380, 1.278, 1.442),
    1.5:  (1.610, 1.500, 1.682),
    2.0:  (2.067, 1.939, 2.157),
    2.5:  (2.469, 2.323, 2.635),
    3.0:  (3.068, 2.900, 3.260),
    4.0:  (4.026, 3.826, 4.260),
    5.0:  (5.047, 4.813, 5.295),
    6.0:  (6.065, 5.761, 6.357),
    8.0:  (7.981, 7.625, 8.329),
    10.0: (10.020, 9.562, 10.420),
    12.0: (11.938, 11.374, 12.390),
    14.0: (13.124, 12.500, 13.624),
    16.0: (15.000, 14.312, 15.624),
    18.0: (16.876, 16.124, 17.624),
    20.0: (18.812, 17.938, 19.564),
    24.0: (22.624, 21.562, 23.500),
}


def pipe_content_weight(nps: float, schedule: str = "40",
                         refrigerant: str = "NH3",
                         fill_fraction: float = 1.0) -> float:
    """
    Calculate weight of refrigerant content per foot of pipe.
    
    Formula:
        W_content = π/4 × (ID/12)² × ρ × fill_fraction
    
    Args:
        nps: Nominal pipe size
        schedule: Pipe schedule
        refrigerant: "NH3", "R-22", "R-404", "CO2"
        fill_fraction: Fill fraction (1.0 = full liquid, 0.25 = 25% wet suction)
        
    Returns:
        Content weight in lb/ft
    """
    if nps not in PIPE_ID:
        return 0.0
    
    # Get ID based on schedule
    ids = PIPE_ID[nps]
    if schedule in ("40", "STD"):
        pipe_id = ids[0]
    elif schedule == "80":
        pipe_id = ids[1]
    else:
        pipe_id = ids[2]  # Sch 10
    
    density = REFRIGERANT_DENSITY.get(refrigerant, 40.0)
    
    # Cross-sectional area in ft²
    area_ft2 = math.pi / 4 * (pipe_id / 12.0) ** 2
    
    return area_ft2 * density * fill_fraction


def pipe_total_weight(nps: float, schedule: str = "40",
                       material: str = "carbon",
                       refrigerant: str = "NH3",
                       service: str = "liquid",
                       insulation_weight_lb_per_ft: float = 0.0) -> float:
    """
    Calculate total weight per foot of pipe (steel + content + insulation).
    
    Service types and fill fractions (from PipeWeights.xlsx):
        "wet_suction": 25% full of liquid
        "liquid": 100% full of liquid
        "dry_suction": empty (vapor only)
        "hot_gas": empty (vapor only)
        "defrost_condensate": 25% full
    
    Args:
        nps: Nominal pipe size
        schedule: Pipe schedule
        material: "carbon" or "stainless"
        refrigerant: Refrigerant type
        service: "wet_suction", "liquid", "dry_suction", "hot_gas"
        insulation_weight_lb_per_ft: Additional insulation weight
        
    Returns:
        Total weight in lb/ft
    """
    # Pipe weight
    if material == "stainless":
        sch_key = "10S" if schedule in ("10", "10S") else "40S"
        pipe_wt = STAINLESS_STEEL_PIPE_WEIGHT.get(nps, {}).get(sch_key, 0)
    else:
        pipe_wt = CARBON_STEEL_PIPE_WEIGHT.get(nps, {}).get(schedule, 0)
    
    # Content fill fraction
    fill_map = {
        "wet_suction": 0.25,
        "liquid": 1.0,
        "dry_suction": 0.0,
        "hot_gas": 0.0,
        "defrost_condensate": 0.25,
        "discharge": 0.0,
    }
    fill = fill_map.get(service, 0.0)
    
    content_wt = pipe_content_weight(nps, schedule, refrigerant, fill)
    
    return pipe_wt + content_wt + insulation_weight_lb_per_ft


# ==============================================================================
# SUPPORT STAND DATA
# From Stand_WorksheetPipe.xlsx "Stands" sheet
# ==============================================================================

# Cross member maximum weight capacity (lb) at various spans
# {label: {span_ft: max_weight_lb}}
CROSS_MEMBERS = {
    "A": {"member": "L2x2x1/4",   "spans": {2: 700, 3: 500, 4: 300, 5: 200}},
    "B": {"member": "L3x3x1/4",   "spans": {2: 1900, 3: 1200, 4: 900, 5: 700, 6: 600}},
    "C": {"member": "L4x4x1/4",   "spans": {2: 3400, 3: 2300, 4: 1700, 5: 1300, 6: 1100, 8: 800, 10: 600}},
    "D": {"member": "L4x4x3/8",   "spans": {2: 5000, 3: 3300, 4: 2500, 5: 2000, 6: 1600, 8: 1200, 10: 1000}},
    "E": {"member": "L5x5x3/8",   "spans": {2: 8000, 3: 5300, 4: 4000, 5: 3200, 6: 2600, 8: 2000, 10: 1600}},
    "F": {"member": "L6x6x3/8",   "spans": {2: 12000, 3: 8000, 4: 6000, 5: 4800, 6: 4000, 8: 3000, 10: 2400}},
    "G": {"member": "L8x8x1/2",   "spans": {2: 22000, 3: 14700, 4: 11000, 5: 8800, 6: 7300, 8: 5500, 10: 4400}},
}

# Stand base types
STAND_BASES = {
    "Y": "Floor-mounted Y-base",
    "V": "Floor-mounted V-base (with anchor offset)",
    "T": "Trapeze/overhead",
    "W": "Wall bracket",
}

# Upright heights (typical options in inches)
UPRIGHT_OPTIONS = [1, 2, 3, 4, 5, 6]  # Feet


@dataclass
class StandSelection:
    """Result of pipe stand selection."""
    stand_number: str = ""
    stand_model: str = ""       # e.g. "Y2C" = Y-base, 2ft upright, C cross member
    base_type: str = ""         # Y, V, T, W
    upright_height_ft: float = 0
    cross_member_label: str = ""
    cross_member_size: str = ""
    
    a_dim_in: float = 0        # Anchor offset dimension
    b_dim_in: float = 0        # Base width
    c_dim_in: float = 0        # Height to cross member
    
    total_weight_on_stand_lb: float = 0
    max_capacity_lb: float = 0
    utilization_pct: float = 0
    is_adequate: bool = False
    
    notes: List[str] = field(default_factory=list)


def select_cross_member(total_weight_lb: float, span_ft: float,
                          safety_factor: float = 0.10) -> str:
    """
    Select minimum cross member for given weight and span.
    
    From Stand_WorksheetPipe.xlsx: Weight safety factor default = 10%.
    
    Args:
        total_weight_lb: Total weight on cross member (lb)
        span_ft: Cross member span (ft)
        safety_factor: Weight safety factor (default 10%)
        
    Returns:
        Cross member label (A through G) or "NONE" if no member adequate
    """
    required = total_weight_lb * (1 + safety_factor)
    
    for label in ["A", "B", "C", "D", "E", "F", "G"]:
        spans = CROSS_MEMBERS[label]["spans"]
        # Find nearest span (round up)
        available_spans = sorted(spans.keys())
        for s in available_spans:
            if s >= span_ft:
                if spans[s] >= required:
                    return label
                break
    
    return "NONE"


def select_stand(pipes: List[Dict], stand_spacing_ft: float = 10.0,
                  upright_height_ft: float = 2.0,
                  base_type: str = "Y",
                  safety_factor: float = 0.10,
                  is_anchored: bool = False) -> StandSelection:
    """
    Select a pipe support stand for a set of pipes.
    
    Args:
        pipes: List of dicts with keys: "nps", "schedule", "material", 
               "refrigerant", "service", "weight_lb_per_ft" (optional override)
        stand_spacing_ft: Distance between stands (ft)
        upright_height_ft: Upright height (ft)
        base_type: Stand base type ("Y", "V", "T", "W")
        safety_factor: Weight safety factor
        is_anchored: Add 12 lb for anchor bolt hardware
        
    Returns:
        StandSelection with model and capacity check
    """
    # Calculate total weight per foot
    total_wt_per_ft = 0
    for pipe in pipes:
        if "weight_lb_per_ft" in pipe:
            total_wt_per_ft += pipe["weight_lb_per_ft"]
        else:
            wt = pipe_total_weight(
                nps=pipe.get("nps", 2),
                schedule=pipe.get("schedule", "40"),
                material=pipe.get("material", "carbon"),
                refrigerant=pipe.get("refrigerant", "NH3"),
                service=pipe.get("service", "liquid"),
            )
            total_wt_per_ft += wt
    
    # Total weight on one stand
    total_weight = total_wt_per_ft * stand_spacing_ft
    if is_anchored:
        total_weight += 12  # Anchor hardware weight
    
    # Estimate span based on number of pipes and spacing
    # Cross member span = total width occupied by pipes
    n_pipes = len(pipes)
    spacing_between = 2.0  # Assume 2" between pipe centers (minimum)
    largest_pipe = max((p.get("nps", 2) for p in pipes), default=2)
    span_ft = (n_pipes * (largest_pipe + spacing_between)) / 12.0
    span_ft = max(span_ft, 2.0)  # Minimum 2 ft span
    
    # Select cross member
    cm_label = select_cross_member(total_weight, span_ft, safety_factor)
    
    result = StandSelection(
        base_type=base_type,
        upright_height_ft=upright_height_ft,
        cross_member_label=cm_label,
        total_weight_on_stand_lb=total_weight,
    )
    
    if cm_label != "NONE":
        result.cross_member_size = CROSS_MEMBERS[cm_label]["member"]
        result.stand_model = f"{base_type}{int(upright_height_ft)}{cm_label}"
        
        # Get capacity at nearest span
        spans = CROSS_MEMBERS[cm_label]["spans"]
        nearest_span = min(spans.keys(), key=lambda s: abs(s - span_ft) if s >= span_ft else 999)
        result.max_capacity_lb = spans.get(nearest_span, 0)
        result.utilization_pct = (total_weight / result.max_capacity_lb * 100) if result.max_capacity_lb > 0 else 999
        result.is_adequate = result.utilization_pct <= 100
    
    return result


# ==============================================================================
# PIPE SLOPE CALCULATIONS
# From Stand_WorksheetPipe.xlsx "Slope" sheet
# ==============================================================================

@dataclass
class SlopeResult:
    """Pipe slope calculation result."""
    starting_boi_in: float       # Bottom of insulation at start
    slope_in_per_ft: float       # Slope in inches per foot
    slope_direction: str         # "Towards" or "Away"
    total_drop_in: float         # Total drop over distance
    end_boi_in: float           # BOI at end of run
    stand_heights: List[float] = field(default_factory=list)  # Heights at each stand


def calculate_pipe_slope(starting_boi_in: float, slope_in: float,
                          over_distance_ft: float,
                          direction: str = "Towards",
                          stand_spacing_in: float = 120,
                          roof_slope_in: float = 0,
                          roof_distance_ft: float = 0,
                          roof_direction: str = "Away") -> SlopeResult:
    """
    Calculate pipe slope and BOI at each stand location.
    
    From Stand_WorksheetPipe.xlsx "Slope" sheet:
        Slope (decimal) = slope_in / (over_distance_ft × 12)
        
    Pipe slopes towards receiver/accumulator typically.
    Must also account for roof slope to determine actual support heights.
    
    Args:
        starting_boi_in: Starting bottom-of-insulation height (inches)
        slope_in: Total slope (inches) over the distance
        over_distance_ft: Horizontal distance (feet)
        direction: "Towards" (downhill) or "Away" (uphill)
        stand_spacing_in: Space between stands (inches)
        roof_slope_in: Roof slope (inches)
        roof_distance_ft: Roof slope distance (feet)
        roof_direction: Roof slope direction
        
    Returns:
        SlopeResult with BOI at each stand
    """
    if over_distance_ft <= 0:
        return SlopeResult(starting_boi_in, 0, direction, 0, starting_boi_in)
    
    slope_decimal = slope_in / (over_distance_ft * 12.0)  # in/in
    
    if direction.lower() == "towards":
        sign = -1  # Pipe drops
    else:
        sign = 1   # Pipe rises
    
    total_drop = slope_in * sign
    end_boi = starting_boi_in + total_drop
    
    # Calculate BOI at each stand position
    stand_heights = []
    n_stands = int((over_distance_ft * 12) / stand_spacing_in) + 1
    
    for i in range(n_stands + 1):
        dist_in = i * stand_spacing_in
        if dist_in > over_distance_ft * 12:
            break
        
        pipe_boi = starting_boi_in + sign * slope_decimal * dist_in
        
        # Account for roof slope if applicable
        if roof_distance_ft > 0:
            roof_slope_decimal = roof_slope_in / (roof_distance_ft * 12.0)
            roof_sign = 1 if roof_direction.lower() == "away" else -1
            roof_adj = roof_sign * roof_slope_decimal * dist_in
            pipe_boi += roof_adj
        
        stand_heights.append(round(pipe_boi, 2))
    
    return SlopeResult(
        starting_boi_in=starting_boi_in,
        slope_in_per_ft=slope_decimal * 12.0,
        slope_direction=direction,
        total_drop_in=abs(total_drop),
        end_boi_in=end_boi,
        stand_heights=stand_heights,
    )
