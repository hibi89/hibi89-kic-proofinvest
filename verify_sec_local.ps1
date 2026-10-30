# KUODRA P21: read-only Windows acceptance of already-held local SEC files.
# NO SEC/LLM HTTP, NO SQLite, NO generated capture receipt, NO file writes.
# Execute from the existing KIC repository (Python 3.11 on PATH).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDirectory,
    [Parameter(Mandatory = $true)]
    [string]$Cik,
    [Parameter(Mandatory = $true)]
    [string]$Accession,
    [Parameter(Mandatory = $true)]
    [string]$AsOf,
    [Parameter(Mandatory = $true)]
    [string]$CollectedAt,
    [string]$SubmissionsFile = "submissions.json",
    [string]$CompanyFactsFile = "companyfacts.json",
    [string]$OriginalFile = "original.html"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    if ($Cik -cnotmatch '^[0-9]{10}$' -or
        $Accession -cnotmatch '^[0-9]{10}-[0-9]{2}-[0-9]{6}$' -or
        -not $Accession.StartsWith($Cik + "-") -or
        $AsOf -cnotmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' -or
        $CollectedAt -cnotmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}T') {
        throw "INVALID_OPERATOR_SELECTION"
    }
    $names = @($SubmissionsFile, $CompanyFactsFile, $OriginalFile)
    foreach ($name in $names) {
        if ([string]::IsNullOrWhiteSpace($name) -or
            $name -match '[/\\]' -or
            $name -in @(".", "..") -or
            [System.IO.Path]::GetFileName($name) -cne $name) {
            throw "SOURCE_FILENAME_MUST_BE_A_LEAF"
        }
    }
    $directory = [System.IO.Path]::GetFullPath($SourceDirectory)
    if (-not [System.IO.Directory]::Exists($directory)) {
        throw "SOURCE_FOLDER_MISSING"
    }
    $python = Get-Command python -CommandType Application -ErrorAction Stop
    if ($null -eq $python) {
        throw "PYTHON_NOT_FOUND"
    }
    # Resolve a plain executable STRING. & $python.Source can be parsed as
    # invoking a member expression rather than a valid command in WinPS 5.1.
    $pythonExecutable = [string]$python.Source
    if ([string]::IsNullOrWhiteSpace($pythonExecutable)) {
        throw "PYTHON_EXECUTABLE_NOT_RESOLVED"
    }
} catch {
    [Console]::Error.WriteLine("P21_LOCAL_PREFLIGHT_BLOCKED")
    exit 2
}

$pythonArgs = @(
    "-B", "-m", "proofinvest.kuodra_loose_sec_compatibility",
    "--submissions", ([System.IO.Path]::Combine($directory, $SubmissionsFile)),
    "--companyfacts", ([System.IO.Path]::Combine($directory, $CompanyFactsFile)),
    "--original", ([System.IO.Path]::Combine($directory, $OriginalFile)),
    "--cik", $Cik, "--accession", $Accession,
    "--as-of", $AsOf, "--collected-at", $CollectedAt
)
Push-Location -LiteralPath $PSScriptRoot
try {
    & $pythonExecutable @pythonArgs
    $code = $LASTEXITCODE
    if ($null -eq $code -or $code -notin @(0, 2)) {
        [Console]::Error.WriteLine("P21_LOCAL_PROCESS_UNEXPECTED_EXIT")
        $code = 2
    }
} catch {
    # Fail without echoing file paths, SEC raw source bytes or stack traces.
    # Only the exception CLASS is logged: no private files/paths/traces.
    $typeName = $_.Exception.GetType().Name
    [Console]::Error.WriteLine("P21_LOCAL_INSPECTION_FAILED_" + $typeName)
    $code = 2
} finally {
    Pop-Location
}
exit $code
