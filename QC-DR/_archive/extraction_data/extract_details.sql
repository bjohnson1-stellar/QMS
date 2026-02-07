BEGIN TRANSACTION;

-- Sheet 46: R50104 - REFRIGERATION DETAILS PIPE AND EQUIPMENT
INSERT OR IGNORE INTO drawing_details (sheet_id, detail_id, detail_title, detail_type, description, materials, notes, confidence)
VALUES
(46, '1', 'ROOF CURB-SINGLE DUCT PENETRATION', 'support_detail', 'Roof curb detail for single duct penetration with foam fill and insulation', 'Factory sloped curb base, curb flashing, duct insulation, foam fill', 'Curb must be secured to structure per manufacturers design. See structural for reinforcement framing.', 0.95),
(46, '2', 'ROOF CURB-SINGLE DUCT PENETRATION (SECTION)', 'support_detail', 'Section view of roof curb single duct penetration', 'IMP panel, damper tray, filter rack, manufacturer provided galvanized sheet metal sleeve', 'Provide double wall curb, no fiberglass or wool insulation. Electrical wiring routed through curb.', 0.95),
(46, '3', 'LOUVER IN IMP WALL', 'equipment_detail', 'Louver installation in IMP wall with drainable configuration', 'Perimeter frame, bird/insect screen, aluminum base sill drip lip', 'Provide drainable louver. Install per manufacturers recommendations.', 0.95),
(46, '4', 'ROOF CURB ADAPTER/REDUCER FOR EXHAUST FAN', 'equipment_detail', 'Roof curb adapter and reducer details for exhaust fan installation', 'Curb adapter, curb cap W&L, 1 inch self-tapping screws with hex head and neoprene washers', 'Continuous 1 inch minimum pressure sensitive tape to seal edge. Screws at 12 inch intervals on all sides.', 0.90),
(46, '6', 'TYPICAL HEATER MOUNTING', 'equipment_detail', 'Various heater mounting configurations: ceiling, pole, and wall mounted', 'Wall mounted: 1/2 inch U-bolt, flat washer, lock washer, nut, mounting bracket, 5/8 inch bolt. Ceiling: 5/8 inch threaded rod, jam nut, 3/8 inch mounting bolt', 'Discharge of heater shall not be directed towards refrigeration piping or equipment. Minimum installation clearances: 30 inch, 72 inch.', 0.92);

-- Sheet 47: R50210 - REFRIGERATION DETAILS SUPPORTS
INSERT OR IGNORE INTO drawing_details (sheet_id, detail_id, detail_title, detail_type, description, materials, notes, confidence)
VALUES
(47, 'A', 'WELDED BEAM ATTACHMENT', 'support_detail', 'Welded beam attachment with weldless eye nut', 'Anvil Fig 66 welded beam attachment, Anvil Fig 290 weldless eye nut, Anvil Fig 140/146/253 hanger rod, hex nut', 'Allows for pipe movement. Apply cold-galvanized paint to all field welds. 3/16 inch weld typical.', 0.95),
(47, 'B', 'WELDED BEAM ATTACHMENT', 'support_detail', 'Welded beam attachment with hex nut configuration', 'Anvil Fig 66 welded beam attachment, Anvil Fig 140/146/253 hanger rod, hex nut, lock nut or double nut', 'Apply cold-galvanized paint to all field welds. 3/16 inch weld typical.', 0.95),
(47, 'C', 'DOUBLE HEX NUT ATTACHMENT', 'support_detail', 'Double hex nut attachment to miscellaneous building steel', 'Anvil Fig 140/146/253 hanger rod, hex nut, double nut or lock nut', 'Drill hole 1/8 inch larger than hanger rod diameter.', 0.93),
(47, 'D', 'STEEL WASHER PLATE', 'support_detail', 'Steel washer plate attachment for back to back structural members', 'Anvil Fig 60 steel washer plate, Anvil Fig 140/146/253 hanger rod, hex nut', 'For back to back building structural steel members.', 0.92),
(47, 'H', 'TYPICAL HANGER AT BEAM DETAIL', 'support_detail', 'Typical hanger rod attachment at beam with support angle', 'Support angle by refrigeration contractor, hanger rod per R0001, hex nut, double nut or lock nut', 'Apply cold-galvanized paint to all field welds. 3/16 inch weld typical. 6 inch minimum from beam.', 0.94),
(47, 'I', 'TYPICAL HANGER AT DOUBLE JOIST DETAIL', 'support_detail', 'Hanger rod attachment at double joist configuration', 'Support angle by refrigeration contractor, hanger rod per R0001, hex nut, double nut or lock nut', 'Apply cold-galvanized paint to all field welds. 3/16 inch weld typical. 6 inch minimum spacing.', 0.94),
(47, 'J', 'PIPE SUPPORT FROM JOIST DETAIL', 'support_detail', 'Pipe support from joist with additional web member if required', 'Anvil Fig 140/146/253 hanger rod, 1/4 inch washer plate, hex nut, lock nut or double nut, L2x2x1/4 web member, L4x4x3/8', 'Additional L2x2x1/4 web member required if load falls at 6 inch or greater from panel points (150 lb max without brace). Max field cut bolt hole 3/4 inch diameter.', 0.93),
(47, 'K', 'IMP CEILING PIPE SUPPORT UP TO 2 INCH', 'support_detail', 'IMP ceiling penetration for pipe support up to 2 inch diameter', '1/2 inch hanger rod, 1/2 inch lock nut or double nut, Carlon B108R-UPC old work box, 2 inch x 1/4 inch square washer, Pipe Tite PT1-000', 'Hole through IMP ceiling to be 1/2 inch larger than rod diameter. Foam fill gap with urethane insulation. For drain lines 2 inch and below only.', 0.92);

-- Sheet 48: R50200 - REFRIGERATION DETAILS SUPPORTS
INSERT OR IGNORE INTO drawing_details (sheet_id, detail_id, detail_title, detail_type, description, materials, notes, confidence)
VALUES
(48, '2', 'IMP CEILING AHU SUPPORT', 'equipment_detail', 'Air handling unit support through IMP ceiling', 'Hanger rod per specifications, hex nut, lock nut or double nut', 'Furnished and installed by refrigeration contractor. All evaporator mounting holes used. Top of hanger brackets must be level. 6 inch minimum clearance.', 0.94),
(48, '4', 'IMP CEILING AHU (ATR STYLE) SUPPORT', 'equipment_detail', 'ATR style air handling unit support through IMP ceiling', 'Hanger rod per specifications, hex nut, lock nut or double nut', 'Furnished and installed by refrigeration contractor. All mounting holes used. Top of hanger brackets must be level.', 0.94),
(48, '5', 'AIR HANDLING UNIT HANGER', 'equipment_detail', 'Air handling unit hanger from joist with additional bracing', 'Hanger rod per R0001, 1/4 inch plate washer, hex nut, lock nut or double nut, L2x2x1/4 additional member, L4x4x3/8', 'Additional L2x2x1/4 required if load does not occur at joist panel or >6 inch and exceeds 150 lb. Apply cold-galvanized paint to all field welds.', 0.93),
(48, '6', 'SHAKER SAFETY BAR', 'equipment_detail', 'Safety bar installation for equipment protection', '1-1/2 inch yellow PVC pipe C&S Plastics PN P150Y80, ball cap PN F125YBC, S-hook crimp down, eye bolt, 2 inch x 2 inch square washer', 'Extend safety bar 2 ft beyond AHU. Safety bar to hang 12 inch below unit. Two bars required for traffic from both sides.', 0.91),
(48, '7', 'CONDENSER ATTACHMENT', 'support_detail', 'Condenser attachment to WF beam', 'WF beam, 3/16 inch weld through all bolt holes of condenser flange', 'Weld to beam through all bolt holes of the condenser flange. 3/16 inch weld typical.', 0.92),
(48, '8', 'COMPRESSOR/EQUIPMENT MOUNTING', 'equipment_detail', 'Compressor foundation mounting with grout and anchor bolts', 'Hilti HIT anchor bolt with Hilti HY-100 injection system, 1-1/2 inch nonshrink epoxy grout minimum, jacking nuts with 1/4 inch plate washers', 'Provide 3/4 inch notch in bottom of pad for drainage. Proper grouting required for 100% contact. Chockfast Foundation System or equal.', 0.94),
(48, '10', 'PIPE CROSSOVER', 'support_detail', 'Roof pipe crossover for safe passage over piping', 'Manufactured by Miro Industries or approved equal', 'Crossover shall comply with OSHA 1910 Subpart D and ASCE 7. Secured to building structure. Install per manufacturers recommendations.', 0.90),
(48, '11', 'ROOF EQUIPMENT SUPPORT RAIL', 'equipment_detail', 'Roof equipment support rail with curb and insulation', 'Insulated pier curb, synthetic wood, counter flashing cover, base plate', 'Provide wood nailer and equipment curb. Size per manufacturer. Curbs account for roof slope. Coordinate with roofing contractor for warranty.', 0.92),
(48, '15', 'HANGER ROD THRU IMP PANEL CEILING', 'support_detail', 'Insulated hanger rod penetration through IMP ceiling', '3/4 inch thick elastomeric insulation, hanger rod threaded ends, CSI Pipetite silicone escutcheon, stainless steel attachment ring', 'Hole through IMP ceiling 1/2 inch larger than rod diameter. Foam fill gap with urethane insulation. Seal end with caulk. 30 inch minimum spacing.', 0.93);

-- Update sheet metadata for extraction completion
UPDATE sheets
SET
    extracted_at = datetime('now'),
    drawing_type = 'detail',
    complexity = 'medium',
    extraction_model = 'sonnet-4.5',
    quality_score = 0.93
WHERE id = 46;

UPDATE sheets
SET
    extracted_at = datetime('now'),
    drawing_type = 'detail',
    complexity = 'medium',
    extraction_model = 'sonnet-4.5',
    quality_score = 0.94
WHERE id = 47;

UPDATE sheets
SET
    extracted_at = datetime('now'),
    drawing_type = 'detail',
    complexity = 'medium',
    extraction_model = 'sonnet-4.5',
    quality_score = 0.93
WHERE id = 48;

COMMIT;
