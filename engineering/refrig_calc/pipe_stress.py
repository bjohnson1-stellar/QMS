"""
Pipe Stress & Branch Reinforcement Module
==========================================

Extracted from: Pipe_Hoop_Stress_Calculation.xlsx, Pipebranch_B31_5_2016.xlsx

Calculates:
1. Pipe Hoop Stress per Barlow's formula (with weld joint efficiency)
2. Hydrostatic Test Pressures and inner radius calculations
3. Branch Connection Reinforcement per ASME B31.5-2016 Para 504.3.1

Standards Reference:
    ASME B31.5-2016 Refrigeration Piping
    ASME B31.5-2010 Para 504.3.1 (Branch Connections)
    ASTM A53B ERW (carbon steel pipe)
    ASTM A312 (stainless steel pipe)
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


# ==============================================================================
# PIPE DIMENSION DATA
# From Pipe_Hoop_Stress_Calculation.xlsx Sheet2 and PipeWeights.xlsx
# {NPS: {schedule: (OD, wall_thickness)}}
# ==============================================================================

PIPE_DIMENSIONS = {
    0.5:  {"OD": 0.840,  "5": 0.065, "10": 0.083, "10S": 0.083, "40": 0.109, "80": 0.147, "STD": 0.109},
    0.75: {"OD": 1.050,  "5": 0.065, "10": 0.083, "10S": 0.083, "40": 0.113, "80": 0.154, "STD": 0.113},
    1.0:  {"OD": 1.315,  "5": 0.065, "10": 0.109, "10S": 0.109, "40": 0.133, "80": 0.179, "STD": 0.133},
    1.25: {"OD": 1.660,  "5": 0.065, "10": 0.109, "10S": 0.109, "40": 0.140, "80": 0.191, "STD": 0.140},
    1.5:  {"OD": 1.900,  "5": 0.065, "10": 0.109, "10S": 0.109, "40": 0.145, "80": 0.200, "STD": 0.145},
    2.0:  {"OD": 2.375,  "5": 0.065, "10": 0.109, "10S": 0.109, "40": 0.154, "80": 0.218, "STD": 0.154},
    2.5:  {"OD": 2.875,  "5": 0.083, "10": 0.120, "10S": 0.120, "40": 0.203, "80": 0.276, "STD": 0.203},
    3.0:  {"OD": 3.500,  "5": 0.083, "10": 0.120, "10S": 0.120, "40": 0.216, "80": 0.300, "STD": 0.216},
    3.5:  {"OD": 4.000,  "5": 0.083, "10": 0.120, "10S": 0.120, "40": 0.226, "80": 0.318, "STD": 0.226},
    4.0:  {"OD": 4.500,  "5": 0.083, "10": 0.120, "10S": 0.120, "40": 0.237, "80": 0.337, "STD": 0.237},
    5.0:  {"OD": 5.563,  "5": 0.109, "10": 0.134, "10S": 0.134, "40": 0.258, "80": 0.375, "STD": 0.258},
    6.0:  {"OD": 6.625,  "5": 0.109, "10": 0.134, "10S": 0.134, "40": 0.280, "80": 0.432, "STD": 0.280},
    8.0:  {"OD": 8.625,  "5": 0.109, "10": 0.148, "10S": 0.148, "40": 0.322, "80": 0.500, "STD": 0.322},
    10.0: {"OD": 10.750, "5": 0.134, "10": 0.165, "10S": 0.165, "40": 0.365, "80": 0.594, "STD": 0.365},
    12.0: {"OD": 12.750, "5": 0.156, "10": 0.180, "10S": 0.180, "40": 0.406, "80": 0.688, "STD": 0.375},
    14.0: {"OD": 14.000, "5": 0.156, "10": 0.188, "10S": 0.188, "40": 0.438, "80": 0.750, "STD": 0.375},
    16.0: {"OD": 16.000, "5": 0.165, "10": 0.188, "10S": 0.188, "40": 0.500, "80": 0.844, "STD": 0.375},
    18.0: {"OD": 18.000, "5": 0.165, "10": 0.188, "10S": 0.188, "40": 0.562, "80": 0.938, "STD": 0.375},
    20.0: {"OD": 20.000, "5": 0.188, "10": 0.218, "10S": 0.218, "40": 0.594, "80": 1.031, "STD": 0.375},
    24.0: {"OD": 24.000, "5": 0.218, "10": 0.250, "10S": 0.250, "40": 0.688, "80": 1.219, "STD": 0.375},
}

# Material allowable stress values (psi)
# From Pipe_Hoop_Stress_Calculation.xlsx, row 3
MATERIAL_STRESS = {
    "A53B_ERW": 14535,      # ASTM A53 Grade B ERW
    "A53B_SMLS": 17100,     # ASTM A53 Grade B Seamless
    "A106B": 17100,         # ASTM A106 Grade B
    "A312_304": 14600,      # ASTM A312 TP304 SS
    "A312_304L": 13300,     # ASTM A312 TP304L SS
    "A312_316": 14600,      # ASTM A312 TP316 SS
    "A312_316L": 13300,     # ASTM A312 TP316L SS
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HoopStressResult:
    """Result of pipe hoop stress calculation."""
    nps: float
    od_in: float
    wall_thickness_in: float
    schedule: str
    design_pressure_psi: float
    test_pressure_psi: float
    
    # Calculated values
    hoop_stress_psi: float = 0.0
    allowable_stress_psi: float = 0.0
    stress_ratio: float = 0.0  # hoop_stress / allowable
    is_acceptable: bool = False
    
    # Inner radius for hydrostatic test
    inner_radius_in: float = 0.0
    
    notes: List[str] = field(default_factory=list)


@dataclass
class BranchReinforcementResult:
    """Result of ASME B31.5 branch reinforcement calculation."""
    header_nps: float
    branch_nps: float
    header_od_in: float
    branch_od_in: float
    header_wall_in: float
    branch_wall_in: float
    design_pressure_psi: float
    branch_angle_deg: float
    
    # B31.5 calculated values
    d1_in: float = 0.0           # Actual corroded opening
    d2_in: float = 0.0           # Half-width of reinforcement zone
    L4_in: float = 0.0           # Height of reinforcement zone
    
    required_area_in2: float = 0.0
    available_area_in2: float = 0.0  # A1 + A2 + A3 + A4
    A1_in2: float = 0.0         # Area in header wall
    A2_in2: float = 0.0         # Area in branch wall
    A3_in2: float = 0.0         # Area in fillet welds
    A4_in2: float = 0.0         # Area of reinforcement pad
    
    reinforcement_adequate: bool = False
    reinforcement_pad_needed: bool = False
    pad_thickness_required_in: float = 0.0
    
    notes: List[str] = field(default_factory=list)


# ==============================================================================
# PIPE HOOP STRESS CALCULATIONS
# ==============================================================================

def pipe_hoop_stress(design_pressure_psi: float, od_in: float,
                      wall_thickness_in: float, weld_efficiency: float = 0.4) -> float:
    """
    Calculate pipe hoop stress using Barlow's formula with weld joint factor.
    
    Formula (from Pipe_Hoop_Stress_Calculation.xlsx):
        σ = P × (OD - 2 × E × t) / (2 × t)
    
    Where:
        σ = hoop stress (psi)
        P = design pressure (psig)
        OD = outside diameter (inches)
        E = weld joint efficiency (0.4 for ASTM A53B ERW per spreadsheet)
        t = wall thickness (inches)
    
    Args:
        design_pressure_psi: Design pressure in psig
        od_in: Outside diameter in inches
        wall_thickness_in: Wall thickness in inches
        weld_efficiency: Weld joint efficiency factor (default 0.4)
        
    Returns:
        Hoop stress in psi
    """
    if wall_thickness_in <= 0:
        return float('inf')
    
    stress = design_pressure_psi * (od_in - 2 * weld_efficiency * wall_thickness_in) / (2 * wall_thickness_in)
    return stress


def check_pipe_schedule(nps: float, schedule: str, design_pressure_psi: float,
                         material: str = "A53B_ERW",
                         test_pressure_factor: float = 1.1) -> HoopStressResult:
    """
    Check if a pipe schedule is adequate for the design pressure.
    
    Calculates hoop stress and compares to allowable stress for the material.
    Also calculates test pressure (default 1.1× design per standard practice).
    
    From Pipe_Hoop_Stress_Calculation.xlsx:
        Test Pressure = Design Pressure × 1.1
        Inner Radius = OD/2 - wall_thickness
    
    Args:
        nps: Nominal pipe size
        schedule: Pipe schedule ("5", "10", "10S", "40", "80", "STD")
        design_pressure_psi: Design pressure in psig
        material: Material specification key
        test_pressure_factor: Test pressure factor (default 1.1)
        
    Returns:
        HoopStressResult with stress analysis
    """
    if nps not in PIPE_DIMENSIONS:
        raise ValueError(f"NPS {nps} not in database. Available: {sorted(PIPE_DIMENSIONS.keys())}")
    
    pipe = PIPE_DIMENSIONS[nps]
    od = pipe["OD"]
    
    if schedule not in pipe:
        raise ValueError(f"Schedule {schedule} not available for NPS {nps}")
    
    wall = pipe[schedule]
    allowable = MATERIAL_STRESS.get(material, 14535)
    test_pressure = design_pressure_psi * test_pressure_factor
    
    # Hoop stress at design pressure
    stress_design = pipe_hoop_stress(design_pressure_psi, od, wall)
    
    # Hoop stress at test pressure
    stress_test = pipe_hoop_stress(test_pressure, od, wall)
    
    inner_radius = od / 2.0 - wall
    
    result = HoopStressResult(
        nps=nps,
        od_in=od,
        wall_thickness_in=wall,
        schedule=schedule,
        design_pressure_psi=design_pressure_psi,
        test_pressure_psi=test_pressure,
        hoop_stress_psi=stress_design,
        allowable_stress_psi=allowable,
        stress_ratio=stress_design / allowable if allowable > 0 else float('inf'),
        is_acceptable=stress_design <= allowable,
        inner_radius_in=inner_radius,
    )
    
    if not result.is_acceptable:
        result.notes.append(
            f"FAIL: Hoop stress {stress_design:.0f} psi exceeds allowable {allowable:.0f} psi "
            f"for {material}. Consider heavier schedule."
        )
    
    if stress_test > allowable * 0.9:  # 90% of allowable during test
        result.notes.append(
            f"WARNING: Test pressure stress {stress_test:.0f} psi is ≥90% of allowable."
        )
    
    return result


def minimum_wall_thickness(design_pressure_psi: float, od_in: float,
                            material: str = "A53B_ERW",
                            corrosion_allowance: float = 0.03125,
                            weld_efficiency: float = 0.4) -> float:
    """
    Calculate minimum required wall thickness for design pressure.
    
    Formula (rearranged from Barlow's):
        t_min = P × OD / (2 × S + 2 × P × E) + C
    
    Where:
        S = allowable stress
        E = weld efficiency
        C = corrosion allowance
    
    Args:
        design_pressure_psi: Design pressure in psig
        od_in: Outside diameter in inches
        material: Material specification key
        corrosion_allowance: Corrosion allowance in inches (default 1/32")
        weld_efficiency: Weld joint efficiency
        
    Returns:
        Minimum required wall thickness in inches
    """
    S = MATERIAL_STRESS.get(material, 14535)
    
    t_min = (design_pressure_psi * od_in) / (2 * S + 2 * design_pressure_psi * weld_efficiency)
    t_min += corrosion_allowance
    
    return t_min


# ==============================================================================
# ASME B31.5 BRANCH REINFORCEMENT
# ==============================================================================

def branch_reinforcement(header_nps: float, branch_nps: float,
                          design_pressure_psi: float,
                          header_schedule: str = "10S",
                          branch_schedule: str = "10S",
                          branch_angle_deg: float = 90.0,
                          fillet_weld_size: float = 0.375,
                          corrosion_allowance: float = 0.03125,
                          reinforcement_pad_thickness: float = 0.0,
                          material: str = "A312_304",
                          mill_tolerance: float = 0.125) -> BranchReinforcementResult:
    """
    Calculate branch connection reinforcement per ASME B31.5-2016 Para 504.3.1.
    
    Extracted from Pipebranch_B31_5_2016.xlsx Worksheet.
    
    Per ASME B31.5, reinforcement is NOT needed if:
        1. Branch is a fitting per ASME standard (B16.9, B16.11)
        2. Branch ≤ 2" NPS AND ≤ 1/4 of header NPS (for threaded/socket weld)
        3. An integrally reinforced fitting per MSS SP-97 is used
    
    Key calculations:
        d1 = [Dob - 2(Tb - C)] / sin(B)     corroded opening length
        d2 = max(d1, (Tb-C)+(Th-C)+d1/2)    but ≤ Doh
        L4 = min(2.5(Th-C), 2.5(Tb-C)+tr)   reinforcement height
        
        Required area = t_h_req × d1 × (2 - sin(B))
        Available area = A1 + A2 + A3 + A4
    
    Args:
        header_nps: Header nominal pipe size
        branch_nps: Branch nominal pipe size  
        design_pressure_psi: Design pressure (psig)
        header_schedule: Header pipe schedule
        branch_schedule: Branch pipe schedule
        branch_angle_deg: Angle between branch and header (degrees)
        fillet_weld_size: Fillet weld size (inches, default 3/8")
        corrosion_allowance: Corrosion allowance (inches, default 1/32")
        reinforcement_pad_thickness: External pad thickness (0 if none)
        material: Pipe material specification
        mill_tolerance: Mill under-tolerance (inches, default 1/8")
        
    Returns:
        BranchReinforcementResult with complete analysis
    """
    C = corrosion_allowance
    f = fillet_weld_size
    tr = reinforcement_pad_thickness
    u = mill_tolerance
    B_rad = math.radians(branch_angle_deg)
    
    # Get pipe dimensions
    if header_nps not in PIPE_DIMENSIONS or branch_nps not in PIPE_DIMENSIONS:
        raise ValueError("Pipe size not in database")
    
    Doh = PIPE_DIMENSIONS[header_nps]["OD"]
    Dob = PIPE_DIMENSIONS[branch_nps]["OD"]
    
    # Nominal wall thicknesses
    Th_prime = PIPE_DIMENSIONS[header_nps].get(header_schedule, 
               PIPE_DIMENSIONS[header_nps].get("10S", 0.165))
    Tb_prime = PIPE_DIMENSIONS[branch_nps].get(branch_schedule,
               PIPE_DIMENSIONS[branch_nps].get("10S", 0.165))
    
    # Actual wall thickness (nominal - mill tolerance × 87.5%)
    Th = Th_prime * (1 - 0.125)  # 12.5% under-tolerance per ASTM
    Tb = Tb_prime * (1 - 0.125)
    
    # Allowable stress
    Sh = MATERIAL_STRESS.get(material, 14600)
    Sb = Sh  # Same material assumed
    P = design_pressure_psi
    
    # d1 = actual corroded length removed from header
    # d1 = [Dob - 2(Tb - C)] / sin(B)
    d1 = (Dob - 2 * (Tb - C)) / math.sin(B_rad)
    
    # d2 = half-width of reinforcement zone
    # d2 = max(d1, (Tb-C)+(Th-C)+d1/2) but ≤ Doh
    d2_option1 = d1
    d2_option2 = (Tb - C) + (Th - C) + d1 / 2.0
    d2 = max(d2_option1, d2_option2)
    d2 = min(d2, Doh)
    
    # L4 = height of reinforcement zone on branch
    # L4 = min(2.5(Th-C), 2.5(Tb-C)+tr)
    L4_option1 = 2.5 * (Th - C)
    L4_option2 = 2.5 * (Tb - C) + tr
    L4 = min(L4_option1, L4_option2)
    
    # Required wall thickness for header (pressure design)
    # t_h_req = P × Doh / (2 × (Sh + P × 0.4))
    t_h_req = P * Doh / (2 * (Sh + P * 0.4))
    
    # Required wall thickness for branch
    t_b_req = P * Dob / (2 * (Sb + P * 0.4))
    
    # Required reinforcement area
    # A_req = t_h_req × d1 × (2 - sin(B))
    A_req = t_h_req * d1 * (2 - math.sin(B_rad))
    
    # Available area A1 (excess metal in header wall)
    # A1 = (2 × d2 - d1) × (Th - C - t_h_req)
    A1 = (2 * d2 - d1) * max(0, Th - C - t_h_req)
    
    # Available area A2 (excess metal in branch wall)
    # A2 = 2 × L4 × (Tb - C - t_b_req) / sin(B)
    A2 = 2 * L4 * max(0, Tb - C - t_b_req) / math.sin(B_rad)
    
    # Available area A3 (fillet welds)
    # A3 = 2 × 0.5 × f² (two fillet welds, triangular cross section)
    A3 = 2 * 0.5 * f ** 2
    
    # Available area A4 (reinforcement pad)
    # A4 = tr × d2 × 2 (if pad provided)
    A4 = tr * d2 * 2 if tr > 0 else 0.0
    
    A_total = A1 + A2 + A3 + A4
    
    # Check adequacy
    adequate = A_total >= A_req
    
    # Calculate required pad thickness if needed
    pad_needed = not adequate and tr == 0
    pad_required = 0.0
    if pad_needed and d2 > 0:
        deficit = A_req - (A1 + A2 + A3)
        pad_required = deficit / (2 * d2) if deficit > 0 else 0.0
    
    result = BranchReinforcementResult(
        header_nps=header_nps,
        branch_nps=branch_nps,
        header_od_in=Doh,
        branch_od_in=Dob,
        header_wall_in=Th,
        branch_wall_in=Tb,
        design_pressure_psi=design_pressure_psi,
        branch_angle_deg=branch_angle_deg,
        d1_in=d1,
        d2_in=d2,
        L4_in=L4,
        required_area_in2=A_req,
        available_area_in2=A_total,
        A1_in2=A1,
        A2_in2=A2,
        A3_in2=A3,
        A4_in2=A4,
        reinforcement_adequate=adequate,
        reinforcement_pad_needed=pad_needed,
        pad_thickness_required_in=pad_required,
    )
    
    if not adequate:
        result.notes.append(
            f"REINFORCEMENT NEEDED: Required area = {A_req:.3f} in², "
            f"Available = {A_total:.3f} in². "
            f"Pad thickness ≥ {pad_required:.3f}\" recommended."
        )
    
    return result


def is_reinforcement_exempt(header_nps: float, branch_nps: float,
                             connection_type: str = "butt_weld") -> Tuple[bool, str]:
    """
    Check if branch reinforcement calculation is exempt per B31.5.
    
    Exemptions per ASME B31.5:
        1. Fitting per ASME B16.9, B16.11
        2. Threaded/socket weld: branch ≤ 2" AND ≤ 1/4 header NPS
        3. Integrally reinforced per MSS SP-97
    
    Args:
        header_nps: Header NPS
        branch_nps: Branch NPS
        connection_type: "butt_weld", "threaded", "socket_weld", "fitting"
        
    Returns:
        Tuple of (is_exempt, reason)
    """
    if connection_type == "fitting":
        return True, "Standard fitting per ASME B16.9 or B16.11 - exempt"
    
    if connection_type in ("threaded", "socket_weld"):
        if branch_nps <= 2.0 and branch_nps <= header_nps / 4.0:
            return True, f"Branch ≤ 2\" NPS and ≤ 1/4 header ({header_nps/4}\" NPS) - exempt"
    
    return False, "Reinforcement calculation required per B31.5 Para 504.3.1"


# ==============================================================================
# QUICK FUNCTIONS
# ==============================================================================

def quick_hoop_stress_check(nps: float, schedule: str, pressure_psi: float,
                             material: str = "A53B_ERW") -> str:
    """Quick pass/fail hoop stress check."""
    result = check_pipe_schedule(nps, schedule, pressure_psi, material)
    status = "PASS" if result.is_acceptable else "FAIL"
    return (f"{status}: NPS {nps}\" Sch {schedule} at {pressure_psi} psi → "
            f"Hoop stress = {result.hoop_stress_psi:.0f} psi "
            f"(Allowable = {result.allowable_stress_psi:.0f} psi, "
            f"Ratio = {result.stress_ratio:.2f})")
