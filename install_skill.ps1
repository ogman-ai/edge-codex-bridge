param(
  [string]$Target = (Join-Path $env:USERPROFILE ".codex\skills\edge-codex-bridge"),
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Target)

$Files = @(
  "SKILL.md",
  "README.md",
  "README.zh-CN.md",
  ".gitignore",
  "agents\openai.yaml",
  "references\protocol.md",
  "scripts\client.py",
  "scripts\native_host.py",
  "scripts\install_host.ps1",
  "scripts\uninstall_host.ps1",
  "scripts\host.cmd"
)

function Assert-UnderRoot {
  param(
    [string]$Root,
    [string]$Path
  )

  $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
  $pathFull = [System.IO.Path]::GetFullPath($Path)
  if (-not $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Path escapes root: $pathFull"
  }
}

New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null

foreach ($relative in $Files) {
  $source = Join-Path $SourceRoot $relative
  $target = Join-Path $TargetRoot $relative

  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Source file does not exist: $source"
  }

  Assert-UnderRoot -Root $SourceRoot -Path $source
  Assert-UnderRoot -Root $TargetRoot -Path $target

  $targetDir = Split-Path -Parent $target
  New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  Copy-Item -LiteralPath $source -Destination $target -Force
}

if ($Clean) {
  $allowed = @{}
  foreach ($relative in $Files) {
    $allowed[[System.IO.Path]::GetFullPath((Join-Path $TargetRoot $relative)).ToLowerInvariant()] = $true
  }

  Get-ChildItem -LiteralPath $TargetRoot -Recurse -File -Force |
    Where-Object { -not $allowed.ContainsKey($_.FullName.ToLowerInvariant()) } |
    ForEach-Object {
      Assert-UnderRoot -Root $TargetRoot -Path $_.FullName
      Remove-Item -LiteralPath $_.FullName -Force
    }

  Get-ChildItem -LiteralPath $TargetRoot -Recurse -Directory -Force |
    Sort-Object FullName -Descending |
    ForEach-Object {
      if (-not (Get-ChildItem -LiteralPath $_.FullName -Force)) {
        Assert-UnderRoot -Root $TargetRoot -Path $_.FullName
        Remove-Item -LiteralPath $_.FullName -Force
      }
    }
}

Write-Host "Installed to: $TargetRoot"
