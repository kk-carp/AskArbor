param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$StudentDoc = "docs/samples/t13/student_course_sample.md",
    [string]$CompanyDoc = "docs/samples/t13/company_policy_sample.md",
    [switch]$SkipStartApi,
    [switch]$SkipDockerUp,
    [int]$MaxHealthWaitSeconds = 90
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Ensure-FileExists {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "File not found: $Path"
    }
}

function Ask {
    param(
        [string]$Username,
        [string]$Question
    )
    $password = if ($env:DEMO_PASSWORD) { $env:DEMO_PASSWORD } else { "demo1234" }
    $loginPayload = @{
        username = $Username
        password = $password
    } | ConvertTo-Json -Depth 5 -Compress
    $askPayload = @{
        question = $Question
    } | ConvertTo-Json -Depth 5 -Compress

    $session = $null
    Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBase/login" `
        -ContentType "application/json; charset=utf-8" `
        -Body $loginPayload `
        -SessionVariable session | Out-Null

    return Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBase/ask" `
        -ContentType "application/json; charset=utf-8" `
        -Body $askPayload `
        -WebSession $session
}

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Push-Location $repoRoot

$apiProcess = $null
try {
    Ensure-FileExists $StudentDoc
    Ensure-FileExists $CompanyDoc

    if (-not $SkipDockerUp.IsPresent) {
        docker compose up -d | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose up -d failed. Start Docker Desktop or rerun with -SkipDockerUp."
        }
    }

    if (-not $SkipStartApi.IsPresent) {
        $apiProcess = Start-Process `
            -FilePath "python" `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
            -PassThru
    }

    $health = $null
    $healthReady = $false
    $maxAttempts = $MaxHealthWaitSeconds
    for ($i = 0; $i -lt $maxAttempts; $i++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod -Method Get -Uri "$ApiBase/health"
            if ($health.api -eq $true -and $health.database -eq $true -and $health.embedding_loaded -eq $true) {
                $healthReady = $true
                break
            }
        } catch {
            continue
        }
    }

    Assert-True ($null -ne $health) "Health check failed: API unreachable."
    Assert-True ($healthReady -eq $true) "Health check failed: API not ready (database/model not healthy)."

    $studentUpload = Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBase/documents" `
        -Form @{ space = "student"; file = Get-Item -LiteralPath $StudentDoc }
    Assert-True ($studentUpload.status -eq "ready") "Student upload status is not ready."
    Assert-True ($studentUpload.chunk_count -gt 0) "Student upload produced no chunks."

    $companyUpload = Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBase/documents" `
        -Form @{ space = "company"; file = Get-Item -LiteralPath $CompanyDoc }
    Assert-True ($companyUpload.status -eq "ready") "Company upload status is not ready."
    Assert-True ($companyUpload.chunk_count -gt 0) "Company upload produced no chunks."

    $studentHit = Ask -Username "student_demo" -Question "When is the assignment submission deadline?"
    Assert-True ($studentHit.hit -eq $true) "Student should hit course document."
    Assert-True ($studentHit.sources.Count -gt 0) "Student hit should return sources."
    Assert-True (($studentHit.sources | Where-Object { $_.space_id -ne "student" }).Count -eq 0) "Student result includes non-student sources."

    $studentBlocked = Ask -Username "student_demo" -Question "What is POLICY-CN-2026?"
    Assert-True ($studentBlocked.hit -eq $false) "Student asking company policy should miss."
    Assert-True ($studentBlocked.sources.Count -eq 0) "Student asking company policy should have no sources."
    $employeeHit = Ask -Username "employee_demo" -Question "What is POLICY-CN-2026?"
    Assert-True ($employeeHit.hit -eq $true) "Employee asking company policy should hit."
    Assert-True (($employeeHit.sources | Where-Object { $_.space_id -eq "company" }).Count -gt 0) "Employee hit should include company sources."

    $teachingStudent = Ask -Username "teaching_demo" -Question "When is the public Q and A window?"
    Assert-True ($teachingStudent.hit -eq $true) "Teaching role asking course should hit."
    Assert-True (($teachingStudent.sources | Where-Object { $_.space_id -eq "student" }).Count -gt 0) "Teaching course answer should include student sources."

    $teachingCompany = Ask -Username "teaching_demo" -Question "What is required before remote internal access?"
    Assert-True ($teachingCompany.hit -eq $true) "Teaching role asking company policy should hit."
    Assert-True (($teachingCompany.sources | Where-Object { $_.space_id -eq "company" }).Count -gt 0) "Teaching company answer should include company sources."

    $noAnswer = Ask -Username "student_demo" -Question "What time does the Mars base cafeteria open?"
    Assert-True ($noAnswer.hit -eq $false) "No-answer question should miss."
    Assert-True ($noAnswer.sources.Count -eq 0) "No-answer question should return no sources."
    Assert-True (-not [string]::IsNullOrWhiteSpace($noAnswer.answer)) "No-answer question should return a refusal answer."
    Assert-True ($studentBlocked.answer -eq $noAnswer.answer) "All miss cases should return the same fixed refusal answer."

    pytest tests/test_retrieve.py::test_search_chunks_builds_space_filtered_sql_and_maps_result -q
    if ($LASTEXITCODE -ne 0) {
        throw "Pytest SQL guardrail check failed."
    }

    Write-Host ""
    Write-Host "T13 acceptance passed: ingest, isolation, hits with sources, miss behavior, and SQL guardrails verified."
} finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
    }
    Pop-Location
}
