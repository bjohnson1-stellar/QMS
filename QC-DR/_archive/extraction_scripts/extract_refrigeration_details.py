#!/usr/bin/env python3
"""
Extract refrigeration detail data from drawing sheets and populate database
Project 07308 - BIRDCAGE
"""
import sqlite3
import json
from datetime import datetime

# Drawing data extracted from PDFs
SHEET_52_DATA = {
    'sheet_id': 52,
    'drawing_number': 'R50222-REFRIGERATION-DETAILS-SUPPORTS',
    'title': 'REFRIGERATION DETAILS SUPPORTS',
    'revision': '3',
    'drawing_type': 'detail',
    'complexity': 'medium',
    'discipline': 'Refrigeration',
    'details': [
        {
            'detail_id': '1',
            'detail_title': 'PIPE STAND SUPPORT',
            'detail_type': 'support_standard',
            'description': 'Standard and anchored pipe stand support system with cross members and uprights',
            'materials': 'L2X2X1/4 angle, L3X3X1/4 angle, L4X4X1/4 angle, L4X4X3/8 angle, C6X8.2 channel, C8X11.5 channel base, 2" SCH40 pipe, 3" SCH40 pipe, 4" SCH40 pipe',
            'dimensions': 'Various per stand schedule - see pipe_stand_schedule',
            'notes': '1. All materials shall comply with environmental plan on cover sheet. 2. All hollow supports shall include weep holes to prevent the collection of water.'
        }
    ],
    'pipe_stands': [
        {'stand_number': '1', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 81, 'dim_b': 78, 'dim_c': 182, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '1A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 93, 'dim_b': 78, 'dim_c': 122, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '2', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 78, 'dim_c': 176, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '2A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 84, 'dim_b': 78, 'dim_c': 116, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '3', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 78, 'dim_c': 168, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '3A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 78, 'dim_c': 108, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '4', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 78, 'dim_c': 168, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '4A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 78, 'dim_c': 108, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '5', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 36, 'dim_b': 78, 'dim_c': 152, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '5A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 48, 'dim_b': 78, 'dim_c': 92, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '6', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 60, 'dim_c': 165, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '6A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 84, 'dim_b': 60, 'dim_c': 106, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '7', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 60, 'dim_c': 157, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '7A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 60, 'dim_c': 97, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '8', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 48, 'dim_b': 60, 'dim_c': 149, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '8A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 60, 'dim_c': 89, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '9', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 81, 'dim_b': 42, 'dim_c': 160, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '9A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 93, 'dim_b': 42, 'dim_c': 101, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '10', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 42, 'dim_c': 154, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '10A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 84, 'dim_b': 42, 'dim_c': 95, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '11', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 42, 'dim_c': 146, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '11A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 42, 'dim_c': 87, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '12', 'model': 'Z2C', 'base': 'Z', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 48, 'dim_b': 42, 'dim_c': 138, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '12A', 'model': 'V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 60, 'dim_b': 42, 'dim_c': 79, 'dim_d': None, 'weight': None, 'anchored': True},
        {'stand_number': '13', 'model': 'Z2D', 'base': 'Z', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': 72, 'dim_b': 78, 'dim_c': 202, 'dim_d': None, 'weight': None, 'anchored': False},
        {'stand_number': '13A', 'model': 'V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': 84, 'dim_b': 78, 'dim_c': 143, 'dim_d': None, 'weight': None, 'anchored': True},
    ]
}

SHEET_53_DATA = {
    'sheet_id': 53,
    'drawing_number': 'R50250-REFRIGERATION-DETAILS-SUPPORTS',
    'title': 'REFRIGERATION DETAILS SUPPORTS',
    'revision': '3',
    'drawing_type': 'detail',
    'complexity': 'medium',
    'discipline': 'Refrigeration',
    'details': [
        {
            'detail_id': '1',
            'detail_title': 'DUCT STAND SUPPORT',
            'detail_type': 'support_duct',
            'description': 'Standard and anchored duct stand support system with 1/2" galvanized threaded rod, double nut both ends, L2x2x1/4 angle attachments',
            'materials': 'L2X2X1/4 angle, L3X3X1/4 angle, L4X4X1/4 angle, L4X4X3/8 angle, C6X8.2 channel, C8X11.5 channel base, 2" SCH40 pipe, 3" SCH40 pipe, 4" SCH40 pipe, 1/2" galvanized threaded rod, 3x3x4 thin angle or sheet metal',
            'dimensions': 'Various per stand schedule - see duct_stand_schedule',
            'notes': '1. All materials shall comply with environmental plan on cover sheet. 2. All hollow supports shall include weep holes to prevent the collection of water. Do not tighten bolts down as to cause insulation crushing.'
        }
    ],
    'duct_stands': [
        {'stand_number': 'D1', 'model': 'D:Y2E', 'base': 'Y', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 63, 'dim_b': 170, 'dim_c': 273, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D1A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': 170, 'dim_c': 191, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D2A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': 117, 'dim_c': 151, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D3A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': 270, 'dim_c': 220, 'dim_d': 150, 'weight': None, 'anchored': True, 'notes': 'See isometric below'},
        {'stand_number': 'D4', 'model': 'D:Y2E', 'base': 'Y', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 63, 'dim_b': 98, 'dim_c': 219, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D4A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': 98, 'dim_c': 137, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D5A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': None, 'dim_b': None, 'dim_c': 114, 'dim_d': 150, 'weight': None, 'anchored': True, 'notes': 'See isometric below'},
        {'stand_number': 'D6', 'model': 'D:Y2E', 'base': 'Y', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 63, 'dim_b': None, 'dim_c': 120, 'dim_d': 150, 'weight': None, 'anchored': False, 'notes': 'One leg stand'},
        {'stand_number': 'D7A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': None, 'dim_b': None, 'dim_c': None, 'dim_d': 200, 'weight': None, 'anchored': True, 'notes': 'See isometric below, dim C: 135-135'},
        {'stand_number': 'D8', 'model': 'D:Y2C', 'base': 'Y', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 63, 'dim_b': 86, 'dim_c': 195, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D8A', 'model': 'D:V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 86, 'dim_c': 113, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D9A', 'model': 'D:V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': None, 'dim_b': 86, 'dim_c': 120, 'dim_d': 150, 'weight': None, 'anchored': True, 'notes': 'See isometric below'},
        {'stand_number': 'D10', 'model': 'D:Y2C', 'base': 'Y', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 63, 'dim_b': 68, 'dim_c': 184, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D10A', 'model': 'D:V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 68, 'dim_c': 102, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D11', 'model': 'D:Y2E', 'base': 'Y', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 63, 'dim_b': 138, 'dim_c': 249, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D11A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': 138, 'dim_c': 167, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D12A', 'model': 'D:V2E', 'base': 'V', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 72, 'dim_b': None, 'dim_c': None, 'dim_d': 220, 'weight': None, 'anchored': True, 'notes': 'See isometric below, dim C: 137-120.5'},
        {'stand_number': 'D13', 'model': 'D:Y2C', 'base': 'Y', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 63, 'dim_b': 75, 'dim_c': 188, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D13A', 'model': 'D:V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': 75, 'dim_c': 107, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D14A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': 72, 'dim_b': 108, 'dim_c': 162, 'dim_d': 150, 'weight': None, 'anchored': True},
        {'stand_number': 'D15A', 'model': 'D:V2C', 'base': 'V', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': 72, 'dim_b': None, 'dim_c': 88, 'dim_d': 150, 'weight': None, 'anchored': True, 'notes': 'See isometric below'},
        {'stand_number': 'D16A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': None, 'dim_b': None, 'dim_c': None, 'dim_d': 200, 'weight': None, 'anchored': True, 'notes': 'See isometric below, dim C: 106-106'},
        {'stand_number': 'D17', 'model': 'D:Y2E', 'base': 'Y', 'upright': '2', 'cross_member': 'E', 'cross_member_2': 'E', 'dim_a': 63, 'dim_b': None, 'dim_c': 162, 'dim_d': 150, 'weight': None, 'anchored': False, 'notes': 'One leg stand'},
        {'stand_number': 'D18', 'model': 'D:Y2C', 'base': 'Y', 'upright': '2', 'cross_member': 'C', 'cross_member_2': 'C', 'dim_a': None, 'dim_b': 88, 'dim_c': 154, 'dim_d': 150, 'weight': None, 'anchored': False},
        {'stand_number': 'D18A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': None, 'dim_b': 101, 'dim_c': 150, 'dim_d': 150, 'weight': None, 'anchored': True, 'notes': 'See isometric below'},
        {'stand_number': 'D19A', 'model': 'D:V2D', 'base': 'V', 'upright': '2', 'cross_member': 'D', 'cross_member_2': 'D', 'dim_a': 72, 'dim_b': None, 'dim_c': None, 'dim_d': 220, 'weight': None, 'anchored': True, 'notes': 'See isometric below, dim C: 123-128'},
    ]
}

SHEET_54_DATA = {
    'sheet_id': 54,
    'drawing_number': 'R50300-REFRIGERATION-DETAILS-DUCT',
    'title': 'REFRIGERATION DETAILS DUCT',
    'revision': '3',
    'drawing_type': 'detail',
    'complexity': 'complex',
    'discipline': 'Refrigeration',
    'details': [
        {
            'detail_id': '1',
            'detail_title': 'IMP EXTERIOR DUCT',
            'detail_type': 'duct_exterior',
            'description': '3" insulated metal panel ductwork exterior installation with TPO membrane, vapor barrier, trim, and sealant',
            'materials': '0.045" TPO white roof membrane, 6" pressure sensitive flashing strip, Eternabond vapor barrier, 3x6 trim, 3x3 trim, Masterseal NP150 sealant, 1/4-14x7/8 HWH TEK screws, #10-3/4 Phil truss HD type A 18-8 S.S. screws, pop rivets, 3" IMP',
            'dimensions': '3" typical spacing',
            'notes': 'Foam fill voids, thermal break at panel intersection'
        },
        {
            'detail_id': '2',
            'detail_title': 'IMP EXTERIOR DUCT CORNER',
            'detail_type': 'duct_exterior_corner',
            'description': 'Corner detail for exterior IMP ductwork',
            'materials': 'Peel-N-Seal vapor barrier, 3" IMP ductwork, 3x6 trim, 3x3 trim, Masterseal NP150, 1/4-14x7/8 HWH TEK screws, #10-3/4 Phil truss HD TEK screws, pop rivets with washer painted white',
            'dimensions': '6" O.C. fastener spacing',
            'notes': 'Foam fill void, thermal break at panel intersection'
        },
        {
            'detail_id': '3',
            'detail_title': 'IMP INTERIOR DUCT',
            'detail_type': 'duct_interior',
            'description': '3" insulated metal panel ductwork interior installation',
            'materials': 'Peel-N-Seal vapor barrier, 3" IMP ductwork, 3x6 trim, 3x3 trim, Masterseal NP150, 1/4-14x7/8 HWH TEK screws, pop rivets',
            'dimensions': '3" typical spacing',
            'notes': 'Foam fill voids, thermal break at panel intersection'
        },
        {
            'detail_id': '4',
            'detail_title': 'IMP INTERIOR DUCT CORNER',
            'detail_type': 'duct_interior_corner',
            'description': 'Corner detail for interior IMP ductwork',
            'materials': 'Peel-N-Seal vapor barrier, 3" IMP ductwork, 3x6 trim, Masterseal NP150, 1/4-14x7/8 HWH TEK screws, pop rivets with washer painted white',
            'dimensions': '6" O.C. fastener spacing',
            'notes': 'Foam fill void, thermal break at panel intersection'
        },
        {
            'detail_id': '5',
            'detail_title': 'IMP DUCT CONNECTION',
            'detail_type': 'duct_connection',
            'description': 'Connection detail between IMP duct and AHU unit',
            'materials': 'TPO membrane fully adhered to 3" IMP ductwork, Masterseal NP150, 3x6 trim, Peel-N-Seal vapor barrier, 1/4-14x7/8 HWH TEK screws, pop rivets with washer painted white',
            'dimensions': '6" O.C. fastener spacing',
            'notes': 'Foam fill void, AHU unit by others'
        },
        {
            'detail_id': '6',
            'detail_title': 'IMP DUCT TRANSITION',
            'detail_type': 'duct_transition',
            'description': 'Transition detail for IMP ductwork size changes',
            'materials': 'Flat trim to match IMP finish, 3x3 trim, non-curing butyl sealant, Peel-N-Seal vapor barrier, #10-3/4 Phil truss HD TEK screws, pop rivets',
            'dimensions': '6" O.C. fastener spacing',
            'notes': 'Exterior/interior transition shown'
        },
        {
            'detail_id': '7',
            'detail_title': 'IMP DUCT TRANSITION',
            'detail_type': 'duct_transition_alt',
            'description': 'Alternative transition detail for IMP ductwork',
            'materials': 'TPO membrane fully adhered to 3" IMP ductwork, Masterseal NP150, 3x6 trim, Peel-N-Seal vapor barrier, AHU unit interface',
            'dimensions': 'Varies per application',
            'notes': 'Foam fill void, AHU unit by others'
        },
        {
            'detail_id': '8',
            'detail_title': 'IMP INTERIOR DUCT CORNER',
            'detail_type': 'duct_interior_corner_alt',
            'description': 'Alternative interior corner detail for IMP ductwork',
            'materials': 'Angle trim to match IMP finish, vapor barrier, 3" IMP, TPO membrane, #10-3/4 Phil truss HD TEK screws, 1/4-14x7/8 HWH TEK screws, Masterseal NP150, 6" pressure sensitive flashing strip',
            'dimensions': '6" O.C. fastener spacing',
            'notes': 'Foam fill void, 2" x 1/4" thick washer typical'
        },
        {
            'detail_id': '9',
            'detail_title': 'R5300 9 DUCTWORK MANBARS',
            'detail_type': 'duct_manbar',
            'description': 'Manbar detail for ductwork access',
            'materials': '1/2" solid SST round bar, Carlon B108R-UPC old work box painted to match, food grade caulk, TEK screws, 1/2" lock nut or double nut, 2" x 1/4" thick washer',
            'dimensions': 'Equal spacing typical, 1-0" O.C. max equal',
            'notes': 'Thread rod both ends typical, foam fill box typical, foam fill voids typical'
        },
        {
            'detail_id': '10',
            'detail_title': 'INTERSTITIAL IMP DUCT SUPPORT',
            'detail_type': 'duct_support_interstitial',
            'description': 'Support system for IMP ductwork in interstitial spaces, parallel and perpendicular to joists',
            'materials': 'L2x2x1/4 angle galvanized, threaded rod per specifications double nut both ends, RevNut 12" O.C., 26 gauge exterior skin IMP, joist hanger rod per specifications',
            'dimensions': '12" O.C. RevNuts, locate angle at mid height in interstitial space',
            'notes': 'See attachments on R5210. Two configurations: facing parallel to joists and facing perpendicular to joists'
        }
    ]
}

def populate_database(db_path):
    """Populate database with extracted data"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = {
        'sheets_updated': 0,
        'details_inserted': 0,
        'pipe_stands_inserted': 0,
        'duct_stands_inserted': 0,
        'errors': []
    }

    try:
        # Check if we need to create support schedule tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('refrigeration_pipe_stands', 'refrigeration_duct_stands')
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]

        if 'refrigeration_pipe_stands' not in existing_tables:
            cursor.execute("""
                CREATE TABLE refrigeration_pipe_stands (
                    id INTEGER PRIMARY KEY,
                    sheet_id INTEGER REFERENCES sheets(id),
                    stand_number TEXT NOT NULL,
                    model TEXT,
                    base_type TEXT,
                    upright_type TEXT,
                    cross_member_1 TEXT,
                    cross_member_2 TEXT,
                    dimension_a REAL,
                    dimension_b REAL,
                    dimension_c REAL,
                    dimension_d REAL,
                    weight_lbs REAL,
                    is_anchored INTEGER DEFAULT 0,
                    notes TEXT,
                    confidence REAL DEFAULT 0.95,
                    UNIQUE(sheet_id, stand_number)
                )
            """)

        if 'refrigeration_duct_stands' not in existing_tables:
            cursor.execute("""
                CREATE TABLE refrigeration_duct_stands (
                    id INTEGER PRIMARY KEY,
                    sheet_id INTEGER REFERENCES sheets(id),
                    stand_number TEXT NOT NULL,
                    model TEXT,
                    base_type TEXT,
                    upright_type TEXT,
                    cross_member_1 TEXT,
                    cross_member_2 TEXT,
                    dimension_a REAL,
                    dimension_b REAL,
                    dimension_c REAL,
                    dimension_d REAL,
                    weight_lbs REAL,
                    is_anchored INTEGER DEFAULT 0,
                    notes TEXT,
                    confidence REAL DEFAULT 0.95,
                    UNIQUE(sheet_id, stand_number)
                )
            """)

        # Process Sheet 52 - Pipe Stands
        sheet_data = SHEET_52_DATA
        cursor.execute("""
            UPDATE sheets
            SET title = ?,
                drawing_type = ?,
                complexity = ?,
                extracted_at = ?,
                extraction_model = 'sonnet-4.5',
                quality_score = 0.92
            WHERE id = ?
        """, (sheet_data['title'], sheet_data['drawing_type'],
              sheet_data['complexity'], datetime.now().isoformat(), sheet_data['sheet_id']))
        results['sheets_updated'] += 1

        # Insert details
        for detail in sheet_data['details']:
            cursor.execute("""
                INSERT OR REPLACE INTO drawing_details
                (sheet_id, detail_id, detail_title, detail_type, description, materials, dimensions, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_data['sheet_id'], detail['detail_id'], detail['detail_title'],
                  detail['detail_type'], detail['description'], detail['materials'],
                  detail['dimensions'], detail['notes'], 0.92))
            results['details_inserted'] += 1

        # Insert pipe stands
        for stand in sheet_data['pipe_stands']:
            cursor.execute("""
                INSERT OR REPLACE INTO refrigeration_pipe_stands
                (sheet_id, stand_number, model, base_type, upright_type, cross_member_1, cross_member_2,
                 dimension_a, dimension_b, dimension_c, dimension_d, is_anchored, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_data['sheet_id'], stand['stand_number'], stand['model'], stand['base'],
                  stand['upright'], stand['cross_member'], stand['cross_member_2'],
                  stand['dim_a'], stand['dim_b'], stand['dim_c'], stand['dim_d'],
                  1 if stand['anchored'] else 0, 0.95))
            results['pipe_stands_inserted'] += 1

        # Process Sheet 53 - Duct Stands
        sheet_data = SHEET_53_DATA
        cursor.execute("""
            UPDATE sheets
            SET title = ?,
                drawing_type = ?,
                complexity = ?,
                extracted_at = ?,
                extraction_model = 'sonnet-4.5',
                quality_score = 0.90
            WHERE id = ?
        """, (sheet_data['title'], sheet_data['drawing_type'],
              sheet_data['complexity'], datetime.now().isoformat(), sheet_data['sheet_id']))
        results['sheets_updated'] += 1

        # Insert details
        for detail in sheet_data['details']:
            cursor.execute("""
                INSERT OR REPLACE INTO drawing_details
                (sheet_id, detail_id, detail_title, detail_type, description, materials, dimensions, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_data['sheet_id'], detail['detail_id'], detail['detail_title'],
                  detail['detail_type'], detail['description'], detail['materials'],
                  detail['dimensions'], detail['notes'], 0.90))
            results['details_inserted'] += 1

        # Insert duct stands
        for stand in sheet_data['duct_stands']:
            notes = stand.get('notes', '')
            cursor.execute("""
                INSERT OR REPLACE INTO refrigeration_duct_stands
                (sheet_id, stand_number, model, base_type, upright_type, cross_member_1, cross_member_2,
                 dimension_a, dimension_b, dimension_c, dimension_d, is_anchored, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_data['sheet_id'], stand['stand_number'], stand['model'], stand['base'],
                  stand['upright'], stand['cross_member'], stand['cross_member_2'],
                  stand['dim_a'], stand['dim_b'], stand['dim_c'], stand['dim_d'],
                  1 if stand['anchored'] else 0, notes, 0.90))
            results['duct_stands_inserted'] += 1

        # Process Sheet 54 - Duct Details
        sheet_data = SHEET_54_DATA
        cursor.execute("""
            UPDATE sheets
            SET title = ?,
                drawing_type = ?,
                complexity = ?,
                extracted_at = ?,
                extraction_model = 'sonnet-4.5',
                quality_score = 0.88
            WHERE id = ?
        """, (sheet_data['title'], sheet_data['drawing_type'],
              sheet_data['complexity'], datetime.now().isoformat(), sheet_data['sheet_id']))
        results['sheets_updated'] += 1

        # Insert details
        for detail in sheet_data['details']:
            cursor.execute("""
                INSERT OR REPLACE INTO drawing_details
                (sheet_id, detail_id, detail_title, detail_type, description, materials, dimensions, notes, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sheet_data['sheet_id'], detail['detail_id'], detail['detail_title'],
                  detail['detail_type'], detail['description'], detail['materials'],
                  detail['dimensions'], detail['notes'], 0.88))
            results['details_inserted'] += 1

        conn.commit()

    except Exception as e:
        conn.rollback()
        results['errors'].append(str(e))
        raise
    finally:
        conn.close()

    return results

if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'D:/quality.db'

    results = populate_database(db_path)
    print(json.dumps(results, indent=2))
