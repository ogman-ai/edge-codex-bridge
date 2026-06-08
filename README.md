# Edge Codex Bridge

Edge Codex Bridge is a local Codex skill for operating the Codex browser extension in Microsoft Edge through a custom Native Messaging host.

It is primarily intended for Edge compatibility work. The scripts keep Chrome-compatible registration options because Edge and Chrome share Chromium extension APIs, but this project is not the official Codex Chrome backend.

## What It Does

- Registers a local Native Messaging host named `com.openai.codexextension`.
- Lets the Codex extension start `scripts/native_host.py` through `scripts/host.cmd`.
- Exposes a localhost-only control bridge for `scripts/client.py`.
- Sends JSON-RPC requests and Chrome DevTools Protocol commands through the extension.
- Supports tab listing, tab creation, navigation, DOM inspection, input, screenshots, console events, downloads events, and cleanup.

## Requirements

- Windows
- Python available as `python`
- Microsoft Edge with the Codex browser extension installed
- PowerShell for host registration scripts

Default Edge extension ID:

```text
hehggadaopoacecdllhhajmbjkdcmajg
```

You can pass a different extension ID to `scripts/install_host.ps1` if needed.

## Install

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_host.ps1
```

Then reload the Codex extension in Edge, or wait for it to reconnect.

The installer writes `scripts/native_host_manifest.json` and registers it under the current user's Edge Native Messaging host registry key.

## Verify

```powershell
python .\scripts\client.py status
python .\scripts\client.py ping
python .\scripts\client.py info
```

If `status` cannot find the state file, the browser extension has not started the native host yet. Reload the extension and try again.

## Basic Usage

Create and inspect a tab:

```powershell
$tab = python .\scripts\client.py create-tab | ConvertFrom-Json
python .\scripts\client.py attach --tab-id $tab.id
python .\scripts\client.py navigate --tab-id $tab.id https://example.com
python .\scripts\client.py title --tab-id $tab.id
python .\scripts\client.py text --tab-id $tab.id
```

Send a raw CDP command:

```powershell
python .\scripts\client.py cdp --tab-id $tab.id --method Runtime.evaluate --params "{\"expression\":\"document.title\",\"returnByValue\":true}"
```

Capture a screenshot:

```powershell
python .\scripts\client.py screenshot --tab-id $tab.id --out .\tmp\page.png
```

Finalize browser tabs for the current bridge session:

```powershell
python .\scripts\client.py finalize
```

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_host.ps1
```

The uninstall script only removes the registration if it points to this skill's generated manifest. Use `-Force` only when you intentionally want to remove a different existing registration.

## Local Skill Install

To copy this repository's public skill files into your local Codex skill directory:

```powershell
.\install_skill.ps1
```

The default target is:

```text
%USERPROFILE%\.codex\skills\edge-codex-bridge
```

Use `-Target` to choose a different location, and `-Clean` to remove files in the target that are not part of this public skill package.

## Safety Notes

- The bridge listens only on `127.0.0.1`.
- The local HTTP control bridge uses a temporary token stored in the user's temp directory.
- Reading browser history, taking over signed-in tabs, downloading, uploading, submitting forms, sending messages, paying, deleting, or modifying real user data should require explicit user confirmation.
- This project uses the native host name `com.openai.codexextension`; uninstall it after testing if you need to restore the default environment.
- Clipboard commands read and write the Windows system clipboard.

## Project Structure

```text
SKILL.md
README.md
README.zh-CN.md
agents/openai.yaml
references/protocol.md
scripts/client.py
scripts/native_host.py
scripts/host.cmd
scripts/install_host.ps1
scripts/uninstall_host.ps1
install_skill.ps1
```

See `references/protocol.md` for JSON-RPC, CDP, and troubleshooting details.
