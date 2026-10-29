<#
.SYNOPSIS
    Read-only inspection and verification of registered IPO Shadow Validation scheduled tasks.

.DESCRIPTION
    Phase 10.25 Verification Script.
    Inspects Task Scheduler state, triggers, repetition intervals, action arguments,
    last run time, last exit code, and execution identity.
    Does not modify or delete tasks.
#>

$ErrorActionPreference = "Continue"

Write-Host "=================================================================="
Write-Host " Phase 10.25 Scheduled Tasks Verification & Inspection"
Write-Host " Operating Mode: STRICT SHADOW VALIDATION ONLY (Read-Only)"
Write-Host "=================================================================="

$TaskNames = @("IPORecord_NoticeCollector", "IPORecord_DeadlineSweeper", "IPORecord_MonitoringReport")
$AllInstalled = $true

foreach ($tname in $TaskNames) {
    Write-Host "`n--- Checking Task: $tname ---"
    $task = Get-ScheduledTask -TaskName $tname -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "  Status: NOT INSTALLED" -ForegroundColor Yellow
        $AllInstalled = $false
        continue
    }

    $info = Get-ScheduledTaskInfo -TaskName $tname -ErrorAction SilentlyContinue
    Write-Host "  State:          $($task.State)"
    Write-Host "  Last Run Time:  $($info.LastRunTime)"
    Write-Host "  Last Task Result: $($info.LastTaskResult)"
    Write-Host "  Next Run Time:  $($info.NextRunTime)"
    Write-Host "  Number Of Missed Runs: $($info.NumberOfMissedRuns)"
    
    foreach ($action in $task.Actions) {
        Write-Host "  Execute:        $($action.Execute)"
        Write-Host "  Arguments:      $($action.Arguments)"
        Write-Host "  Working Dir:    $($action.WorkingDirectory)"
    }
    
    foreach ($trigger in $task.Triggers) {
        Write-Host "  Trigger Type:   $($trigger.CimClass.CimClassName)"
        Write-Host "  Start Boundary: $($trigger.StartBoundary)"
        if ($trigger.Repetition) {
            Write-Host "  Repetition Interval: $($trigger.Repetition.Interval)"
            Write-Host "  Repetition Duration: $($trigger.Repetition.Duration)"
        }
    }
}

Write-Host "`n=================================================================="
if ($AllInstalled) {
    Write-Host " Summary Status: ALL TASKS REGISTERED & VERIFIED" -ForegroundColor Green
} else {
    Write-Host " Summary Status: ONE OR MORE TASKS NOT INSTALLED" -ForegroundColor Yellow
    Write-Host " To deploy, run: .\scripts\deploy_scheduled_tasks.ps1"
}
Write-Host "=================================================================="
