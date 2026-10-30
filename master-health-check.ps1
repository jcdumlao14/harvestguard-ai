$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $PSScriptRoot

$script:Results = @()

function Add-Result {
    param([string]$Name, [string]$Status, [string]$Detail)

    $script:Results += [PSCustomObject]@{
        Check = $Name
        Status = $Status
        Detail = $Detail
    }

    $color = switch ($Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        default { "Yellow" }
    }

    Write-Host "[$Status] $Name" -ForegroundColor $color

    if ($Detail) {
        Write-Host "       $Detail"
    }
}

function Test-Check {
    param([string]$Name, [scriptblock]$Action)

    try {
        $output = & $Action
        $detail = ($output | Out-String).Trim()

        if ($detail.Length -gt 350) {
            $detail = $detail.Substring(0,350) + "..."
        }

        Add-Result $Name "PASS" $detail
    }
    catch {
        Add-Result $Name "FAIL" $_.Exception.Message
    }
}

function Get-Json {
    param([string]$Url)

    Invoke-RestMethod -Uri $Url -TimeoutSec 10
}

Write-Host ""
Write-Host "================================================"
Write-Host "       HARVESTGUARD MASTER HEALTH CHECK"
Write-Host "================================================"
Write-Host "Project: $PSScriptRoot"
Write-Host "Date: $(Get-Date)"
Write-Host ""

# 1. Project environment
Write-Host "`n=== 1. ENVIRONMENT ==="

Test-Check "Git project root" {
    $expected = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    $actualRaw = git rev-parse --show-toplevel

    if ($LASTEXITCODE -ne 0) { throw "Git root unavailable." }

    $actual = [IO.Path]::GetFullPath(
        $actualRaw.Trim().Replace('/', '\')
    ).TrimEnd('\')

    if ($expected -ine $actual) {
        throw "Project root mismatch: $actual"
    }

    "Correct project root."
}

Test-Check "Python" {
    $v = python --version
    if ($LASTEXITCODE -ne 0) { throw "Python unavailable." }
    $v
}

Test-Check "Node and npm" {
    $n = node --version
    if ($LASTEXITCODE -ne 0) { throw "Node unavailable." }
    $npm = npm --version
    if ($LASTEXITCODE -ne 0) { throw "npm unavailable." }
    "Node $n; npm $npm"
}

# 2. Backend tests on isolated SQLite
Write-Host "`n=== 2. BACKEND TESTS ==="

Test-Check "Backend pytest - isolated SQLite" {
    $testDb = Join-Path $env:TEMP (
        "hg-master-{0}.db" -f (Get-Date -Format "yyyyMMddHHmmssfff")
    )

    $oldUrl = $env:DATABASE_URL

    try {
        $env:DATABASE_URL = "sqlite:///$($testDb.Replace('\','/'))"

        Push-Location (Join-Path $PSScriptRoot "backend")
        try {
            $out = @(python -m pytest -q 2>&1)
            $exitCode = $LASTEXITCODE

            if ($exitCode -ne 0) {
                throw ($out -join "`n")
            }

            ($out | Select-Object -Last 3) -join " "
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($null -eq $oldUrl) {
            Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        }
        else {
            $env:DATABASE_URL = $oldUrl
        }

        if (Test-Path $testDb) {
            Remove-Item $testDb -Force
        }
    }
}

# 3. Frontend production build
Write-Host "`n=== 3. FRONTEND ==="

Test-Check "Frontend TypeScript and production build" {
    Push-Location (Join-Path $PSScriptRoot "frontend")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

        if (-not (Test-Path ".\dist\index.html")) {
            throw "Missing frontend dist/index.html."
        }

        "Production build successful."
    }
    finally {
        Pop-Location
    }
}

# 4. Docker
Write-Host "`n=== 4. DOCKER ==="

Test-Check "Docker Compose configuration" {
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Invalid Compose configuration." }
    "Compose configuration valid."
}

Test-Check "Six expected containers running" {
    $expected = @(
        "db", "api", "frontend",
        "prometheus", "alertmanager", "grafana"
    )

    $running = @(docker compose ps --services --filter "status=running")

    if ($LASTEXITCODE -ne 0) { throw "Docker inspection failed." }

    $missing = @($expected | Where-Object { $_ -notin $running })

    if ($missing.Count -gt 0) {
        throw "Missing running services: $($missing -join ', ')"
    }

    "All six services running."
}

Test-Check "PostgreSQL readiness" {
    docker compose exec -T db pg_isready -U harvestguard -d harvestguard
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL not ready." }
    "PostgreSQL ready."
}

# 5. Application endpoints
Write-Host "`n=== 5. APPLICATION ==="

Test-Check "Backend health" {
    $r = Get-Json "http://127.0.0.1:8001/health"
    if ($r.status -ne "ok") { throw "Unexpected health response." }
    "API healthy."
}

Test-Check "Frontend HTTP" {
    $r = Invoke-WebRequest `
        -Uri "http://127.0.0.1:5174" `
        -UseBasicParsing -TimeoutSec 10

    if ([int]$r.StatusCode -ne 200) { throw "HTTP status not 200." }
    "HTTP 200."
}

Test-Check "Inventory API read" {
    $response = Get-Json "http://127.0.0.1:8001/api/inventory"
    $count = if ($null -eq $response) { 0 } else { @($response).Count }
    "Inventory records: $count"
}

Test-Check "Waste API read" {
    $response = Get-Json "http://127.0.0.1:8001/api/waste?limit=500"
    $count = if ($null -eq $response) { 0 } else { @($response).Count }
    "Waste records: $count"
}

Test-Check "Analytics API" {
    $r = Get-Json "http://127.0.0.1:8001/api/analytics/summary"

    if ($r.data_source -ne "database") {
        throw "Unexpected analytics source."
    }

    "Items: $($r.item_count); value: $($r.inventory_value); weekly waste: $($r.waste_cost_this_week) $($r.currency)"
}

Test-Check "Application metrics endpoint" {
    $r = Invoke-WebRequest `
        -Uri "http://127.0.0.1:8001/metrics" `
        -UseBasicParsing -TimeoutSec 10

    if ($r.Content -notmatch "harvestguard_http_requests_total") {
        throw "HarvestGuard metric not found."
    }

    "HTTP application metrics available."
}

# 6. Prometheus
Write-Host "`n=== 6. PROMETHEUS ==="

Test-Check "Prometheus readiness" {
    $r = Invoke-WebRequest `
        -Uri "http://127.0.0.1:19091/-/ready" `
        -UseBasicParsing -TimeoutSec 10

    if ($r.StatusCode -ne 200) { throw "Prometheus not ready." }
    "Ready."
}

Test-Check "Prometheus API target" {
    $r = Get-Json "http://127.0.0.1:19091/api/v1/targets?state=active"

    if ($r.status -ne "success") { throw "Target API failed." }

    $targets = @($r.data.activeTargets | Where-Object {
        $_.scrapeUrl -match "api" -and $_.health -eq "up"
    })

    if ($targets.Count -eq 0) { throw "Healthy API target not found." }

    $targets[0].scrapeUrl
}

Test-Check "Four Prometheus alert rules" {
    $r = Get-Json "http://127.0.0.1:19091/api/v1/rules"

    if ($r.status -ne "success") { throw "Rules API failed." }

    $rules = @($r.data.groups | ForEach-Object { $_.rules })
    $names = @($rules | ForEach-Object { $_.name })

    $expected = @(
        "HarvestGuardApiUnavailable",
        "HarvestGuardPrometheusTargetMissing",
        "HarvestGuardHighHttp5xxRate",
        "HarvestGuardHighApiLatency"
    )

    $missing = @($expected | Where-Object { $_ -notin $names })

    if ($missing.Count -gt 0) {
        throw "Missing rules: $($missing -join ', ')"
    }

    "All four rules loaded."
}

Test-Check "Prometheus Alertmanager connection" {
    $r = Get-Json "http://127.0.0.1:19091/api/v1/alertmanagers"

    if ($r.status -ne "success") { throw "Alertmanager API failed." }

    $active = @($r.data.activeAlertmanagers)

    if ($active.Count -eq 0) { throw "No active Alertmanager connection." }

    "Active Alertmanager connections: $($active.Count)"
}

# 7. Grafana and Alertmanager
Write-Host "`n=== 7. GRAFANA ==="

Test-Check "Grafana health" {
    $r = Get-Json "http://127.0.0.1:3001/api/health"
    if ($r.database -ne "ok") { throw "Grafana database unhealthy." }
    "Grafana database healthy."
}

Test-Check "Alertmanager readiness" {
    $r = Invoke-WebRequest `
        -Uri "http://127.0.0.1:9093/-/ready" `
        -UseBasicParsing -TimeoutSec 10

    if ($r.StatusCode -ne 200) { throw "Alertmanager not ready." }
    "Alertmanager ready."
}

# 8. Provisioning and dashboard
Write-Host "`n=== 8. OBSERVABILITY CONFIGURATION ==="

Test-Check "Grafana provisioning files" {
    $files = @(
        "ops/grafana/provisioning/datasources/prometheus.yml",
        "ops/grafana/provisioning/dashboards/provider.yml",
        "ops/grafana/provisioning/dashboard-files/harvestguard-overview.json"
    )

    $missing = @($files | Where-Object {
        -not (Test-Path (Join-Path $PSScriptRoot $_))
    })

    if ($missing.Count -gt 0) { throw "Missing: $($missing -join ', ')" }

    "All three provisioning files found."
}

Test-Check "Grafana dashboard JSON validity" {
    $file = Join-Path $PSScriptRoot `
        "ops/grafana/provisioning/dashboard-files/harvestguard-overview.json"

    $dashboard = Get-Content $file -Raw | ConvertFrom-Json

    if (-not $dashboard.panels) { throw "Dashboard has no panels." }

    "Dashboard JSON valid; panels: $(@($dashboard.panels).Count)"
}

Test-Check "Prometheus and Alertmanager configuration files" {
    $files = @(
        "ops/prometheus.yml",
        "ops/alerts.yml",
        "ops/alertmanager.yml"
    )

    $missing = @($files | Where-Object {
        -not (Test-Path (Join-Path $PSScriptRoot $_))
    })

    if ($missing.Count -gt 0) { throw "Missing: $($missing -join ', ')" }

    "All three configuration files found."
}

# 9. Documentation
Write-Host "`n=== 9. DOCUMENTATION ==="

Test-Check "Fourteen project documentation files" {
    $files = @(
        "README.md",
        "docs/specification.md",
        "docs/acceptance-criteria.md",
        "docs/architecture.md",
        "docs/development-process.md",
        "docs/testing.md",
        "docs/deployment.md",
        "docs/rollback.md",
        "docs/observability.md",
        "docs/incident-response.md",
        "docs/implementation-evidence.md",
        "docs/agents/responder-policy.md",
        "docs/agents/team.md",
        "docs/issues/issue-plan.md"
    )

    $missing = @($files | Where-Object {
        -not (Test-Path (Join-Path $PSScriptRoot $_) -PathType Leaf)
    })

    if ($missing.Count -gt 0) { throw "Missing: $($missing -join ', ')" }

    "All $($files.Count) expected documents found."
}

# 10. Git
Write-Host "`n=== 10. GIT ==="

Test-Check "Git staged and unstaged whitespace" {
    $unstaged = @(& $env:ComSpec /d /c "git diff --check 2>&1")
    $unstagedExit = $LASTEXITCODE

    $staged = @(& $env:ComSpec /d /c "git diff --cached --check 2>&1")
    $stagedExit = $LASTEXITCODE

    $all = @($unstaged) + @($staged)

    $errors = @($all | Where-Object {
        "$_" -match ':\d+:\s+(trailing whitespace|space before tab)'
    })

    if ($unstagedExit -ne 0 -or $stagedExit -ne 0 -or $errors.Count -gt 0) {
        throw "Actual Git whitespace issue detected."
    }

    "No whitespace errors. Line-ending notices are informational."
}

Test-Check "Git branch and status" {
    $branch = git branch --show-current
    if ($LASTEXITCODE -ne 0) { throw "Git branch unavailable." }

    $status = @(git status --short)
    "Branch: $branch; changed/untracked entries: $($status.Count)"
}

# 11. Report
Write-Host ""
Write-Host "================================================"
Write-Host "           FINAL HEALTH CHECK REPORT"
Write-Host "================================================"

$script:Results | Format-Table -AutoSize -Wrap

$passed = @($script:Results | Where-Object Status -eq "PASS").Count
$failed = @($script:Results | Where-Object Status -eq "FAIL").Count
$total = $script:Results.Count

Write-Host ""
Write-Host "TOTAL CHECKS : $total"
Write-Host "PASSED       : $passed" -ForegroundColor Green
Write-Host "FAILED       : $failed" -ForegroundColor Red

if ($failed -eq 0) {
    Write-Host "`nOVERALL RESULT: ALL CHECKS PASSED" -ForegroundColor Green
}
else {
    Write-Host "`nOVERALL RESULT: INVESTIGATION REQUIRED" -ForegroundColor Red
}

Write-Host ""
Write-Host "Safety: no production records created or deleted."
Write-Host "No containers restarted; no Docker volumes deleted."
Write-Host "Backend tests use isolated temporary SQLite."
Write-Host "================================================"

