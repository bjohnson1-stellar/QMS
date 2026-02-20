#!/usr/bin/env python3
"""Cross-Checker Agent for QMS Pipeline - Detects conflicts across drawings."""

import sqlite3
from typing import List, Dict, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Conflict:
    conflict_type: str
    severity: str
    item: str
    item_type: str
    sheet1_id: int
    sheet2_id: Optional[int]
    value1: str
    value2: Optional[str]
    details: str
    drawing1: str = ""
    drawing2: str = ""


class CrossChecker:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conflicts: List[Conflict] = []
        
    def run_checks(self, project_id: int) -> Dict:
        sep = "=" * 80
        print()
        print(sep)
        print("CROSS-CHECK ANALYSIS")
        print(sep)
        print()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            project = conn.execute("SELECT id, name, number FROM projects WHERE id = ?",
                                   (project_id,)).fetchone()
            if not project:
                raise ValueError(f"Project ID {project_id} not found")
            
            print(f"Project: {project['number']} - {project['name']}")
            print()
            
            stats = self._get_project_stats(conn, project_id)
            print(f"Drawings Analyzed: {stats['sheets']}")
            print(f"Items Compared: {stats['total_items']:,}")
            print(f"Disciplines: {', '.join(stats['disciplines'])}")
            print()
            
            conn.execute("DELETE FROM conflicts WHERE project_id = ?", (project_id,))
            conn.commit()
            
            print("Running conflict detection queries...")
            print()
            
            self._check_material_conflicts(conn, project_id)
            self._check_size_conflicts(conn, project_id)
            self._check_duplicate_tags(conn, project_id)
            
            self._store_conflicts(conn, project_id)
            report = self._generate_report(conn, project_id, stats)
            
            return report
    
    def _get_project_stats(self, conn, project_id):
        sheets = conn.execute(
            "SELECT COUNT(*) as cnt FROM sheets WHERE project_id = ? AND is_current = 1",
            (project_id,)).fetchone()['cnt']
        
        disciplines = [row[0] for row in conn.execute(
            "SELECT DISTINCT discipline FROM sheets WHERE project_id = ? AND is_current = 1 ORDER BY discipline",
            (project_id,)).fetchall()]
        
        equipment_cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM equipment WHERE sheet_id IN (SELECT id FROM sheets WHERE project_id = ? AND is_current = 1)",
            (project_id,)).fetchone()['cnt']
        
        lines_cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM lines WHERE sheet_id IN (SELECT id FROM sheets WHERE project_id = ? AND is_current = 1)",
            (project_id,)).fetchone()['cnt']
        
        instruments_cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM instruments WHERE sheet_id IN (SELECT id FROM sheets WHERE project_id = ? AND is_current = 1)",
            (project_id,)).fetchone()['cnt']
        
        return {
            'sheets': sheets,
            'disciplines': disciplines,
            'equipment': equipment_cnt,
            'lines': lines_cnt,
            'instruments': instruments_cnt,
            'total_items': equipment_cnt + lines_cnt + instruments_cnt
        }
    
    def _check_material_conflicts(self, conn, project_id):
        print("  Checking material conflicts...")
        query = """SELECT l1.line_number, l1.material as material_1, l2.material as material_2,
                   s1.id as sheet1_id, s2.id as sheet2_id,
                   s1.drawing_number as drawing_1, s2.drawing_number as drawing_2,
                   s1.discipline as disc1, s2.discipline as disc2
            FROM lines l1
            JOIN lines l2 ON l1.line_number = l2.line_number AND l1.id < l2.id
            JOIN sheets s1 ON s1.id = l1.sheet_id
            JOIN sheets s2 ON s2.id = l2.sheet_id
            WHERE s1.project_id = ? AND s2.project_id = ?
              AND l1.material IS NOT NULL AND l2.material IS NOT NULL
              AND TRIM(l1.material) != '' AND TRIM(l2.material) != ''
              AND LOWER(TRIM(l1.material)) != LOWER(TRIM(l2.material))
              AND s1.is_current = 1 AND s2.is_current = 1
            ORDER BY l1.line_number"""
        results = conn.execute(query, (project_id, project_id)).fetchall()
        for row in results:
            mat1 = row["material_1"].upper()
            mat2 = row["material_2"].upper()
            if ("CS" in mat1 or "CARBON" in mat1) and ("SS" in mat2 or "STAINLESS" in mat2):
                severity, details = "critical", "Carbon/Stainless mismatch - galvanic corrosion risk"
            elif ("SS" in mat1 or "STAINLESS" in mat1) and ("CS" in mat2 or "CARBON" in mat2):
                severity, details = "critical", "Stainless/Carbon mismatch - galvanic corrosion risk"
            else:
                severity, details = "medium", "Material specification mismatch"
            self.conflicts.append(Conflict(
                conflict_type="MATERIAL", severity=severity, item=row["line_number"],
                item_type="line", sheet1_id=row["sheet1_id"], sheet2_id=row["sheet2_id"],
                value1=row["material_1"], value2=row["material_2"],
                details=f"{details} ({row['disc1']} vs {row['disc2']})",
                drawing1=row["drawing_1"], drawing2=row["drawing_2"]))
        print(f"    Found {len(results)} material conflicts")
    def _check_size_conflicts(self, conn, project_id):
        print("  Checking size conflicts...")
        query = """SELECT l1.line_number, l1.size as size_1, l2.size as size_2,
                   s1.id as sheet1_id, s2.id as sheet2_id,
                   s1.drawing_number as drawing_1, s2.drawing_number as drawing_2,
                   s1.discipline as disc1, s2.discipline as disc2
            FROM lines l1
            JOIN lines l2 ON l1.line_number = l2.line_number AND l1.id < l2.id
            JOIN sheets s1 ON s1.id = l1.sheet_id
            JOIN sheets s2 ON s2.id = l2.sheet_id
            WHERE s1.project_id = ?
              AND l1.size IS NOT NULL AND l2.size IS NOT NULL
              AND TRIM(l1.size) != '' AND TRIM(l2.size) != ''
              AND LOWER(TRIM(l1.size)) != LOWER(TRIM(l2.size))
              AND s1.is_current = 1 AND s2.is_current = 1
            ORDER BY l1.line_number"""
        results = conn.execute(query, (project_id,)).fetchall()
        for row in results:
            size_diff = self._calculate_size_difference(row["size_1"], row["size_2"])
            if size_diff is not None and size_diff > 2:
                severity, details = "critical", f"Major size discrepancy ({size_diff} sizes apart)"
            elif size_diff is not None and size_diff <= 2:
                severity, details = "medium", "Size difference - may be intentional reducer"
            else:
                severity, details = "medium", "Size specification mismatch"
            self.conflicts.append(Conflict(
                conflict_type="SIZE", severity=severity, item=row["line_number"],
                item_type="line", sheet1_id=row["sheet1_id"], sheet2_id=row["sheet2_id"],
                value1=row["size_1"], value2=row["size_2"],
                details=f"{details} ({row['disc1']} vs {row['disc2']})",
                drawing1=row["drawing_1"], drawing2=row["drawing_2"]))
        print(f"    Found {len(results)} size conflicts")
    def _check_duplicate_tags(self, conn, project_id):
        print("  Checking duplicate equipment tags...")
        query = """SELECT e1.tag, e1.description as desc_1, e2.description as desc_2,
                   e1.equipment_type as type_1, e2.equipment_type as type_2,
                   s1.id as sheet1_id, s2.id as sheet2_id,
                   s1.drawing_number as drawing_1, s2.drawing_number as drawing_2,
                   s1.discipline as disc1, s2.discipline as disc2
            FROM equipment e1
            JOIN equipment e2 ON e1.tag = e2.tag AND e1.id < e2.id
            JOIN sheets s1 ON s1.id = e1.sheet_id
            JOIN sheets s2 ON s2.id = e2.sheet_id
            WHERE s1.project_id = ? AND s1.is_current = 1 AND s2.is_current = 1
              AND ((e1.equipment_type IS NOT NULL AND e2.equipment_type IS NOT NULL
                    AND LOWER(TRIM(e1.equipment_type)) != LOWER(TRIM(e2.equipment_type)))
                   OR (e1.description IS NOT NULL AND e2.description IS NOT NULL
                       AND LOWER(TRIM(e1.description)) != LOWER(TRIM(e2.description))))
            ORDER BY e1.tag"""
        results = conn.execute(query, (project_id,)).fetchall()
        for row in results:
            if row["type_1"] and row["type_2"] and row["type_1"] != row["type_2"]:
                severity, details = "high", "Equipment type mismatch"
            else:
                severity, details = "low", "Description mismatch"
            self.conflicts.append(Conflict(
                conflict_type="TAG_CONFLICT", severity=severity, item=row["tag"],
                item_type="equipment", sheet1_id=row["sheet1_id"], sheet2_id=row["sheet2_id"],
                value1=f"{row['type_1'] or ''} - {row['desc_1'] or ''}",
                value2=f"{row['type_2'] or ''} - {row['desc_2'] or ''}",
                details=f"{details} ({row['disc1']} vs {row['disc2']})",
                drawing1=row["drawing_1"], drawing2=row["drawing_2"]))
        print(f"    Found {len(results)} tag conflicts")
    def _calculate_size_difference(self, size1, size2):
        try:
            def parse(s):
                s = s.strip().replace('"', '').replace("'", '')
                if '-' in s:
                    parts = s.split('-')
                    return float(parts[0]) + eval(parts[1])
                return float(s)
            return abs(int(parse(size1) - parse(size2)))
        except:
            return None
    
    def _store_conflicts(self, conn, project_id):
        print()
        print(f"Storing {len(self.conflicts)} conflicts...")
        for c in self.conflicts:
            item_desc = f"{c.item_type}: {c.item}"
            full_details = f"{c.details} | {c.drawing1}: {c.value1}"
            if c.drawing2:
                full_details += f" | {c.drawing2}: {c.value2}"
            conn.execute("""INSERT INTO conflicts
                (project_id, conflict_type, severity, item, details, resolved)
                VALUES (?, ?, ?, ?, ?, 0)""",
                (project_id, c.conflict_type, c.severity, item_desc, full_details))
        conn.commit()
    def _generate_report(self, conn, project_id, stats):
        sep = "=" * 80
        print()
        print(sep)
        print("CONFLICTS FOUND")
        print(sep)
        print()
        
        by_severity = defaultdict(list)
        by_type = defaultdict(int)
        for c in self.conflicts:
            by_severity[c.severity].append(c)
            by_type[c.conflict_type] += 1
        
        for severity in ["critical", "high", "medium", "low"]:
            conflicts = by_severity.get(severity, [])
            if conflicts:
                print(f"{severity.upper()} ({len(conflicts)}):")
                print("-" * 80)
                for i, c in enumerate(conflicts[:10], 1):
                    print(f"{i}. {c.conflict_type}: {c.item_type.title()} '{c.item}'")
                    print(f"   {c.drawing1}: {c.value1}")
                    if c.drawing2:
                        print(f"   {c.drawing2}: {c.value2}")
                    print(f"   Impact: {c.details}")
                    print()
                if len(conflicts) > 10:
                    print(f"   ... and {len(conflicts)-10} more {severity} conflicts")
                    print()
        
        print()
        print(sep)
        print("SUMMARY")
        print(sep)
        print()
        print(f"Total Conflicts: {len(self.conflicts)}")
        print()
        print("By Severity:")
        for severity in ["critical", "high", "medium", "low"]:
            count = len(by_severity.get(severity, []))
            if count > 0:
                print(f"  {severity.capitalize()}: {count}")
        print()
        print("By Type:")
        for ctype, count in sorted(by_type.items()):
            print(f"  {ctype}: {count}")
        print()
        
        return {
            "project_id": project_id,
            "total_conflicts": len(self.conflicts),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "by_type": dict(by_type),
            "stats": stats
        }
def run_cross_check(project_number, db_path="data/quality.db"):
    with sqlite3.connect(db_path) as conn:
        project = conn.execute("SELECT id FROM projects WHERE number = ?",
                               (project_number,)).fetchone()
        if not project:
            raise ValueError(f"Project {project_number} not found")
        project_id = project[0]
    checker = CrossChecker(db_path)
    return checker.run_checks(project_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cross_checker.py <project_number>")
        sys.exit(1)
    result = run_cross_check(sys.argv[1])
    print(f"Cross-check complete. {result['total_conflicts']} conflicts found.")
