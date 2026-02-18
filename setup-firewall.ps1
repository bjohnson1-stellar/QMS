#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Opens Windows Firewall for QMS web server (port 5000).
.DESCRIPTION
    Creates an inbound firewall rule allowing TCP traffic on port 5000
    so coworkers on the LAN can access http://L004470-CAD:5000
.NOTES
    Run this once from an elevated PowerShell prompt:
        powershell -ExecutionPolicy Bypass -File D:\qms\setup-firewall.ps1
#>

$RuleName = "QMS Web Server (TCP 5000)"

# Remove existing rule if present (idempotent)
$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Remove-NetFirewallRule -DisplayName $RuleName
    Write-Host "Removed existing rule: $RuleName" -ForegroundColor Yellow
}

# Create inbound allow rule for TCP 5000
New-NetFirewallRule `
    -DisplayName $RuleName `
    -Description "Allow inbound access to QMS Quality Management System on port 5000" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5000 `
    -Action Allow `
    -Profile Domain,Private `
    -Enabled True | Out-Null

Write-Host ""
Write-Host "Firewall rule created: $RuleName" -ForegroundColor Green
Write-Host "  Direction : Inbound"
Write-Host "  Port      : TCP 5000"
Write-Host "  Profiles  : Domain, Private"
Write-Host "  Action    : Allow"
Write-Host ""
Write-Host "Coworkers can now access: http://L004470-CAD:5000" -ForegroundColor Cyan
Write-Host "                      or: http://172.15.40.45:5000" -ForegroundColor Cyan
Write-Host ""
