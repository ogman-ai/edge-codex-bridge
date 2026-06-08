---
name: edge-codex-bridge
description: "Use when Codex needs to register, inspect, or operate the local Edge Codex extension through this custom Native Messaging bridge, including tab control, JSON-RPC, and CDP commands. Chrome-compatible, but primarily intended for Edge."
---

# Edge Codex Bridge

## Overview

Use this skill to operate the local Codex browser extension in Microsoft Edge. It registers a custom `com.openai.codexextension` Native Messaging host and converts local script commands into JSON-RPC requests that the extension can handle.

This is a proof-of-concept tool primarily intended for Edge compatibility testing. It is not the official Codex Chrome backend. It uses the official native host name, so uninstall it after testing when you need to restore the default environment.

## Quick Start

1. Confirm the extension is installed. The default Edge extension ID is `hehggadaopoacecdllhhajmbjkdcmajg`.
2. Run `scripts/install_host.ps1` to register the native host.
3. Reload the Codex extension in Edge, or wait for it to reconnect.
4. Run `scripts/client.py status` to check whether the bridge is online.
5. Run `scripts/client.py ping` or `scripts/client.py info` to verify JSON-RPC.
6. Run `scripts/uninstall_host.ps1` when cleanup is needed.

## Common Commands

Run commands from the skill root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_host.ps1
python .\scripts\client.py status
python .\scripts\client.py ping
python .\scripts\client.py info
python .\scripts\client.py user-tabs
python .\scripts\client.py selected-tab
python .\scripts\client.py create-tab
python .\scripts\client.py claim-user-tab --tab-id 123
```

Browser operation commands:

```powershell
python .\scripts\client.py navigate --tab-id 123 https://example.com
python .\scripts\client.py back --tab-id 123
python .\scripts\client.py forward --tab-id 123
python .\scripts\client.py reload --tab-id 123
python .\scripts\client.py title --tab-id 123
python .\scripts\client.py url --tab-id 123
python .\scripts\client.py text --tab-id 123
python .\scripts\client.py eval --tab-id 123 "document.title"
python .\scripts\client.py dom --tab-id 123 --limit 20
python .\scripts\client.py click --tab-id 123 --x 120 --y 240
python .\scripts\client.py double-click --tab-id 123 --x 120 --y 240
python .\scripts\client.py move --tab-id 123 --x 120 --y 240
python .\scripts\client.py scroll --tab-id 123 --x 500 --y 500 --scroll-y 800
python .\scripts\client.py type --tab-id 123 "hello"
python .\scripts\client.py press --tab-id 123 "Ctrl+L"
python .\scripts\client.py drag --tab-id 123 --path "[{\"x\":10,\"y\":10},{\"x\":200,\"y\":200}]"
python .\scripts\client.py wait --tab-id 123 --selector "#app" --timeout 5
python .\scripts\client.py wait-selector --tab-id 123 "#app" --timeout 5
python .\scripts\client.py selector-click --tab-id 123 "button[type=submit]"
python .\scripts\client.py selector-fill --tab-id 123 "input[name=q]" "hello"
python .\scripts\client.py selector-text --tab-id 123 "main"
python .\scripts\client.py selector-attr --tab-id 123 "a" href
python .\scripts\client.py selector-count --tab-id 123 "a"
python .\scripts\client.py name-session "Research"
python .\scripts\client.py viewport --tab-id 123 --width 1280 --height 720
python .\scripts\client.py viewport --tab-id 123 --reset
python .\scripts\client.py console-logs --tab-id 123 --limit 20
python .\scripts\client.py events --limit 20
python .\scripts\client.py downloads --limit 10
python .\scripts\client.py frames --tab-id 123
python .\scripts\client.py page-assets --tab-id 123 --limit 100
python .\scripts\client.py clipboard-write-text --tab-id 123 "hello"
python .\scripts\client.py press --tab-id 123 "Ctrl+V"
python .\scripts\client.py clipboard-read-text --tab-id 123
python .\scripts\client.py screenshot --tab-id 123 --out .\tmp\page.png
python .\scripts\client.py screenshot --tab-id 123 --out .\tmp\full.png --full-page
python .\scripts\client.py close --tab-id 123
```

Minimal low-level control chain:

```powershell
$tab = python .\scripts\client.py create-tab | ConvertFrom-Json
python .\scripts\client.py attach --tab-id $tab.id
python .\scripts\client.py cdp --tab-id $tab.id --method Page.navigate --params "{\"url\":\"https://example.com\"}"
python .\scripts\client.py cdp --tab-id $tab.id --method Runtime.evaluate --params "{\"expression\":\"document.title\",\"returnByValue\":true}"
```

Claim an existing tab before attaching:

```powershell
python .\scripts\client.py user-tabs
python .\scripts\client.py claim-user-tab --tab-id 123
python .\scripts\client.py attach --tab-id 123
```

Send low-level RPC:

```powershell
python .\scripts\client.py rpc getInfo
python .\scripts\client.py rpc getUserTabs --params "{}"
```

Send CDP commands:

```powershell
python .\scripts\client.py cdp --tab-id 123 --method Runtime.evaluate --params "{\"expression\":\"document.title\",\"returnByValue\":true}"
```

Finalize tabs:

```powershell
python .\scripts\client.py finalize --keep 123:handoff
python .\scripts\client.py finalize --keep 123:deliverable
python .\scripts\client.py finalize
```

## Safety Boundaries

- Ask the user for confirmation before reading browsing history, taking over signed-in tabs, downloading, uploading, submitting forms, sending messages, paying, deleting, or modifying real user data.
- Do not expose this bridge to non-local addresses. The scripts only listen on `127.0.0.1`.
- Do not overwrite an existing `com.openai.codexextension` registration without explaining it first. The installer detects conflicting registrations and stops unless `-Force` is used.
- Prefer uninstalling after tests to restore the registry state.
- Clipboard commands read and write the Windows system clipboard, not the page Clipboard API. Use `press Ctrl+V` when the page needs a paste action.

## Resources

- `README.md`: English project overview, install flow, verification flow, and safety notes.
- `README.zh-CN.md`: Chinese project overview.
- `install_skill.ps1`: Installs the public skill files into a local Codex skill directory.
- `scripts/install_host.ps1`: Registers the Edge Native Messaging host. The script also keeps Chrome compatibility options.
- `scripts/uninstall_host.ps1`: Removes the native host registration created by this skill.
- `scripts/native_host.py`: Native Messaging host launched by the browser extension. It also exposes the local HTTP control interface.
- `scripts/client.py`: Command-line client.
- `scripts/host.cmd`: Windows native host launcher.
- `references/protocol.md`: Protocol, methods, and troubleshooting reference.
- `agents/openai.yaml`: Codex app UI metadata and invocation policy.
