[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\kambar\harvestguard-ai',
    [switch]$RunPersistenceProbe,
    [switch]$SkipReadmeSync
)

# HarvestGuard rubric completion runner.
# Safe defaults: backs up files before edits; no commit, push, service restart,
# database reset, volume deletion, password reset, or remote issue comments.
# The optional persistence probe creates one uniquely named synthetic row,
# reads it back, and deletes only that exact row. It requires explicit opt-in.

$ErrorActionPreference = 'Stop'
$script:Checks = New-Object System.Collections.Generic.List[object]
$script:Evidence = New-Object System.Collections.Generic.List[string]
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

function Add-Check {
    param([string]$Name,[ValidateSet('PASS','WARN','FAIL','INFO')][string]$Status,[string]$Detail)
    $script:Checks.Add([pscustomobject]@{Check=$Name;Status=$Status;Detail=$Detail})
    $c = switch ($Status) {'PASS' {'Green'} 'WARN' {'Yellow'} 'FAIL' {'Red'} default {'Cyan'}}
    Write-Host ("[{0}] {1}: {2}" -f $Status,$Name,$Detail) -ForegroundColor $c
    $script:Evidence.Add(("- **{0} — {1}:** {2}" -f $Status,$Name,$Detail))
}

function Invoke-External {
    param([string]$File,[string[]]$Arguments,[string]$WorkingDirectory)
    Push-Location $WorkingDirectory
    try {
        $output = & $File @Arguments 2>&1
        $code = $LASTEXITCODE
        return [pscustomobject]@{ExitCode=$code;Output=(($output | Out-String).Trim())}
    } finally { Pop-Location }
}

function Backup-IfPresent {
    param([string]$Path,[string]$BackupRoot)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $relative = $Path.Substring($ProjectRoot.Length).TrimStart('\')
        $dest = Join-Path $BackupRoot $relative
        $parent = Split-Path -Parent $dest
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $Path -Destination $dest -Force
        return $dest
    }
    return $null
}

function Test-HttpEndpoint {
    param([string]$Name,[string]$Uri,[string]$ExpectedText='')
    try {
        $r = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 8
        if ([int]$r.StatusCode -ge 200 -and [int]$r.StatusCode -lt 300) {
            if ($ExpectedText -and $r.Content -notmatch [regex]::Escape($ExpectedText)) {
                Add-Check $Name 'WARN' ("HTTP {0}; expected marker not found" -f $r.StatusCode)
            } else { Add-Check $Name 'PASS' ("HTTP {0}" -f $r.StatusCode) }
            return $r
        }
        Add-Check $Name 'FAIL' ("HTTP {0}" -f $r.StatusCode)
    } catch { Add-Check $Name 'WARN' $_.Exception.Message }
    return $null
}

function New-CiWorkflow {
    return @'
name: HarvestGuard CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: harvestguard-ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend-and-frontend:
    name: Backend tests and frontend build
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
          cache: pip
          cache-dependency-path: backend/requirements.txt

      - name: Install backend dependencies
        run: python -m pip install --upgrade pip && python -m pip install -r backend/requirements.txt pytest httpx

      - name: Run backend unit and API tests
        working-directory: backend
        env:
          PYTHONPATH: ${{ github.workspace }}/backend
        run: python -m pytest tests -q

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '24'
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Build frontend
        working-directory: frontend
        run: npm run build
'@
}

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    Write-Error "Project folder not found: $ProjectRoot"
    exit 2
}
Set-Location -LiteralPath $ProjectRoot
$gitRoot = (git rev-parse --show-toplevel 2>$null | Out-String).Trim()
if (-not $gitRoot -or [IO.Path]::GetFullPath($gitRoot) -ne [IO.Path]::GetFullPath($ProjectRoot)) {
    Write-Error 'Safety stop: selected folder is not the expected Git repository root.'
    exit 2
}

$backupRoot = Join-Path $ProjectRoot ("backups\rubric-completion-{0}" -f $stamp)
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$reportDir = Join-Path $ProjectRoot 'artifacts\rubric-evidence'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$reportPath = Join-Path $reportDir ("rubric-evidence-{0}.md" -f $stamp)

Write-Host "`n=== HARVESTGUARD RUBRIC COMPLETION ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host "Backup:  $backupRoot"
Write-Host 'Safe mode: no commit/push, no service restart, no destructive database operations.' -ForegroundColor Yellow

# Repository identity and existing tracker evidence
$remote = (git remote get-url origin 2>$null | Out-String).Trim()
if ($remote -match 'jcdumlao14/harvestguard-ai') { Add-Check 'GitHub origin' 'PASS' 'Origin points to jcdumlao14/harvestguard-ai.' }
else { Add-Check 'GitHub origin' 'WARN' ("Unexpected or missing origin: {0}" -f $remote) }

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    $auth = Invoke-External 'gh' @('auth','status') $ProjectRoot
    if ($auth.ExitCode -eq 0) { Add-Check 'GitHub CLI authentication' 'PASS' 'gh auth status succeeded.' }
    else { Add-Check 'GitHub CLI authentication' 'WARN' 'gh is installed but not authenticated.' }
    $issues = Invoke-External 'gh' @('issue','list','--repo','jcdumlao14/harvestguard-ai','--state','open','--limit','100','--json','number,title,url') $ProjectRoot
    if ($issues.ExitCode -eq 0) {
        try {
            $issueRows = @($issues.Output | ConvertFrom-Json)
            Add-Check 'Public GitHub task tracker' 'PASS' ("Found {0} open public issue(s)." -f $issueRows.Count)
            foreach ($i in $issueRows) { $script:Evidence.Add(("- Public issue #{0}: [{1}]({2})" -f $i.number,$i.title,$i.url)) }
        } catch { Add-Check 'Public GitHub task tracker' 'WARN' 'Could not parse gh issue list output.' }
    } else { Add-Check 'Public GitHub task tracker' 'WARN' 'Could not query issues; check gh authentication/network.' }
} else { Add-Check 'GitHub CLI' 'WARN' 'gh CLI not installed; public tracker cannot be queried automatically.' }

# Back up any files that this runner may update.
$readmePath = Join-Path $ProjectRoot 'README.md'
$workflowPath = Join-Path $ProjectRoot '.github\workflows\ci.yml'
$readmeBackup = Backup-IfPresent $readmePath $backupRoot
$workflowBackup = Backup-IfPresent $workflowPath $backupRoot
if ($readmeBackup) { Add-Check 'README backup' 'PASS' $readmeBackup }
if ($workflowBackup) { Add-Check 'Existing CI workflow backup' 'PASS' $workflowBackup }

# Add CI workflow only if one is not already present; never overwrite an existing workflow.
$workflowDir = Split-Path -Parent $workflowPath
if (-not (Test-Path $workflowDir)) { New-Item -ItemType Directory -Path $workflowDir -Force | Out-Null }
if (-not (Test-Path $workflowPath)) {
    Set-Content -LiteralPath $workflowPath -Value (New-CiWorkflow) -Encoding UTF8
    Add-Check 'GitHub Actions CI workflow' 'PASS' 'Created .github/workflows/ci.yml for pull requests and pushes to main; runs backend tests and frontend build.'
} else {
    Add-Check 'GitHub Actions CI workflow' 'INFO' 'A CI workflow already exists; preserved it without overwriting.'
}

# Update only known stale README statements; preserve all other content.
if (-not $SkipReadmeSync -and (Test-Path $readmePath)) {
    $readme = Get-Content -LiteralPath $readmePath -Raw
    $original = $readme
    $oldNote = 'Deployment note: Docker Compose files and Dockerfiles are not present in the inspected checkout. Container orchestration, production CI/CD, and observability should be documented as operational only after implementation and verification.'
    $newNote = 'Current local implementation update (2026-10-30): the working local environment has a seven-service Docker Compose stack (API, frontend, PostgreSQL, Prometheus, Grafana, Alertmanager, and Tempo). The local runtime has been verified independently. Public deployment is intentionally optional and is not claimed. See the generated `artifacts/rubric-evidence/` report for verification details.'
    if ($readme.Contains($oldNote)) { $readme = $readme.Replace($oldNote,$newNote) }

    $oldSectionPattern = '(?s)## Docker Compose and deployment status\r?\n.*?(?=\r?\n## Documentation)'
    $newSection = @'
## Docker Compose and deployment status

The local development environment is orchestrated with Docker Compose. The verified local stack contains the FastAPI API, React frontend, PostgreSQL database, Prometheus, Grafana, Alertmanager, and Grafana Tempo.

Start the local stack from the repository root with:

```powershell
docker compose up -d --build
```

Validate the Compose configuration without changing running services:

```powershell
docker compose config --quiet
```

Public deployment is optional and has intentionally been deferred to avoid recurring hosting costs. No public production URL is claimed. GitHub Actions CI is configured to run backend tests and the frontend production build on pull requests and pushes to `main`; it becomes active on GitHub after this workflow is committed and pushed.

'@
    if ($readme -match $oldSectionPattern) { $readme = [regex]::Replace($readme,$oldSectionPattern,$newSection) }
    $readme = $readme.Replace('http://127.0.0.1:5173/','http://127.0.0.1:5174/')
    $readme = $readme.Replace('http://localhost:5173/','http://localhost:5174/')
    $readme = $readme.Replace('http://127.0.0.1:8000/','http://127.0.0.1:8001/')
    $readme = $readme.Replace('http://localhost:8000/','http://localhost:8001/')
    if ($readme -ne $original) {
        Set-Content -LiteralPath $readmePath -Value $readme -Encoding UTF8
        Add-Check 'README status synchronization' 'PASS' 'Updated only known stale deployment statements and local ports; original backed up.'
    } else { Add-Check 'README status synchronization' 'WARN' 'No known stale text matched; README preserved. Review public README against current local implementation.' }
} elseif ($SkipReadmeSync) {
    Add-Check 'README status synchronization' 'INFO' 'Skipped by request.'
}

# Run backend tests using the existing virtual environment; do not install or recreate environments.
$backendDir = Join-Path $ProjectRoot 'backend'
$backendPythonCandidates = @(
    (Join-Path $backendDir '.venv\Scripts\python.exe'),
    (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
)
$backendPython = $backendPythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($backendPython -and (Test-Path (Join-Path $backendDir 'tests'))) {
    $test = Invoke-External $backendPython @('-m','pytest','tests','-q') $backendDir
    if ($test.ExitCode -eq 0) { Add-Check 'Backend test suite' 'PASS' $test.Output }
    else { Add-Check 'Backend test suite' 'FAIL' $test.Output }
} else { Add-Check 'Backend test suite' 'WARN' 'Existing backend virtual environment or backend/tests folder not found; no environment was created.' }

# Classify existing tests conservatively; do not claim both test types from a single undifferentiated pass.
$testFiles = @()
if (Test-Path (Join-Path $backendDir 'tests')) { $testFiles = @(Get-ChildItem (Join-Path $backendDir 'tests') -Recurse -File -Filter 'test_*.py') }
$hasApiClientTests = $false
$hasUnitStyleTests = $false
foreach ($tf in $testFiles) {
    $src = Get-Content -LiteralPath $tf.FullName -Raw
    if ($src -match 'TestClient|AsyncClient|httpx\.(get|post|put|patch|delete)|client\.(get|post|put|patch|delete)') { $hasApiClientTests = $true }
    if ($src -match '^\s*(def|async def) test_' -and $src -notmatch 'TestClient|AsyncClient') { $hasUnitStyleTests = $true }
}
if ($hasApiClientTests -and $hasUnitStyleTests) { Add-Check 'Unit and API/integration test coverage' 'PASS' 'Test sources include direct unit-style tests and HTTP/API client tests.' }
elseif ($hasApiClientTests) { Add-Check 'Unit and API/integration test coverage' 'WARN' 'API/integration-style tests detected; separate unit-test evidence was not confidently identified.' }
elseif ($hasUnitStyleTests) { Add-Check 'Unit and API/integration test coverage' 'WARN' 'Unit-style tests detected; API/integration test evidence was not confidently identified.' }
else { Add-Check 'Unit and API/integration test coverage' 'WARN' 'Could not classify both unit and API/integration tests from the existing test sources.' }

# Run frontend build only if dependencies are already installed; do not run npm ci locally.
$frontendDir = Join-Path $ProjectRoot 'frontend'
if ((Test-Path (Join-Path $frontendDir 'node_modules')) -and (Test-Path (Join-Path $frontendDir 'package.json'))) {
    $build = Invoke-External 'npm' @('run','build') $frontendDir
    if ($build.ExitCode -eq 0) { Add-Check 'Frontend production build' 'PASS' $build.Output }
    else { Add-Check 'Frontend production build' 'FAIL' $build.Output }
} else { Add-Check 'Frontend production build' 'WARN' 'frontend/node_modules is absent; skipped local install to avoid changing dependencies. CI uses npm ci.' }

# Compose validation only; no compose up/down/restart commands are issued.
$composeFileExists = (Test-Path (Join-Path $ProjectRoot 'compose.yaml')) -or (Test-Path (Join-Path $ProjectRoot 'compose.yml')) -or (Test-Path (Join-Path $ProjectRoot 'docker-compose.yml')) -or (Test-Path (Join-Path $ProjectRoot 'docker-compose.yaml'))
if ($composeFileExists -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    $compose = Invoke-External 'docker' @('compose','config','--quiet') $ProjectRoot
    if ($compose.ExitCode -eq 0) { Add-Check 'Docker Compose configuration' 'PASS' 'Configuration validates; running services were not changed.' }
    else { Add-Check 'Docker Compose configuration' 'FAIL' $compose.Output }
} else { Add-Check 'Docker Compose configuration' 'WARN' 'Compose file or Docker CLI not found.' }

# Lightweight live smoke checks; do not re-audit all telemetry components.
$api = Test-HttpEndpoint 'API health' 'http://127.0.0.1:8001/health' 'harvestguard-api'
$front = Test-HttpEndpoint 'Frontend HTTP' 'http://127.0.0.1:5174/'
$inventory = Test-HttpEndpoint 'Inventory API read path' 'http://127.0.0.1:8001/api/inventory'
if ($inventory) {
    try {
        $items = @($inventory.Content | ConvertFrom-Json)
        Add-Check 'API inventory response' 'PASS' ("GET /api/inventory returned {0} record(s)." -f $items.Count)
    } catch { Add-Check 'API inventory response' 'WARN' 'Endpoint responded but response was not a JSON collection.' }
}

# Optional controlled persistence probe. Requires explicit -RunPersistenceProbe.
if ($RunPersistenceProbe) {
    Write-Host "`nPersistence probe requested: will create one uniquely named synthetic inventory item, read it, then delete that exact item." -ForegroundColor Yellow
    $openapi = $null
    try { $openapi = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/openapi.json' -TimeoutSec 8 } catch {}
    if (-not $openapi -or -not $openapi.paths.'/api/inventory'.post) {
        Add-Check 'API-to-database persistence probe' 'WARN' 'OpenAPI does not expose POST /api/inventory; no database write attempted.'
    } else {
        $postOp = $openapi.paths.'/api/inventory'.post
        $schemaRef = $postOp.requestBody.content.'application/json'.schema.'$ref'
        $schemaName = if ($schemaRef) { ($schemaRef -split '/')[-1] } else { $null }
        $schema = if ($schemaName) { $openapi.components.schemas.$schemaName } else { $null }
        if (-not $schema -or -not $schema.properties) {
            Add-Check 'API-to-database persistence probe' 'WARN' 'Could not safely infer request schema; no database write attempted.'
        } else {
            $guid = [guid]::NewGuid().ToString('N').Substring(0,12)
            $payload = @{}
            foreach ($schemaProperty in $schema.properties.PSObject.Properties) {
                $propName = $schemaProperty.Name
                $p = $schemaProperty.Value
                $type = [string]$p.type
                if ($propName -match 'sku|code') { $payload[$propName] = "HG-AUDIT-$guid" }
                elseif ($propName -match 'name|title') { $payload[$propName] = "HarvestGuard Automated Persistence Probe $guid" }
                elseif ($propName -match 'category') { $payload[$propName] = 'automated-audit' }
                elseif ($propName -match 'unit$') { $payload[$propName] = 'unit' }
                elseif ($propName -match 'expiry|date') { $payload[$propName] = (Get-Date).AddDays(30).ToString('yyyy-MM-dd') }
                elseif ($propName -match 'quantity|amount') { $payload[$propName] = 1 }
                elseif ($propName -match 'cost|price|value') { $payload[$propName] = 0.01 }
                elseif ($propName -match 'reorder|threshold') { $payload[$propName] = 0 }
                elseif ($type -eq 'string') { $payload[$propName] = "audit-$guid" }
                elseif ($type -eq 'integer' -or $type -eq 'number') { $payload[$propName] = 1 }
                elseif ($type -eq 'boolean') { $payload[$propName] = $false }
            }
            $required = @($schema.required)
            $missing = @($required | Where-Object { -not $payload.ContainsKey($_) })
            if ($missing.Count -gt 0 -or -not $openapi.paths.'/api/inventory/{item_id}'.delete -or -not $openapi.paths.'/api/inventory/{item_id}'.get) {
                Add-Check 'API-to-database persistence probe' 'WARN' 'Request schema is ambiguous or safe DELETE cleanup is unavailable; no database write attempted.'
            } else {
                $createdId = $null
                try {
                    $created = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/inventory' -Method Post -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 8) -TimeoutSec 10
                    $createdId = $created.id
                    if (-not $createdId) { throw 'Create response did not contain an id; cannot safely clean up.' }
                    $readBack = Invoke-RestMethod -Uri ("http://127.0.0.1:8001/api/inventory/{0}" -f $createdId) -TimeoutSec 10
                    if ($readBack.id -ne $createdId) { throw 'Read-back ID did not match the created record.' }
                    $deleteResponse = Invoke-WebRequest -Uri ("http://127.0.0.1:8001/api/inventory/{0}" -f $createdId) -Method Delete -UseBasicParsing -TimeoutSec 10
                    if ([int]$deleteResponse.StatusCode -notin @(200,202,204)) { throw ("Cleanup returned HTTP {0}" -f $deleteResponse.StatusCode) }
                    Add-Check 'API-to-database persistence probe' 'PASS' 'Synthetic record created, read back by ID, and exact record deleted.'
                } catch {
                    Add-Check 'API-to-database persistence probe' 'FAIL' ("Probe failed: {0}" -f $_.Exception.Message)
                    if ($createdId) {
                        try { Invoke-WebRequest -Uri ("http://127.0.0.1:8001/api/inventory/{0}" -f $createdId) -Method Delete -UseBasicParsing -TimeoutSec 10 | Out-Null; Add-Check 'Persistence probe cleanup' 'PASS' 'Attempted deletion of only the probe record.' }
                        catch { Add-Check 'Persistence probe cleanup' 'FAIL' ("Could not delete probe record ID {0}: {1}" -f $createdId,$_.Exception.Message) }
                    }
                }
            }
        }
    }
} else {
    Add-Check 'API-to-database write persistence' 'INFO' 'Not run in safe default mode. Re-run with -RunPersistenceProbe to create/read/delete one uniquely named synthetic row.'
}

# GitHub workflow activation status: a local workflow is not public until committed/pushed.
if ($gh) {
    $runs = Invoke-External 'gh' @('run','list','--repo','jcdumlao14/harvestguard-ai','--limit','5','--json','databaseId,status,conclusion,workflowName,url') $ProjectRoot
    if ($runs.ExitCode -eq 0) {
        try {
            $runRows = @($runs.Output | ConvertFrom-Json)
            if ($runRows.Count -gt 0) {
                $successful = @($runRows | Where-Object { $_.conclusion -eq 'success' }).Count
                Add-Check 'Public GitHub Actions runs' 'INFO' ("Found {0} recent run(s), {1} successful." -f $runRows.Count,$successful)
                foreach ($r in $runRows) { $script:Evidence.Add(("- GitHub Actions: {0} — {1} — {2}" -f $r.workflowName,$r.conclusion,$r.url)) }
            } else { Add-Check 'Public GitHub Actions runs' 'WARN' 'No public workflow runs found yet; workflow must be committed and pushed to activate CI.' }
        } catch { Add-Check 'Public GitHub Actions runs' 'WARN' 'Could not parse GitHub Actions run list.' }
    } else { Add-Check 'Public GitHub Actions runs' 'WARN' 'Could not query GitHub Actions runs.' }
}

# Evidence report generation.
$pass = @($script:Checks | Where-Object Status -eq 'PASS').Count
$warn = @($script:Checks | Where-Object Status -eq 'WARN').Count
$fail = @($script:Checks | Where-Object Status -eq 'FAIL').Count
$info = @($script:Checks | Where-Object Status -eq 'INFO').Count
$report = @()
$report += '# HarvestGuard AI — Rubric Evidence Report'
$report += ''
$report += ("- Generated: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
$report += '- Scope: local project completion checks; no deployment performed.'
$report += '- Safety: no commit/push, no service restart, no volume deletion, no password reset.'
$report += ("- Summary: **{0} PASS / {1} WARN / {2} FAIL / {3} INFO**" -f $pass,$warn,$fail,$info)
$report += ''
$report += '## Automated results'
$report += ''
foreach ($c in $script:Checks) { $report += ("- **{0} — {1}:** {2}" -f $c.Status,$c.Check,($c.Detail -replace '\r?\n','; ')) }
$report += ''
$report += '## Public tracker and CI evidence'
$report += ''
$report += $script:Evidence
$report += ''
$report += '## Rubric limitations / items not auto-claimed'
$report += ''
$report += '- Public task tracker exists, but agent execution evidence must be attached to the relevant GitHub issues or pull requests after actual work is linked.'
$report += '- A local CI workflow does not earn CI points until it is committed, pushed, and a successful GitHub Actions run is visible.'
$report += '- Public deployment is intentionally deferred; no deployment points are claimed.'
$report += '- The current on-call webhook receives and evaluates alerts, but it does not autonomously remediate incidents. Do not claim the on-call-agent points until a bounded, approved action is implemented and independently verified.'
$report += '- A passing inventory read is not proof of write persistence. Use the opt-in persistence probe for create/read/delete evidence.'
$report | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Host "`n=== FINAL SUMMARY ===" -ForegroundColor Cyan
$script:Checks | Format-Table -AutoSize -Wrap
Write-Host ("PASS: {0}  WARN: {1}  FAIL: {2}  INFO: {3}" -f $pass,$warn,$fail,$info) -ForegroundColor Cyan
Write-Host "Evidence report: $reportPath" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor Green
Write-Host "`nNext required publication step: review git diff, then explicitly commit/push to activate GitHub Actions. This script does not publish changes." -ForegroundColor Yellow

if ($fail -gt 0) { exit 2 }
if ($warn -gt 0) { exit 1 }
exit 0
