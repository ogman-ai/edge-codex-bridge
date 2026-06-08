import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


STATE_PATH = os.path.join(tempfile.gettempdir(), "edge-codex-bridge-state.json")
DEFAULT_SESSION_ID = "manual-bridge"
DEFAULT_TURN_ID = "manual-turn"


def load_state():
    with open(STATE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def rpc(method, params=None, timeout=10):
    state = load_state()
    url = f"http://{state['host']}:{state['port']}/rpc"
    body = json.dumps(
        {"method": method, "params": params or {}, "timeout": timeout}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Edge-Codex-Bridge-Token": state["token"],
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout + 2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
    if not payload.get("ok"):
        message = payload.get("error", "request failed")
        if "is not part of browser session" in message:
            tab_id = (params or {}).get("tabId")
            if tab_id is None:
                tab_id = ((params or {}).get("target") or {}).get("tabId")
            if tab_id is not None:
                message += (
                    "\nRun these commands first:\n"
                    f"python .\\scripts\\client.py claim-user-tab --tab-id {tab_id}\n"
                    f"python .\\scripts\\client.py attach --tab-id {tab_id}"
                )
        raise RuntimeError(message)
    return payload.get("result")


def health():
    state = load_state()
    url = f"http://{state['host']}:{state['port']}/health"
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def bridge_get(path, query=None, timeout=3):
    state = load_state()
    qs = urllib.parse.urlencode(query or {})
    suffix = f"?{qs}" if qs else ""
    url = f"http://{state['host']}:{state['port']}{path}{suffix}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"X-Edge-Codex-Bridge-Token": state["token"]},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "request failed"))
    return payload


def bridge_post(path, payload=None, timeout=3):
    state = load_state()
    url = f"http://{state['host']}:{state['port']}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Edge-Codex-Bridge-Token": state["token"],
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "request failed"))
    return result


def session_params(args):
    return {"session_id": args.session_id, "turn_id": args.turn_id}


def cdp_request(args, tab_id, method, params=None, timeout=10):
    payload = {
        **session_params(args),
        "target": {"tabId": tab_id},
        "method": method,
        "commandParams": params or {},
        "timeoutMs": int(timeout * 1000),
    }
    return rpc("executeCdp", payload, timeout=timeout + 2)


def cdp_value(args, tab_id, expression, timeout=10):
    result = cdp_request(
        args,
        tab_id,
        "Runtime.evaluate",
        params={"expression": expression, "returnByValue": True, "awaitPromise": True},
        timeout=timeout,
    )
    return ((result.get("result") or {}).get("value"))


def mouse_event(args, tab_id, event_type, x, y, **extra):
    params = {"type": event_type, "x": x, "y": y, **extra}
    return cdp_request(args, tab_id, "Input.dispatchMouseEvent", params=params)


def button_name(button):
    return {1: "left", 2: "middle", 3: "right"}.get(button, "left")


KEY_ALIASES = {
    "CTRL": "Control",
    "CONTROL": "Control",
    "CMD": "Meta",
    "COMMAND": "Meta",
    "WIN": "Meta",
    "WINDOWS": "Meta",
    "OPTION": "Alt",
    "ESC": "Escape",
    "RETURN": "Enter",
    "DEL": "Delete",
    "PGUP": "PageUp",
    "PGDN": "PageDown",
    "SPACE": " ",
}


KEY_CODES = {
    "Backspace": 8,
    "Tab": 9,
    "Enter": 13,
    "Shift": 16,
    "Control": 17,
    "Alt": 18,
    "Pause": 19,
    "CapsLock": 20,
    "Escape": 27,
    " ": 32,
    "PageUp": 33,
    "PageDown": 34,
    "End": 35,
    "Home": 36,
    "ArrowLeft": 37,
    "ArrowUp": 38,
    "ArrowRight": 39,
    "ArrowDown": 40,
    "Insert": 45,
    "Delete": 46,
    "Meta": 91,
}


for index in range(1, 13):
    KEY_CODES[f"F{index}"] = 111 + index


def normalize_key(raw_key):
    key = raw_key.strip()
    if not key:
        raise RuntimeError("empty key")
    upper = key.upper()
    if upper in KEY_ALIASES:
        return KEY_ALIASES[upper]
    arrow = {
        "LEFT": "ArrowLeft",
        "RIGHT": "ArrowRight",
        "UP": "ArrowUp",
        "DOWN": "ArrowDown",
    }.get(upper)
    if arrow:
        return arrow
    if len(key) == 1:
        return key
    return key[0].upper() + key[1:]


def key_code(key):
    if key in KEY_CODES:
        return KEY_CODES[key]
    if len(key) == 1:
        return ord(key.upper())
    return 0


def key_code_name(key):
    if len(key) == 1 and key.isalpha():
        return "Key" + key.upper()
    if len(key) == 1 and key.isdigit():
        return "Digit" + key
    names = {
        " ": "Space",
        "Control": "ControlLeft",
        "Shift": "ShiftLeft",
        "Alt": "AltLeft",
        "Meta": "MetaLeft",
        "Escape": "Escape",
        "Enter": "Enter",
        "Tab": "Tab",
        "Backspace": "Backspace",
        "Delete": "Delete",
        "ArrowLeft": "ArrowLeft",
        "ArrowRight": "ArrowRight",
        "ArrowUp": "ArrowUp",
        "ArrowDown": "ArrowDown",
        "Home": "Home",
        "End": "End",
        "PageUp": "PageUp",
        "PageDown": "PageDown",
    }
    return names.get(key, key)


def modifier_mask(keys):
    mask = 0
    if "Alt" in keys:
        mask |= 1
    if "Control" in keys:
        mask |= 2
    if "Meta" in keys:
        mask |= 4
    if "Shift" in keys:
        mask |= 8
    return mask


def dispatch_key(args, tab_id, key, event_type, modifiers):
    params = {
        "type": event_type,
        "key": key,
        "code": key_code_name(key),
        "windowsVirtualKeyCode": key_code(key),
        "nativeVirtualKeyCode": key_code(key),
        "modifiers": modifier_mask(modifiers),
    }
    if len(key) == 1 and event_type == "keyDown" and not modifiers:
        params["text"] = key
        params["unmodifiedText"] = key
    return cdp_request(args, tab_id, "Input.dispatchKeyEvent", params=params)


def parse_keys(value):
    if "," in value:
        return [normalize_key(part) for part in value.split(",")]
    return [normalize_key(part) for part in value.split("+")]


def selector_exists_expression(selector):
    return "Boolean(document.querySelector(" + json.dumps(selector) + "))"


def selector_rect_expression(selector):
    return (
        "(() => {"
        "const el = document.querySelector("
        + json.dumps(selector)
        + ");"
        "if (!el) return null;"
        "el.scrollIntoView({block: 'center', inline: 'center'});"
        "const rect = el.getBoundingClientRect();"
        "return {"
        "x: rect.x, y: rect.y, width: rect.width, height: rect.height,"
        "top: rect.top, left: rect.left, right: rect.right, bottom: rect.bottom"
        "};"
        "})()"
    )


def selector_text_expression(selector):
    return (
        "(() => {"
        "const el = document.querySelector("
        + json.dumps(selector)
        + ");"
        "if (!el) return null;"
        "if ('innerText' in el) return el.innerText;"
        "return el.textContent;"
        "})()"
    )


def selector_attr_expression(selector, name):
    return (
        "(() => {"
        "const el = document.querySelector("
        + json.dumps(selector)
        + ");"
        "return el ? el.getAttribute("
        + json.dumps(name)
        + ") : null;"
        "})()"
    )


def selector_fill_expression(selector, text):
    return (
        "(() => {"
        "const el = document.querySelector("
        + json.dumps(selector)
        + ");"
        "if (!el) return false;"
        "el.focus();"
        "if ('value' in el) {"
        "el.value = "
        + json.dumps(text)
        + ";"
        "} else {"
        "el.textContent = "
        + json.dumps(text)
        + ";"
        "}"
        "el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: "
        + json.dumps(text)
        + "}));"
        "el.dispatchEvent(new Event('change', {bubbles: true}));"
        "return true;"
        "})()"
    )


def visible_dom_expression(limit):
    return (
        "(() => {"
        "const cssEscape = globalThis.CSS && CSS.escape ? CSS.escape : (value) => String(value).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');"
        "const selectorFor = (el) => {"
        "if (el.id) return '#' + cssEscape(el.id);"
        "const attr = ['name','aria-label','placeholder','data-testid'].find((name) => el.getAttribute(name));"
        "if (attr) return el.tagName.toLowerCase() + '[' + attr + '=' + JSON.stringify(el.getAttribute(attr)) + ']';"
        "return el.tagName.toLowerCase();"
        "};"
        "const candidates = Array.from(document.querySelectorAll('a,button,input,textarea,select,summary,label,[role],[onclick],[tabindex]'));"
        "return candidates.map((el, index) => {"
        "const rect = el.getBoundingClientRect();"
        "const style = getComputedStyle(el);"
        "const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';"
        "if (!visible) return null;"
        "const text = ((el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.textContent || '') + '').trim().replace(/\\s+/g, ' ').slice(0, 160);"
        "return {id: String(index + 1), tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), text, selector: selectorFor(el), rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}};"
        "}).filter(Boolean).slice(0, "
        + str(limit)
        + ");"
        "})()"
    )


def page_assets_expression(limit):
    return (
        "(() => {"
        "const byUrl = new Map();"
        "const add = (asset) => {"
        "if (!asset || !asset.url) return;"
        "const previous = byUrl.get(asset.url) || {};"
        "byUrl.set(asset.url, {...previous, ...asset});"
        "};"
        "performance.getEntriesByType('resource').forEach((entry) => add({"
        "url: entry.name, type: entry.initiatorType || 'resource', duration: entry.duration,"
        "transferSize: entry.transferSize, decodedBodySize: entry.decodedBodySize"
        "}));"
        "document.querySelectorAll('img[src],script[src],link[href],source[src],video[src],audio[src]').forEach((el) => add({"
        "url: el.currentSrc || el.src || el.href, tag: el.tagName.toLowerCase(),"
        "rel: el.rel || null, type: el.as || el.rel || el.tagName.toLowerCase()"
        "}));"
        "return Array.from(byUrl.values()).slice(0, "
        + str(limit)
        + ");"
        "})()"
    )


def flatten_frame_tree(node):
    frame = node.get("frame") or {}
    result = [
        {
            "id": frame.get("id"),
            "parentId": frame.get("parentId"),
            "name": frame.get("name"),
            "url": frame.get("url"),
            "securityOrigin": frame.get("securityOrigin"),
            "mimeType": frame.get("mimeType"),
        }
    ]
    for child in node.get("childFrames") or []:
        result.extend(flatten_frame_tree(child))
    return result


def recent_events(limit, method=None):
    query = {"limit": limit}
    if method:
        query["method"] = method
    return bridge_get("/events", query=query).get("events", [])


def tab_matches_event(tab_id, event):
    params = event.get("params") or {}
    source = params.get("source") or {}
    return source.get("tabId") in {None, tab_id}


def os_clipboard_read():
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def os_clipboard_write(text):
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
        input=text,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def wait_until(args, predicate):
    deadline = time.time() + args.timeout
    while time.time() <= deadline:
        if predicate():
            return True
        time.sleep(0.25)
    return False


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parse_json_object(value):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return parsed


def parse_json_array(value):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("value must be a JSON array")
    return parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--turn-id", default=DEFAULT_TURN_ID)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("ping")
    sub.add_parser("info")
    sub.add_parser("user-tabs")
    sub.add_parser("selected-tab")
    sub.add_parser("create-tab")

    rpc_parser = sub.add_parser("rpc")
    rpc_parser.add_argument("method")
    rpc_parser.add_argument("--params", type=parse_json_object, default={})
    rpc_parser.add_argument("--timeout", type=float, default=10)

    attach_parser = sub.add_parser("attach")
    attach_parser.add_argument("--tab-id", type=int, required=True)

    claim_user_tab_parser = sub.add_parser("claim-user-tab")
    claim_user_tab_parser.add_argument("--tab-id", type=int, required=True)

    cdp_parser = sub.add_parser("cdp")
    cdp_parser.add_argument("--tab-id", type=int, required=True)
    cdp_parser.add_argument("--method", required=True)
    cdp_parser.add_argument("--params", type=parse_json_object, default={})
    cdp_parser.add_argument("--timeout", type=float, default=10)

    nav_parser = sub.add_parser("navigate")
    nav_parser.add_argument("--tab-id", type=int, required=True)
    nav_parser.add_argument("url")
    nav_parser.add_argument("--timeout", type=float, default=10)

    back_parser = sub.add_parser("back")
    back_parser.add_argument("--tab-id", type=int, required=True)
    back_parser.add_argument("--timeout", type=float, default=10)

    forward_parser = sub.add_parser("forward")
    forward_parser.add_argument("--tab-id", type=int, required=True)
    forward_parser.add_argument("--timeout", type=float, default=10)

    reload_parser = sub.add_parser("reload")
    reload_parser.add_argument("--tab-id", type=int, required=True)
    reload_parser.add_argument("--ignore-cache", action="store_true")
    reload_parser.add_argument("--timeout", type=float, default=10)

    title_parser = sub.add_parser("title")
    title_parser.add_argument("--tab-id", type=int, required=True)
    title_parser.add_argument("--timeout", type=float, default=10)

    url_parser = sub.add_parser("url")
    url_parser.add_argument("--tab-id", type=int, required=True)
    url_parser.add_argument("--timeout", type=float, default=10)

    text_parser = sub.add_parser("text")
    text_parser.add_argument("--tab-id", type=int, required=True)
    text_parser.add_argument("--timeout", type=float, default=10)

    dom_parser = sub.add_parser("dom")
    dom_parser.add_argument("--tab-id", type=int, required=True)
    dom_parser.add_argument("--limit", type=int, default=80)
    dom_parser.add_argument("--timeout", type=float, default=10)

    eval_parser = sub.add_parser("eval")
    eval_parser.add_argument("--tab-id", type=int, required=True)
    eval_parser.add_argument("expression")
    eval_parser.add_argument("--timeout", type=float, default=10)

    click_parser = sub.add_parser("click")
    click_parser.add_argument("--tab-id", type=int, required=True)
    click_parser.add_argument("--x", type=float, required=True)
    click_parser.add_argument("--y", type=float, required=True)
    click_parser.add_argument("--button", type=int, default=1)

    double_click_parser = sub.add_parser("double-click")
    double_click_parser.add_argument("--tab-id", type=int, required=True)
    double_click_parser.add_argument("--x", type=float, required=True)
    double_click_parser.add_argument("--y", type=float, required=True)

    move_parser = sub.add_parser("move")
    move_parser.add_argument("--tab-id", type=int, required=True)
    move_parser.add_argument("--x", type=float, required=True)
    move_parser.add_argument("--y", type=float, required=True)

    scroll_parser = sub.add_parser("scroll")
    scroll_parser.add_argument("--tab-id", type=int, required=True)
    scroll_parser.add_argument("--x", type=float, required=True)
    scroll_parser.add_argument("--y", type=float, required=True)
    scroll_parser.add_argument("--scroll-x", type=float, default=0)
    scroll_parser.add_argument("--scroll-y", type=float, default=0)

    type_parser = sub.add_parser("type")
    type_parser.add_argument("--tab-id", type=int, required=True)
    type_parser.add_argument("text")

    press_parser = sub.add_parser("press")
    press_parser.add_argument("--tab-id", type=int, required=True)
    press_parser.add_argument("keys", help="Example: Enter, Ctrl+L, Ctrl+A")

    drag_parser = sub.add_parser("drag")
    drag_parser.add_argument("--tab-id", type=int, required=True)
    drag_parser.add_argument(
        "--path",
        type=parse_json_array,
        required=True,
        help='JSON array, e.g. [{"x":10,"y":10},{"x":100,"y":100}]',
    )

    wait_parser = sub.add_parser("wait")
    wait_parser.add_argument("--tab-id", type=int)
    wait_parser.add_argument("--ms", type=int, default=0)
    wait_parser.add_argument("--url-contains")
    wait_parser.add_argument("--title-contains")
    wait_parser.add_argument("--selector")
    wait_parser.add_argument("--timeout", type=float, default=10)

    selector_click_parser = sub.add_parser("selector-click")
    selector_click_parser.add_argument("--tab-id", type=int, required=True)
    selector_click_parser.add_argument("selector")
    selector_click_parser.add_argument("--timeout", type=float, default=10)

    selector_fill_parser = sub.add_parser("selector-fill")
    selector_fill_parser.add_argument("--tab-id", type=int, required=True)
    selector_fill_parser.add_argument("selector")
    selector_fill_parser.add_argument("text")
    selector_fill_parser.add_argument("--timeout", type=float, default=10)

    selector_text_parser = sub.add_parser("selector-text")
    selector_text_parser.add_argument("--tab-id", type=int, required=True)
    selector_text_parser.add_argument("selector")
    selector_text_parser.add_argument("--timeout", type=float, default=10)

    selector_attr_parser = sub.add_parser("selector-attr")
    selector_attr_parser.add_argument("--tab-id", type=int, required=True)
    selector_attr_parser.add_argument("selector")
    selector_attr_parser.add_argument("name")
    selector_attr_parser.add_argument("--timeout", type=float, default=10)

    selector_count_parser = sub.add_parser("selector-count")
    selector_count_parser.add_argument("--tab-id", type=int, required=True)
    selector_count_parser.add_argument("selector")
    selector_count_parser.add_argument("--timeout", type=float, default=10)

    wait_selector_parser = sub.add_parser("wait-selector")
    wait_selector_parser.add_argument("--tab-id", type=int, required=True)
    wait_selector_parser.add_argument("selector")
    wait_selector_parser.add_argument("--timeout", type=float, default=10)

    name_session_parser = sub.add_parser("name-session")
    name_session_parser.add_argument("name")

    viewport_parser = sub.add_parser("viewport")
    viewport_parser.add_argument("--tab-id", type=int, required=True)
    viewport_parser.add_argument("--width", type=int)
    viewport_parser.add_argument("--height", type=int)
    viewport_parser.add_argument("--device-scale-factor", type=float, default=1)
    viewport_parser.add_argument("--mobile", action="store_true")
    viewport_parser.add_argument("--reset", action="store_true")
    viewport_parser.add_argument("--timeout", type=float, default=10)

    clipboard_read_parser = sub.add_parser("clipboard-read-text")
    clipboard_read_parser.add_argument("--tab-id", type=int, required=True)
    clipboard_read_parser.add_argument("--timeout", type=float, default=10)

    clipboard_write_parser = sub.add_parser("clipboard-write-text")
    clipboard_write_parser.add_argument("--tab-id", type=int, required=True)
    clipboard_write_parser.add_argument("text")
    clipboard_write_parser.add_argument("--timeout", type=float, default=10)

    console_logs_parser = sub.add_parser("console-logs")
    console_logs_parser.add_argument("--tab-id", type=int, required=True)
    console_logs_parser.add_argument("--limit", type=int, default=50)
    console_logs_parser.add_argument("--clear", action="store_true")
    console_logs_parser.add_argument("--timeout", type=float, default=10)

    events_parser = sub.add_parser("events")
    events_parser.add_argument("--limit", type=int, default=50)
    events_parser.add_argument("--method")
    events_parser.add_argument("--clear", action="store_true")

    downloads_parser = sub.add_parser("downloads")
    downloads_parser.add_argument("--limit", type=int, default=20)
    downloads_parser.add_argument("--clear", action="store_true")

    frames_parser = sub.add_parser("frames")
    frames_parser.add_argument("--tab-id", type=int, required=True)
    frames_parser.add_argument("--timeout", type=float, default=10)

    page_assets_parser = sub.add_parser("page-assets")
    page_assets_parser.add_argument("--tab-id", type=int, required=True)
    page_assets_parser.add_argument("--limit", type=int, default=200)
    page_assets_parser.add_argument("--timeout", type=float, default=10)

    screenshot_parser = sub.add_parser("screenshot")
    screenshot_parser.add_argument("--tab-id", type=int, required=True)
    screenshot_parser.add_argument("--out", required=True)
    screenshot_parser.add_argument("--full-page", action="store_true")
    screenshot_parser.add_argument("--timeout", type=float, default=10)

    close_parser = sub.add_parser("close")
    close_parser.add_argument("--tab-id", type=int, action="append", required=True)

    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument(
        "--keep",
        action="append",
        default=[],
        help="tabId:status where status is handoff or deliverable",
    )

    args = parser.parse_args()

    if args.command == "status":
        print_json(health())
    elif args.command == "ping":
        print_json(rpc("ping"))
    elif args.command == "info":
        print_json(rpc("getInfo"))
    elif args.command == "user-tabs":
        print_json(rpc("getUserTabs", session_params(args)))
    elif args.command == "selected-tab":
        tabs = rpc("getUserTabs", session_params(args))
        print_json(tabs[0] if tabs else None)
    elif args.command == "create-tab":
        print_json(rpc("createTab", session_params(args)))
    elif args.command == "rpc":
        params = {**session_params(args), **args.params}
        print_json(rpc(args.method, params, timeout=args.timeout))
    elif args.command == "attach":
        params = {**session_params(args), "tabId": args.tab_id}
        print_json(rpc("attach", params))
    elif args.command == "claim-user-tab":
        params = {**session_params(args), "tabId": args.tab_id}
        print_json(rpc("claimUserTab", params))
    elif args.command == "cdp":
        print_json(
            cdp_request(
                args,
                args.tab_id,
                args.method,
                params=args.params,
                timeout=args.timeout,
            )
        )
    elif args.command == "navigate":
        print_json(
            cdp_request(
                args,
                args.tab_id,
                "Page.navigate",
                params={"url": args.url},
                timeout=args.timeout,
            )
        )
    elif args.command in {"back", "forward"}:
        history = cdp_request(
            args,
            args.tab_id,
            "Page.getNavigationHistory",
            timeout=args.timeout,
        )
        entries = history.get("entries") or []
        current = int(history.get("currentIndex", 0))
        next_index = current - 1 if args.command == "back" else current + 1
        if next_index < 0 or next_index >= len(entries):
            raise RuntimeError(f"cannot go {args.command}; no history entry")
        print_json(
            cdp_request(
                args,
                args.tab_id,
                "Page.navigateToHistoryEntry",
                params={"entryId": entries[next_index]["id"]},
                timeout=args.timeout,
            )
        )
    elif args.command == "reload":
        print_json(
            cdp_request(
                args,
                args.tab_id,
                "Page.reload",
                params={"ignoreCache": bool(args.ignore_cache)},
                timeout=args.timeout,
            )
        )
    elif args.command == "title":
        print_json(
            {
                "title": cdp_value(
                    args, args.tab_id, "document.title", timeout=args.timeout
                )
            }
        )
    elif args.command == "url":
        print_json(
            {
                "url": cdp_value(
                    args, args.tab_id, "location.href", timeout=args.timeout
                )
            }
        )
    elif args.command == "text":
        print_json(
            {
                "text": cdp_value(
                    args,
                    args.tab_id,
                    "document.body ? document.body.innerText : document.documentElement.innerText",
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "dom":
        print_json(
            {
                "nodes": cdp_value(
                    args,
                    args.tab_id,
                    visible_dom_expression(args.limit),
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "eval":
        print_json(
            cdp_request(
                args,
                args.tab_id,
                "Runtime.evaluate",
                params={
                    "expression": args.expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                timeout=args.timeout,
            )
        )
    elif args.command == "click":
        button = button_name(args.button)
        mouse_event(args, args.tab_id, "mouseMoved", args.x, args.y)
        mouse_event(
            args,
            args.tab_id,
            "mousePressed",
            args.x,
            args.y,
            button=button,
            clickCount=1,
        )
        result = mouse_event(
            args,
            args.tab_id,
            "mouseReleased",
            args.x,
            args.y,
            button=button,
            clickCount=1,
        )
        print_json(result)
    elif args.command == "double-click":
        mouse_event(args, args.tab_id, "mouseMoved", args.x, args.y)
        for count in (1, 2):
            mouse_event(
                args,
                args.tab_id,
                "mousePressed",
                args.x,
                args.y,
                button="left",
                clickCount=count,
            )
            result = mouse_event(
                args,
                args.tab_id,
                "mouseReleased",
                args.x,
                args.y,
                button="left",
                clickCount=count,
            )
        print_json(result)
    elif args.command == "move":
        print_json(mouse_event(args, args.tab_id, "mouseMoved", args.x, args.y))
    elif args.command == "scroll":
        print_json(
            mouse_event(
                args,
                args.tab_id,
                "mouseWheel",
                args.x,
                args.y,
                deltaX=args.scroll_x,
                deltaY=args.scroll_y,
            )
        )
    elif args.command == "type":
        print_json(
            cdp_request(
                args,
                args.tab_id,
                "Input.insertText",
                params={"text": args.text},
            )
        )
    elif args.command == "press":
        keys = parse_keys(args.keys)
        modifiers = [key for key in keys if key in {"Alt", "Control", "Meta", "Shift"}]
        regular = [key for key in keys if key not in modifiers]
        if not regular and len(modifiers) == 1:
            regular = modifiers
            modifiers = []
        for key in modifiers:
            dispatch_key(args, args.tab_id, key, "rawKeyDown", modifiers)
        for key in regular:
            dispatch_key(args, args.tab_id, key, "keyDown", modifiers)
            result = dispatch_key(args, args.tab_id, key, "keyUp", modifiers)
        for key in reversed(modifiers):
            dispatch_key(args, args.tab_id, key, "keyUp", modifiers)
        print_json(result if regular else {})
    elif args.command == "drag":
        if len(args.path) < 2:
            raise RuntimeError("--path needs at least two points")
        for point in args.path:
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                raise RuntimeError("--path items must be objects with x and y")
        first = args.path[0]
        mouse_event(args, args.tab_id, "mouseMoved", first["x"], first["y"])
        mouse_event(
            args,
            args.tab_id,
            "mousePressed",
            first["x"],
            first["y"],
            button="left",
            clickCount=1,
        )
        result = {}
        for point in args.path[1:]:
            result = mouse_event(
                args,
                args.tab_id,
                "mouseMoved",
                point["x"],
                point["y"],
                button="left",
                buttons=1,
            )
        last = args.path[-1]
        result = mouse_event(
            args,
            args.tab_id,
            "mouseReleased",
            last["x"],
            last["y"],
            button="left",
            clickCount=1,
        )
        print_json(result)
    elif args.command == "wait":
        if args.ms:
            time.sleep(args.ms / 1000)
        checks = [
            args.url_contains is not None,
            args.title_contains is not None,
            args.selector is not None,
        ]
        if any(checks) and args.tab_id is None:
            raise RuntimeError("--tab-id is required for URL/title/selector waits")
        deadline = time.time() + args.timeout
        matched = not any(checks)
        while any(checks) and time.time() <= deadline:
            if args.url_contains is not None:
                matched = args.url_contains in (
                    cdp_value(args, args.tab_id, "location.href", timeout=2) or ""
                )
            elif args.title_contains is not None:
                matched = args.title_contains in (
                    cdp_value(args, args.tab_id, "document.title", timeout=2) or ""
                )
            elif args.selector is not None:
                expression = (
                    "Boolean(document.querySelector("
                    + json.dumps(args.selector)
                    + "))"
                )
                matched = bool(cdp_value(args, args.tab_id, expression, timeout=2))
            if matched:
                break
            time.sleep(0.25)
        if not matched:
            raise RuntimeError("wait condition timed out")
        print_json({"ok": True})
    elif args.command == "selector-click":
        rect = cdp_value(
            args,
            args.tab_id,
            selector_rect_expression(args.selector),
            timeout=args.timeout,
        )
        if not rect:
            raise RuntimeError(f"selector not found: {args.selector}")
        x = rect["x"] + rect["width"] / 2
        y = rect["y"] + rect["height"] / 2
        mouse_event(args, args.tab_id, "mouseMoved", x, y)
        mouse_event(
            args,
            args.tab_id,
            "mousePressed",
            x,
            y,
            button="left",
            clickCount=1,
        )
        result = mouse_event(
            args,
            args.tab_id,
            "mouseReleased",
            x,
            y,
            button="left",
            clickCount=1,
        )
        print_json({"ok": True, "x": x, "y": y, "result": result})
    elif args.command == "selector-fill":
        ok = cdp_value(
            args,
            args.tab_id,
            selector_fill_expression(args.selector, args.text),
            timeout=args.timeout,
        )
        if not ok:
            raise RuntimeError(f"selector not found: {args.selector}")
        print_json({"ok": True})
    elif args.command == "selector-text":
        print_json(
            {
                "text": cdp_value(
                    args,
                    args.tab_id,
                    selector_text_expression(args.selector),
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "selector-attr":
        print_json(
            {
                "value": cdp_value(
                    args,
                    args.tab_id,
                    selector_attr_expression(args.selector, args.name),
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "selector-count":
        expression = (
            "document.querySelectorAll(" + json.dumps(args.selector) + ").length"
        )
        print_json(
            {
                "count": cdp_value(
                    args,
                    args.tab_id,
                    expression,
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "wait-selector":
        if not wait_until(
            args,
            lambda: bool(
                cdp_value(
                    args,
                    args.tab_id,
                    selector_exists_expression(args.selector),
                    timeout=2,
                )
            ),
        ):
            raise RuntimeError("wait-selector timed out")
        print_json({"ok": True})
    elif args.command == "name-session":
        print_json(rpc("nameSession", {**session_params(args), "name": args.name}))
    elif args.command == "viewport":
        if args.reset:
            print_json(
                cdp_request(
                    args,
                    args.tab_id,
                    "Emulation.clearDeviceMetricsOverride",
                    timeout=args.timeout,
                )
            )
        else:
            if args.width is None or args.height is None:
                raise RuntimeError("--width and --height are required unless --reset")
            print_json(
                cdp_request(
                    args,
                    args.tab_id,
                    "Emulation.setDeviceMetricsOverride",
                    params={
                        "width": args.width,
                        "height": args.height,
                        "deviceScaleFactor": args.device_scale_factor,
                        "mobile": bool(args.mobile),
                    },
                    timeout=args.timeout,
                )
            )
    elif args.command == "clipboard-read-text":
        print_json({"ok": True, "text": os_clipboard_read(), "source": "os"})
    elif args.command == "clipboard-write-text":
        print_json({"ok": os_clipboard_write(args.text), "source": "os"})
    elif args.command == "console-logs":
        if args.clear:
            bridge_post("/events/clear")
        cdp_request(args, args.tab_id, "Runtime.enable", timeout=args.timeout)
        events = recent_events(max(args.limit * 4, args.limit), method="onCDPEvent")
        logs = []
        for event in events:
            if not tab_matches_event(args.tab_id, event):
                continue
            params = event.get("params") or {}
            if params.get("method") != "Runtime.consoleAPICalled":
                continue
            payload = params.get("params") or {}
            values = []
            for item in payload.get("args") or []:
                if "value" in item:
                    values.append(item.get("value"))
                else:
                    values.append(item.get("description") or item.get("type"))
            logs.append(
                {
                    "type": payload.get("type"),
                    "values": values,
                    "timestamp": payload.get("timestamp"),
                    "time": event.get("time"),
                }
            )
        print_json({"logs": logs[-args.limit:]})
    elif args.command == "events":
        if args.clear:
            bridge_post("/events/clear")
            print_json({"ok": True})
        else:
            print_json({"events": recent_events(args.limit, method=args.method)})
    elif args.command == "downloads":
        if args.clear:
            bridge_post("/events/clear")
            print_json({"ok": True})
        else:
            events = recent_events(max(args.limit * 4, args.limit))
            downloads = [
                event
                for event in events
                if event.get("method") == "onDownloadChange"
                or ((event.get("params") or {}).get("method") or "").startswith(
                    "Browser.download"
                )
            ]
            print_json({"downloads": downloads[-args.limit:]})
    elif args.command == "frames":
        tree = cdp_request(
            args,
            args.tab_id,
            "Page.getFrameTree",
            timeout=args.timeout,
        )
        frame_tree = tree.get("frameTree") or {}
        print_json({"frames": flatten_frame_tree(frame_tree)})
    elif args.command == "page-assets":
        print_json(
            {
                "assets": cdp_value(
                    args,
                    args.tab_id,
                    page_assets_expression(args.limit),
                    timeout=args.timeout,
                )
            }
        )
    elif args.command == "screenshot":
        params = {
            "format": "png",
            "captureBeyondViewport": bool(args.full_page),
        }
        if args.full_page:
            metrics = cdp_request(
                args,
                args.tab_id,
                "Page.getLayoutMetrics",
                timeout=args.timeout,
            )
            size = metrics.get("cssContentSize") or {}
            params["clip"] = {
                "x": size.get("x", 0),
                "y": size.get("y", 0),
                "width": size.get("width", 1280),
                "height": size.get("height", 720),
                "scale": 1,
            }
        result = cdp_request(
            args,
            args.tab_id,
            "Page.captureScreenshot",
            params=params,
            timeout=args.timeout,
        )
        data = result.get("data")
        if not isinstance(data, str):
            raise RuntimeError("Page.captureScreenshot returned no data")
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as handle:
            handle.write(base64.b64decode(data))
        print_json({"path": os.path.abspath(args.out)})
    elif args.command == "close":
        params = {
            **session_params(args),
            "keep": [{"tabId": tab_id, "status": "handoff"} for tab_id in args.tab_id],
        }
        print_json(rpc("finalizeTabs", params))
    elif args.command == "finalize":
        keep = []
        for item in args.keep:
            raw_tab_id, _, status = item.partition(":")
            if status not in {"handoff", "deliverable"}:
                raise RuntimeError("--keep must be tabId:handoff or tabId:deliverable")
            keep.append({"tabId": int(raw_tab_id), "status": status})
        print_json(rpc("finalizeTabs", {**session_params(args), "keep": keep}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
