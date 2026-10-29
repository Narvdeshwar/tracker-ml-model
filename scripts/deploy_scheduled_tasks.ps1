<#
.SYNOPSIS
    Deploy and register Windows Scheduled Tasks for IPO Research & Prospective Shadow Validation.

.DESCRIPTION
    Phase 10.25 Windows Task Scheduler Deployment Script.
    Configures precise recurrence intervals, operating time windows, weekday filters,
    execution timeouts, and missed-run recovery:
      1. Notice Ingestion: Every 15 minutes, 09:00 to 18:00 IST.
      2. Deadline Expiry Sweeper: Every 5 minutes, 15:00 to 18:00 IST.
      3. Daily Monitoring Report: Daily at 18:30 IST.

.NOTES
    Operating Mode: STRICT SHADOW VALIDATION ONLY
    Prohibited: Real-money trading, automated order execution, broker APIs.
#>

[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [string]$RepoRoot = "D:\personal\st-ai\ipo-record",
    [string]$PythonExe = "D:\personal\st-ai\ipo-record\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================="
Write-Host " Phase 10.25 Windows Task Scheduler Deployment & Configuration"
Write-Host " Operating Mode: STRICT SHADOW VALIDATION ONLY"
Write-Host "=================================================================="

# Verify prerequisites
if (-not (Test-Path $PythonExe)) {
    throw "Configured Python executable not found at '$PythonExe'."
}
if (-not (Test-Path $RepoRoot)) {
    throw "Repository root directory not found at '$RepoRoot'."
}

$ScriptPath = Join-Path $RepoRoot "src\operational_task_runner.py"
if (-not (Test-Path $ScriptPath)) {
    throw "Operational task runner script not found at '$ScriptPath'."
}

$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
    Write-Host "[+] Created logs directory at: $LogsDir"
}

# Principal: Run under current user session
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

# Task Settings: Disallow concurrent instances, execution timeout of 10 minutes, restart on failure
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# -------------------------------------------------------------------------
# Task 1: Official Exchange Notice Collector
# Cadence: Recurring every 15 minutes between 09:00 and 18:00 IST
# -------------------------------------------------------------------------
$Task1Name = "IPORecord_NoticeCollector"
$Task1Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "src\operational_task_runner.py --action collect_notices --exchanges BSE NSE" `
    -WorkingDirectory $RepoRoot

$Task1Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At "09:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

if ($PSCmdlet.ShouldProcess($Task1Name, "Register Scheduled Task (Every 15m, 09:00-18:00 IST)")) {
    Unregister-ScheduledTask -TaskName $Task1Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask `
        -TaskName $Task1Name `
        -Action $Task1Action `
        -Trigger $Task1Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Phase 10.25: Collects official BSE/NSE SME IPO notices every 15m" | Out-Null
    Write-Host "[+] Registered Task: $Task1Name (Every 15m, 09:00-18:00 IST)"
}

# -------------------------------------------------------------------------
# Task 2: Candidate Deadline Expiry Sweeper
# Cadence: Recurring every 5 minutes between 15:00 and 18:00 IST
# -------------------------------------------------------------------------
$Task2Name = "IPORecord_DeadlineSweeper"
$Task2Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "src\operational_task_runner.py --action sweep_expiries" `
    -WorkingDirectory $RepoRoot

$Task2Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At "15:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

if ($PSCmdlet.ShouldProcess($Task2Name, "Register Scheduled Task (Every 5m, 15:00-18:00 IST)")) {
    Unregister-ScheduledTask -TaskName $Task2Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask `
        -TaskName $Task2Name `
        -Action $Task2Action `
        -Trigger $Task2Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Phase 10.25: Sweeps candidate cutoff deadlines every 5m" | Out-Null
    Write-Host "[+] Registered Task: $Task2Name (Every 5m, 15:00-18:00 IST)"
}

# -------------------------------------------------------------------------
# Task 3: Daily Monitoring Report Generator
# Cadence: Once daily at 18:30 IST
# -------------------------------------------------------------------------
$Task3Name = "IPORecord_MonitoringReport"
$Task3Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "src\operational_task_runner.py --action monitoring_report" `
    -WorkingDirectory $RepoRoot

$Task3Trigger = New-ScheduledTaskTrigger -Daily -At "18:30"

if ($PSCmdlet.ShouldProcess($Task3Name, "Register Scheduled Task (Daily at 18:30 IST)")) {
    Unregister-ScheduledTask -TaskName $Task3Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask `
        -TaskName $Task3Name `
        -Action $Task3Action `
        -Trigger $Task3Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Phase 10.25: Generates daily operational and governance monitoring report at 18:30 IST" | Out-Null
    Write-Host "[+] Registered Task: $Task3Name (Daily at 18:30 IST)"
}

Write-Host "=================================================================="
Write-Host " Deployment script execution completed."
Write-Host " Run '.\scripts\verify_scheduled_tasks.ps1' to inspect registered status."
Write-Host "=================================================================="
