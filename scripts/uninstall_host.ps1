param(
  [ValidateSet("Edge", "Chrome", "Both")]
  [string]$Browser = "Edge",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManifestPath = Join-Path $ScriptDir "native_host_manifest.json"
$HostName = "com.openai.codexextension"

function Remove-NativeHost {
  param([string]$Root)

  $keyPath = Join-Path $Root $HostName
  if (-not (Test-Path $keyPath)) {
    Write-Host "Not found: $keyPath"
    return
  }

  $existing = (Get-Item -LiteralPath $keyPath).GetValue("")
  if ($existing -and $existing -ne $ManifestPath -and -not $Force) {
    throw "$keyPath points to $existing, not the manifest created by this skill. Use -Force only if you intend to remove it."
  }

  Remove-Item -LiteralPath $keyPath -Recurse -Force
  Write-Host "Removed $keyPath"
}

if ($Browser -eq "Edge" -or $Browser -eq "Both") {
  Remove-NativeHost "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts"
}

if ($Browser -eq "Chrome" -or $Browser -eq "Both") {
  Remove-NativeHost "HKCU:\Software\Google\Chrome\NativeMessagingHosts"
}
