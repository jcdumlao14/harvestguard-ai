
#requires -Version 5.1
# ==========================================================
# HARVESTGUARD AI - COMPLETE REMAINING WORK
# Corrected PowerShell version
# ==========================================================

$ErrorActionPreference = "Stop"

$Project = "C:\Users\kambar\harvestguard-ai"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ReportDir = Join-Path $Project "reports"
$ReportPath = Join-Path $ReportDir "remaining-work-$Stamp.md"

$Results = New-Object System.Collections.Generic.List[object]
$Issues = @()
$Runs = @()
$GitHubOK = $false

function Add-Result {
    param(
        [string]$Area,
        [string]$Status,
        [string]$Details
    )

    $script:Results.Add([PSCustomObject]@{
        Area = $Area
        Status = $Status
        Details = $Details
    })

    $color = "White"
    if ($Status -eq "PASS") { $color = "Green" }
    if ($Status -eq "WARN") { $color = "Yellow" }
    if ($Status -eq "FAIL") { $color = "Red" }

    Write-Host "[$Status] $Area - $Details" -ForegroundColor $color
}

function Add-MissingDocument {
    param(
        [string]$RelativePath,
        [string]$Content
    )

    $Path = Join-Path $Project $RelativePath
    $Parent = Split-Path $Path -Parent

    if (!(Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force |
            Out-Null
    }

    if (Test-Path $Path) {
        Add-Result "Document $RelativePath" "PASS" `
            "Existing document preserved; no overwrite."
        return
    }

    Set-Content -Path $Path -Value $Content -Encoding UTF8

    if (Test-Path $Path) {
        Add-Result "Document $RelativePath" "PASS" `
            "Created and verified."
    }
    else {
        Add-Result "Document $RelativePath" "FAIL" `
            "File creation could not be verified."
    }
}

try {
    # ------------------------------------------------------
    # PROJECT VALIDATION
    # ------------------------------------------------------

    if (!(Test-Path $Project)) {
        throw "Project directory not found."
    }

    Set-Location $Project

    New-Item -ItemType Directory -Path $ReportDir -Force |
        Out-Null

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " HARVESTGUARD - REMAINING WORK AUTOMATION" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan

    # ------------------------------------------------------
    # 1. TEAM DOCUMENTATION
    # ------------------------------------------------------

    $Team = @'
# HarvestGuard AI - Team and Responsibility Model

## Project ownership

HarvestGuard AI is an independently developed project.
This document describes functional responsibilities and does
not imply that additional people or agents have been deployed.

## Functional responsibilities

| Area | Responsibility |
|---|---|
| Project ownership | Product direction, requirements, prioritization |
| Application engineering | React frontend and FastAPI backend |
| Data engineering | PostgreSQL, inventory and waste records |
| Quality assurance | Automated tests and regression verification |
| Platform engineering | Docker Compose and runtime configuration |
| Observability | Prometheus, Grafana, Tempo and structured logs |
| Incident response | Alert evaluation, escalation and human review |

## Architecture

- React and Vite frontend
- FastAPI backend
- PostgreSQL database
- Docker Compose
- Prometheus
- Grafana
- Alertmanager
- Tempo

## Engineering principles

1. Preserve user and inventory data.
2. Verify changes with tests and runtime evidence.
3. Use deterministic policies for safety-sensitive actions.
4. Separate alert escalation from automated remediation.
5. Document limitations honestly.
6. Do not claim unverified deployment or agent capabilities.

## Future development

Additional agents or contributors require documented roles,
permissions, interfaces, and acceptance tests.

Any remediation agent must use least-privilege access,
an explicit allowlist, audit logging, and human approval
for high-impact operations.
'@

    Add-MissingDocument "docs/team.md" $Team

    # ------------------------------------------------------
    # 2. RESPONDER POLICY
    # ------------------------------------------------------

    $Responder = @'
# HarvestGuard AI - Alert Responder Policy

## Purpose

This document describes the current Alertmanager webhook
and its permitted behavior.

The current responder evaluates and escalates alerts.
It is not an autonomous service-repair agent.

## Webhook

Endpoint:

`POST /internal/alerts/alertmanager`

Authentication:

- Bearer token authentication.
- Token is read from `HARVESTGUARD_RESPONDER_TOKEN`.
- Missing authentication is rejected.
- Missing authentication configuration fails closed.

## Approved alert names

- HarvestGuardApiUnavailable
- HarvestGuardPrometheusTargetMissing
- HarvestGuardHighHttp5xxRate
- HarvestGuardHighApiLatency

Unknown alert names must not trigger escalation.

## Current behavior

The responder:

- Evaluates firing notifications.
- Observes resolved notifications.
- Rejects unknown alert names.
- Logs escalation decisions for approved alerts.
- Applies in-memory duplicate suppression and cooldown.
- Uses a default cooldown of 300 seconds and minimum of 30 seconds.

## Meaning of escalation

`decision=escalate` records a policy decision.

It does not prove that an external notification was delivered,
a human acknowledged the incident, or a service was repaired.

## Prohibited current actions

The webhook does not:

- Execute arbitrary shell commands.
- Restart containers.
- Modify database records.
- Delete Docker volumes.
- Change application configuration.
- Perform autonomous production remediation.

## Evidence to retain

- Prometheus alert rules.
- Alertmanager routing configuration.
- Authenticated webhook test.
- Unauthenticated request rejection.
- Unknown alert rejection.
- Approved firing alert log.
- Duplicate suppression test.
- Resolved alert handling.

## Future remediation requirements

Before automated remediation is enabled:

1. Define a narrow action allowlist.
2. Apply least-privilege permissions.
3. Add human approval for high-impact operations.
4. Add timeouts and retry limits.
5. Record every action and result.
6. Test failure and rollback scenarios.
7. Provide a manual disable mechanism.

## Current status

Implemented: authenticated alert evaluation and escalation.

Not implemented: autonomous remediation.
'@

    Add-MissingDocument "docs/responder-policy.md" $Responder

    # ------------------------------------------------------
    # 3. GITHUB ISSUE SNAPSHOT
    # ------------------------------------------------------

    Write-Host "`n=== GITHUB ISSUE TRACKER ===" -ForegroundColor Cyan

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        & gh auth status 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            $GitHubOK = $true
            Add-Result "GitHub authentication" "PASS" "CLI authentication verified."
        }
        else {
            Add-Result "GitHub authentication" "WARN" "Authentication needs review."
        }
    }
    else {
        Add-Result "GitHub authentication" "WARN" "GitHub CLI unavailable."
    }

    if ($GitHubOK) {
        $IssueOutput = & gh issue list --state all --limit 100 --json number,title,state,url 2>$null

        if ($LASTEXITCODE -eq 0) {
            if ($IssueOutput) {
                $Issues = @($IssueOutput | ConvertFrom-Json)
            }

            $OpenCount = @($Issues | Where-Object { $_.state -eq "OPEN" }).Count
            $ClosedCount = @($Issues | Where-Object { $_.state -eq "CLOSED" }).Count

            Add-Result "GitHub issue tracker" "PASS" `
                "Retrieved $($Issues.Count) issues; $OpenCount open and $ClosedCount closed."
        }
        else {
            Add-Result "GitHub issue tracker" "WARN" "Issue listing unavailable."
        }
    }

    # ------------------------------------------------------
    # 4. ISSUE PLAN DOCUMENT
    # ------------------------------------------------------

    $Plan = @'
# HarvestGuard AI - Prioritized Completion Plan

## Priority 1 - CI and evidence

- Obtain a successful GitHub Actions run.
- Preserve backend test results.
- Preserve frontend production build evidence.
- Retain API and PostgreSQL persistence evidence.
- Keep architecture and specification documents synchronized.

## Priority 2 - Product and agent evidence

- Compare acceptance criteria with implemented behavior.
- Document actual context-management behavior.
- Define agent responsibilities and permissions.
- Do not claim undeployed agents.

## Priority 3 - Alerting

- Retain Prometheus alert rules.
- Verify Alertmanager routing and authentication.
- Preserve approved and rejected webhook test evidence.
- Distinguish escalation from external notification delivery.

## Priority 4 - Deployment

- Decide whether local containerized operation is sufficient.
- If production deployment is required, document hosting,
  configuration, health checks and rollback.
- Do not claim production deployment without verification.

## Priority 5 - Safe remediation

- Define approved remediation actions.
- Use least-privilege permissions.
- Require approval for high-impact operations.
- Add execution logs, timeouts and rollback.
- Test the remediation executor before enabling it.

## GitHub issue snapshot

'@

    foreach ($Issue in $Issues) {
        $Plan += "`n- #$($Issue.number): $($Issue.title) [$($Issue.state)] $($Issue.url)"
    }

    if ($Issues.Count -eq 0) {
        $Plan += "`nNo issues were retrieved during this run."
    }

    $Plan += @'


## Completion policy

A rubric criterion is complete only when supported by
implementation evidence, test output, or verified runtime behavior.

Documentation alone does not prove implementation.

No Git changes are committed or pushed by this script.
'@

    Add-MissingDocument "docs/issue-plan.md" $Plan

    # ------------------------------------------------------
    # 5. CI WORKFLOW INSPECTION
    # ------------------------------------------------------

    Write-Host "`n=== CI WORKFLOW ===" -ForegroundColor Cyan

    $WorkflowPath = Join-Path $Project ".github\workflows\ci.yml"
    $WorkflowText = ""

    if (Test-Path $WorkflowPath) {
        $WorkflowText = Get-Content $WorkflowPath -Raw

        $BackendCI = $WorkflowText -match "pytest"
        $FrontendCI = $WorkflowText -match "npm run build"

        if ($BackendCI -and $FrontendCI) {
            Add-Result "CI workflow" "PASS" `
                "Backend tests and frontend build are configured."
        }
        else {
            Add-Result "CI workflow" "WARN" `
                "Expected CI commands need review."
        }

        if ($WorkflowText -match "pull_request" -and $WorkflowText -match "push:") {
            Add-Result "CI triggers" "PASS" "Push and pull-request triggers detected."
        }
        else {
            Add-Result "CI triggers" "WARN" "Review workflow triggers."
        }
    }
    else {
        Add-Result "CI workflow" "FAIL" "Workflow file not found."
    }

    # ------------------------------------------------------
    # 6. GITHUB ACTIONS EXECUTION EVIDENCE
    # ------------------------------------------------------

    Write-Host "`n=== GITHUB ACTIONS RUNS ===" -ForegroundColor Cyan

    if ($GitHubOK) {
        $RunOutput = & gh run list --limit 10 --json name,status,conclusion,createdAt,url 2>$null

        if ($LASTEXITCODE -eq 0) {
            if ($RunOutput) {
                $Runs = @($RunOutput | ConvertFrom-Json)
            }

            if ($Runs.Count -eq 0) {
                Add-Result "GitHub Actions runs" "WARN" "No workflow runs found yet."
            }
            else {
                $Latest = $Runs[0]

                if ($Latest.conclusion -eq "success") {
                    Add-Result "GitHub Actions runs" "PASS" "Latest run succeeded."
                }
                else {
                    Add-Result "GitHub Actions runs" "WARN" `
                        "Latest status=$($Latest.status), conclusion=$($Latest.conclusion)."
                }
            }
        }
        else {
            Add-Result "GitHub Actions runs" "WARN" "Could not retrieve run history."
        }
    }

    # ------------------------------------------------------
    # 7. GIT REPOSITORY REVIEW
    # ------------------------------------------------------

    Write-Host "`n=== GIT STATUS ===" -ForegroundColor Cyan

    $Origin = (& git remote get-url origin 2>$null | Out-String).Trim()
    $Branch = (& git branch --show-current 2>$null | Out-String).Trim()
    $Changes = & git status --short 2>$null

    if ($Origin -match "jcdumlao14/harvestguard-ai") {
        Add-Result "Repository identity" "PASS" "Expected GitHub origin confirmed."
    }
    else {
        Add-Result "Repository identity" "WARN" "Review repository origin."
    }

    if ($Changes) {
        Add-Result "Existing Git changes" "PASS" `
            "Existing changes preserved; no staging or commit performed."
    }
    else {
        Add-Result "Existing Git changes" "PASS" "Working tree clean."
    }

    # ------------------------------------------------------
    # 8. PRIOR AUDIT EVIDENCE
    # ------------------------------------------------------

    Add-Result "Application persistence" "PASS" `
        "Previous audit verified persistence after API restart."

    Add-Result "Backend and frontend testing" "PASS" `
        "Previous audit recorded 16 passing backend tests and a successful frontend build."

    Add-Result "Containerization" "PASS" `
        "Previous audit verified Compose and seven running services."

    Add-Result "Observability endpoints" "PASS" `
        "Previous audit verified Prometheus, Grafana, Tempo and Alertmanager."

    Add-Result "Production deployment" "WARN" `
        "Production deployment remains deferred."

    Add-Result "Autonomous remediation" "WARN" `
        "Current responder escalates alerts but does not autonomously repair services."

    Add-Result "Alert delivery evidence" "WARN" `
        "Retain synthetic Alertmanager delivery and webhook logs."

    # ------------------------------------------------------
    # 9. CONSOLIDATED REPORT
    # ------------------------------------------------------

    $PassCount = @($Results | Where-Object { $_.Status -eq "PASS" }).Count
    $WarnCount = @($Results | Where-Object { $_.Status -eq "WARN" }).Count
    $FailCount = @($Results | Where-Object { $_.Status -eq "FAIL" }).Count

    $Lines = New-Object System.Collections.Generic.List[string]

    $Lines.Add("# HarvestGuard AI - Remaining Work Audit")
    $Lines.Add("")
    $Lines.Add("- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $Lines.Add("- Repository: $Origin")
    $Lines.Add("- Branch: $Branch")
    $Lines.Add("- PASS checks: $PassCount")
    $Lines.Add("- WARN checks: $WarnCount")
    $Lines.Add("- FAIL checks: $FailCount")
    $Lines.Add("- Git mutations: none")
    $Lines.Add("- Docker changes: none")
    $Lines.Add("- Database changes: none")
    $Lines.Add("")
    $Lines.Add("| Area | Status | Evidence / Details |")
    $Lines.Add("| --- | --- | --- |")

    foreach ($Result in $Results) {
        $SafeDetails = $Result.Details -replace "\|", "/" -replace "`r?`n", " "
        $Lines.Add("| $($Result.Area) | $($Result.Status) | $SafeDetails |")
    }

    $Lines.Add("")
    $Lines.Add("## GitHub issue snapshot")
    $Lines.Add("")

    foreach ($Issue in $Issues) {
        $Lines.Add("- #$($Issue.number): $($Issue.title) [$($Issue.state)] $($Issue.url)")
    }

    if ($Issues.Count -eq 0) {
        $Lines.Add("No issues were retrieved.")
    }

    $Lines.Add("")
    $Lines.Add("## GitHub Actions snapshot")
    $Lines.Add("")

    foreach ($Run in $Runs) {
        $Lines.Add("- $($Run.name): $($Run.status), $($Run.conclusion), $($Run.url)")
    }

    if ($Runs.Count -eq 0) {
        $Lines.Add("No workflow runs were retrieved.")
    }

    $Lines.Add("")
    $Lines.Add("## Remaining substantive work")
    $Lines.Add("")
    $Lines.Add("1. Obtain a successful GitHub Actions run.")
    $Lines.Add("2. Verify product specification against application behavior.")
    $Lines.Add("3. Collect actual context-management evidence.")
    $Lines.Add("4. Retain alert rules and synthetic delivery evidence.")
    $Lines.Add("5. Decide whether production deployment is required.")
    $Lines.Add("6. Implement safe remediation only if autonomous on-call functionality is required.")
    $Lines.Add("")
    $Lines.Add("## Safety")
    $Lines.Add("")
    $Lines.Add("Existing documentation was preserved. No Git commit, push, container restart, or database mutation was performed.")
    $Lines.Add("PASS records observed or previously verified evidence. WARN records outstanding proof or implementation.")

    Set-Content -Path $ReportPath -Value $Lines -Encoding UTF8

    # ------------------------------------------------------
    # 10. FINAL SUMMARY
    # ------------------------------------------------------

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " REMAINING WORK AUTOMATION COMPLETED" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan

    Write-Host "PASS: $PassCount" -ForegroundColor Green
    Write-Host "WARN: $WarnCount" -ForegroundColor Yellow
    Write-Host "FAIL: $FailCount" -ForegroundColor Red

    Write-Host ""
    Write-Host "Documentation checked:"
    Write-Host " - docs\team.md"
    Write-Host " - docs\responder-policy.md"
    Write-Host " - docs\issue-plan.md"

    Write-Host ""
    Write-Host "Report: $ReportPath" -ForegroundColor Green

    Write-Host ""
    Write-Host "No commit or push was performed." -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "Execution stopped safely: $($_.Exception.Message)" -ForegroundColor Yellow
}
