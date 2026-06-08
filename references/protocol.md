# Edge Codex Bridge Protocol Reference

## Native Messaging

The extension connects to the native host with `chrome.runtime.connectNative("com.openai.codexextension")`. Edge extensions also use Chromium's `chrome.*` extension API namespace.

Messages use the Chromium Native Messaging framing format:

```text
4-byte little-endian uint32 length
UTF-8 JSON payload
```

This bridge uses `native_host.py` to communicate with the extension over stdin/stdout. stderr is reserved for logs.

## JSON-RPC

The extension and native host exchange JSON-RPC 2.0-style messages.

Request:

```json
{"jsonrpc":"2.0","id":1,"method":"getInfo","params":{}}
```

Successful response:

```json
{"jsonrpc":"2.0","id":1,"result":{"name":"Edge","type":"extension"}}
```

Error response:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":1,"message":"..."}}
```

Notification:

```json
{"jsonrpc":"2.0","method":"onCDPEvent","params":{}}
```

## Common Extension Methods

- `ping`: Heartbeat. Does not require session parameters.
- `getInfo`: Returns extension information. Does not require session parameters.
- `getUserTabs`: Lists user browser tabs. Requires `session_id` and `turn_id`.
- `createTab`: Creates a new agent-managed tab. Requires `session_id` and `turn_id`.
- `claimUserTab`: Claims an existing tab. Requires `session_id`, `turn_id`, and `tabId`.
- `attach`: Attaches with `chrome.debugger.attach`. Requires `session_id`, `turn_id`, and `tabId`.
- `detach`: Releases debugger attachment. Requires `session_id`, `turn_id`, and `tabId`.
- `executeCdp`: Executes a CDP command. Requires `session_id`, `turn_id`, `target`, `method`, and `commandParams`.
- `nameSession`: Names the automation session. Requires `session_id`, `turn_id`, and `name`.

## High-Level Client Commands

- `navigate --tab-id <id> <url>`: Wraps `Page.navigate`.
- `back --tab-id <id>`: Uses `Page.getNavigationHistory` and `Page.navigateToHistoryEntry`.
- `forward --tab-id <id>`: Uses `Page.getNavigationHistory` and `Page.navigateToHistoryEntry`.
- `reload --tab-id <id>`: Wraps `Page.reload`.
- `title --tab-id <id>`: Reads `document.title`.
- `url --tab-id <id>`: Reads `location.href`.
- `text --tab-id <id>`: Reads visible page body text.
- `dom --tab-id <id> --limit <n>`: Reads simplified visible DOM nodes with `id`, `tag`, `role`, `text`, `selector`, and `rect`.
- `eval --tab-id <id> <expression>`: Wraps `Runtime.evaluate` with `returnByValue=true` by default.
- `click --tab-id <id> --x <n> --y <n>`: Sends a coordinate click.
- `double-click --tab-id <id> --x <n> --y <n>`: Sends a coordinate double click.
- `move --tab-id <id> --x <n> --y <n>`: Moves the mouse.
- `scroll --tab-id <id> --x <n> --y <n> --scroll-y <n>`: Scrolls from a coordinate.
- `type --tab-id <id> <text>`: Inserts text into the current focus.
- `press --tab-id <id> <keys>`: Presses a key or key combination, such as `Enter`, `Ctrl+L`, or `Ctrl+A`.
- `drag --tab-id <id> --path <json>`: Drags along a coordinate path.
- `wait --ms <n>`: Waits for a fixed number of milliseconds.
- `wait --tab-id <id> --selector <selector>`: Waits for a selector.
- `wait --tab-id <id> --url-contains <text>`: Waits for the URL to contain text.
- `wait --tab-id <id> --title-contains <text>`: Waits for the title to contain text.
- `selector-click --tab-id <id> <selector>`: Scrolls the element into view, reads its rectangle, and clicks its center.
- `selector-fill --tab-id <id> <selector> <text>`: Sets an input value and dispatches `input` and `change` events.
- `selector-text --tab-id <id> <selector>`: Reads the first matching element's text.
- `selector-attr --tab-id <id> <selector> <name>`: Reads an attribute from the first matching element.
- `selector-count --tab-id <id> <selector>`: Counts matching elements.
- `wait-selector --tab-id <id> <selector>`: Waits for a selector.
- `selected-tab`: Returns the first tab from `getUserTabs`, usually the most recent or focused tab returned by the extension. It is not guaranteed to be the current automation tab.
- `claim-user-tab --tab-id <id>`: Calls `claimUserTab` so an existing user tab becomes part of the current bridge session.
- `name-session <name>`: Calls extension `nameSession`, usually changing the Codex tab group name.
- `viewport --tab-id <id> --width <n> --height <n>`: Wraps `Emulation.setDeviceMetricsOverride`.
- `viewport --tab-id <id> --reset`: Wraps `Emulation.clearDeviceMetricsOverride`.
- `console-logs --tab-id <id>`: Enables `Runtime.enable` and reads locally recorded `Runtime.consoleAPICalled` events.
- `console-logs --clear`: Clears the local event cache.
- `events --limit <n>`: Reads recent local host events.
- `events --method <name>`: Filters events by method, such as `onCDPEvent`.
- `events --clear`: Clears the local event cache.
- `downloads --limit <n>`: Reads recent download-related events, primarily extension `onDownloadChange` notifications.
- `downloads --clear`: Clears the event cache.
- `frames --tab-id <id>`: Wraps `Page.getFrameTree` and returns a flattened frame list.
- `page-assets --tab-id <id>`: Reads page assets by merging Performance Resource Timing with DOM `img/script/link/source/video/audio` references.
- `clipboard-write-text --tab-id <id> <text>`: Writes the Windows system clipboard. `--tab-id` is accepted for compatibility and does not use the page Clipboard API.
- `clipboard-read-text --tab-id <id>`: Reads the Windows system clipboard. `--tab-id` is accepted for compatibility and does not use the page Clipboard API.
- `screenshot --tab-id <id> --out <path>`: Wraps `Page.captureScreenshot` and saves a PNG file.
- `screenshot --full-page`: Reads `Page.getLayoutMetrics` and captures the full `cssContentSize`.
- `close --tab-id <id>`: Calls `finalizeTabs`, keeping the specified tab as `handoff` and letting the extension finalize other session tabs.
- `finalize --keep <tabId:status>`: Calls `finalizeTabs` directly. `status` must be `handoff` or `deliverable`.

## Troubleshooting

- `status` cannot find the state file: the extension has not started the native host yet. Reload the extension.
- `Native host has exited`: check whether `host.cmd` can find `python`.
- `already exists`: a native host with the same name is already registered. Do not use `-Force` unless you intentionally want to overwrite it.
- `Debugger unattached`: run `attach` for the target tab first.
- `Tab ... is not part of browser session`: create the tab with `createTab`, or claim an existing tab with `claimUserTab`.
