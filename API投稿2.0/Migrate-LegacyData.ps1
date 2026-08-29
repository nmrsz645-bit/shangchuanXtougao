$ErrorActionPreference = 'Stop'
$app = $PSScriptRoot
$marker = Join-Path $app '.legacy-data-migrated'
if (Test-Path -LiteralPath $marker) { exit 0 }

$previous = $app + '.previous'
if (-not (Test-Path -LiteralPath $previous -PathType Container)) {
    [IO.File]::WriteAllText($marker, 'no-legacy-previous', [Text.UTF8Encoding]::new($false))
    exit 0
}

function Copy-UserTree([string]$Name) {
    $source = Join-Path $previous $Name
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { return }
    Get-ChildItem -LiteralPath $source -File -Recurse -Force | ForEach-Object {
        $relative = $_.FullName.Substring($source.Length).TrimStart('\\')
        $target = Join-Path (Join-Path $app $Name) $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

try {
    # Update packages never replace these folders.  This is only for safely
    # recovering the same user's data when an older installation is upgraded.
    foreach ($name in @('config', 'data', 'logs')) { Copy-UserTree $name }
    [IO.File]::WriteAllText($marker, 'migrated', [Text.UTF8Encoding]::new($false))
}
catch {
    [IO.File]::WriteAllText((Join-Path $app 'legacy-migration-error.txt'), $_.Exception.ToString(), [Text.UTF8Encoding]::new($false))
    exit 1
}
