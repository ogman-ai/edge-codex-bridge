param(
  [ValidateSet("Edge", "Chrome", "Both")]
  [string]$Browser = "Edge",
  [string]$ExtensionId = "hehggadaopoacecdllhhajmbjkdcmajg",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HostCmd = Join-Path $ScriptDir "host.cmd"
$ManifestPath = Join-Path $ScriptDir "native_host_manifest.json"
$HostName = "com.openai.codexextension"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "python was not found. Make sure the python command is available."
}

$manifest = [ordered]@{
  name = $HostName;
  description = "Local Edge Codex bridge native host";
  path = $HostCmd;
  type = "stdio";
  allowed_origins = @("chrome-extension://$ExtensionId/");
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

function Set-NativeHost {
  param([string]$Root)

  $keyPath = Join-Path $Root $HostName
  if (Test-Path $keyPath) {
    $existing = (Get-Item -LiteralPath $keyPath).GetValue("")
    if ($existing -and $existing -ne $ManifestPath -and -not $Force) {
      throw "$keyPath already exists and points to $existing. Use -Force only if you intend to overwrite it."
    }
  }

  New-Item -Path $keyPath -Force | Out-Null
  $relativeKeyPath = $keyPath -replace '^HKCU:\\', ''
  $writableKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($relativeKeyPath, $true)
  if ($null -eq $writableKey) {
    throw "Failed to open writable registry key: $keyPath"
  }
  try {
    $writableKey.SetValue("", $ManifestPath, [Microsoft.Win32.RegistryValueKind]::String)
  }
  finally {
    $writableKey.Close()
  }
  Write-Host "Registered $keyPath => $ManifestPath"
}

if ($Browser -eq "Edge" -or $Browser -eq "Both") {
  Set-NativeHost "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts"
}

if ($Browser -eq "Chrome" -or $Browser -eq "Both") {
  Set-NativeHost "HKCU:\Software\Google\Chrome\NativeMessagingHosts"
}

Write-Host "Done. Reload the Codex extension, or wait for it to reconnect."
