$sqlite = "C:\Users\bjohnson1\AppData\Local\Microsoft\WinGet\Packages\SQLite.SQLite_Microsoft.Winget.Source_8wekyb3d8bbwe\sqlite3.exe"
$db = "D:\quality.db"

Write-Host "`nScanning D:\Projects\...`n" -ForegroundColor Cyan

$projects = Get-ChildItem "D:\Projects" -Directory

foreach ($proj in $projects) {
    if ($proj.Name -match '^(\d+)-(.+)$') {
        $number = $Matches[1]
        $name = $Matches[2]
        $path = $proj.FullName

        Write-Host "$number-$name" -ForegroundColor Yellow
        Write-Host "  Path: $path"

        # Insert/update project
        $sql = "INSERT INTO projects (number, name, path, status) VALUES ('$number', '$name', '$path', 'active') ON CONFLICT(number) DO UPDATE SET name='$name', path='$path', updated_at=CURRENT_TIMESTAMP;"
        & $sqlite $db $sql

        # Get project ID
        $projId = & $sqlite $db "SELECT id FROM projects WHERE number='$number';"

        # Scan disciplines
        $disciplines = Get-ChildItem $path -Directory -ErrorAction SilentlyContinue
        $totalSheets = 0

        foreach ($disc in $disciplines) {
            $discName = $disc.Name
            $discPath = $disc.FullName

            # Count PDFs
            $pdfs = Get-ChildItem $discPath -Filter "*.pdf" -ErrorAction SilentlyContinue
            $pdfCount = ($pdfs | Measure-Object).Count

            if ($pdfCount -gt 0) {
                $totalSheets += $pdfCount

                # Determine prefix from first PDF
                $prefix = ""
                if ($pdfs.Count -gt 0) {
                    $firstPdf = $pdfs[0].Name
                    if ($firstPdf -match '^([A-Z]+)-') {
                        $prefix = $Matches[1] + "-"
                    }
                }

                Write-Host "    $discName`: $pdfCount PDFs" -ForegroundColor Gray

                # Insert/update discipline
                $sql = "INSERT INTO disciplines (project_id, name, folder_path, prefix, sheet_count, last_scanned) VALUES ($projId, '$discName', '$discPath', '$prefix', $pdfCount, CURRENT_TIMESTAMP) ON CONFLICT(project_id, name) DO UPDATE SET folder_path='$discPath', prefix='$prefix', sheet_count=$pdfCount, last_scanned=CURRENT_TIMESTAMP;"
                & $sqlite $db $sql

                # Get discipline ID
                $discId = & $sqlite $db "SELECT id FROM disciplines WHERE project_id=$projId AND name='$discName';"

                # Insert sheets
                foreach ($pdf in $pdfs) {
                    $fileName = $pdf.Name
                    $filePath = $pdf.FullName

                    # Parse drawing number and revision
                    $drawingNum = ""
                    $revision = "0"
                    $isCurrent = 1

                    if ($fileName -match '-SUPERSEDED') {
                        $isCurrent = 0
                    }

                    # Try to parse: DrawingNumber-Rev.X.pdf or DrawingNumber_Rev.X.pdf
                    if ($fileName -match '^(.+?)[-_]Rev\.?([A-Z0-9]+)') {
                        $drawingNum = $Matches[1]
                        $revision = $Matches[2]
                    } elseif ($fileName -match '^(.+?)\.pdf$') {
                        $drawingNum = $Matches[1]
                    }

                    $sql = "INSERT OR IGNORE INTO sheets (project_id, discipline_id, file_path, file_name, drawing_number, revision, is_current) VALUES ($projId, $discId, '$filePath', '$fileName', '$drawingNum', '$revision', $isCurrent);"
                    & $sqlite $db $sql
                }
            }
        }

        Write-Host "  Total: $totalSheets sheets`n"
    }
}

# Show summary
Write-Host "`n=== Scan Complete ===" -ForegroundColor Green
Write-Host ""
& $sqlite $db -header -column "SELECT number, name, (SELECT COUNT(*) FROM disciplines d WHERE d.project_id=p.id) as disciplines, (SELECT SUM(sheet_count) FROM disciplines d WHERE d.project_id=p.id) as sheets FROM projects p ORDER BY number;"
