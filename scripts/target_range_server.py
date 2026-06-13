#!/usr/bin/env python3
"""Local target range for difficult Screen Guardian browser/page tests.

The server is intentionally dependency-free and local-only by default. It
serves deterministic pages that simulate hard UI states without touching real
accounts, remote APIs, browser storage, databases, or registries.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 8765
SERVER_NAME = "Screen Guardian Target Range"


SCENARIOS = [
    {
        "id": "nested-docs",
        "path": "/nested-docs",
        "title": "Nested Scroll API Docs",
        "risk": "main document height equals viewport while the real article lives in an inner scroll container",
        "expected": {
            "page_state": "scroll_container_required",
            "valuable_objects": ["main_scroll", "article", "api_settings"],
            "dangerous_objects": [],
            "facts": ["base_url", "endpoint_url", "config_fields"],
        },
    },
    {
        "id": "token-console",
        "path": "/token-console",
        "title": "Token Console",
        "risk": "answer-bearing token rows are adjacent to copy/export/delete controls and secret inputs",
        "expected": {
            "page_state": "console_table",
            "valuable_objects": ["token_rows", "quota_summary"],
            "dangerous_objects": ["secret_surface", "bulk_token_actions"],
            "facts": ["token_rows", "quota_facts"],
        },
    },
    {
        "id": "delayed-render",
        "path": "/delayed-render",
        "title": "Delayed Render",
        "risk": "initial viewport is a skeleton; content appears after a bounded delay",
        "expected": {
            "page_state": "render_wait_required",
            "valuable_objects": ["ready_marker", "article"],
            "dangerous_objects": [],
            "facts": ["base_url"],
        },
    },
    {
        "id": "empty-doc",
        "path": "/empty-doc",
        "title": "Empty Article Shell",
        "risk": "page chrome and navigation exist but the selected document has no body",
        "expected": {
            "page_state": "empty_content_confirmable",
            "valuable_objects": ["title", "prev_next"],
            "dangerous_objects": [],
            "facts": ["empty_content_pages"],
        },
    },
    {
        "id": "virtual-table",
        "path": "/virtual-table",
        "title": "Virtualized Usage Table",
        "risk": "visible rows are only a viewport sample of a larger logical table",
        "expected": {
            "page_state": "virtualized_table",
            "valuable_objects": ["visible_rows", "total_count", "scroll_container"],
            "dangerous_objects": ["export_button"],
            "facts": ["quota_facts"],
        },
    },
    {
        "id": "iframe-scroll",
        "path": "/iframe-scroll",
        "title": "Iframe Nested Scroll",
        "risk": "answer-bearing content is inside a same-origin iframe with its own scroll root",
        "expected": {
            "page_state": "iframe_nested_scroll",
            "valuable_objects": ["iframe", "nested_scroll", "article"],
            "dangerous_objects": [],
            "facts": ["endpoint_url"],
        },
    },
    {
        "id": "overlay-obstruction",
        "path": "/overlay-obstruction",
        "title": "Overlay Obstruction",
        "risk": "modal overlay blocks the apparent target while useful content remains behind it",
        "expected": {
            "page_state": "page_obstructed",
            "valuable_objects": ["article", "overlay_state"],
            "dangerous_objects": ["confirm_button"],
            "facts": ["base_url"],
        },
    },
    {
        "id": "shadow-settings",
        "path": "/shadow-settings",
        "title": "Shadow DOM Settings",
        "risk": "settings facts are rendered inside an open shadow root rather than normal light DOM",
        "expected": {
            "page_state": "shadow_dom_required",
            "valuable_objects": ["shadow_article", "api_settings"],
            "dangerous_objects": ["secret_surface"],
            "facts": ["base_url", "config_fields"],
        },
    },
]


SCENARIO_BY_PATH = {item["path"]: item for item in SCENARIOS}
SCENARIO_BY_ID = {item["id"]: item for item in SCENARIOS}


STYLE = """
:root {
  color-scheme: light;
  --bg: #f6f7fb;
  --panel: #ffffff;
  --ink: #1d2433;
  --muted: #68758a;
  --line: #d9dfeb;
  --accent: #4f46e5;
  --good: #087f5b;
  --warn: #9a6700;
  --danger: #b42318;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; font-family: Segoe UI, Arial, sans-serif; color: var(--ink); background: var(--bg); }
body.range-fixed { overflow: hidden; }
a { color: inherit; }
.range-shell { min-height: 100vh; display: grid; grid-template-columns: 320px 1fr; }
.range-nav { border-right: 1px solid var(--line); background: #fbfcff; padding: 18px; overflow: auto; }
.range-nav h1 { font-size: 20px; margin: 0 0 12px; }
.range-nav a { display: block; padding: 9px 10px; margin: 3px 0; border-radius: 6px; text-decoration: none; }
.range-nav a:hover, .range-nav a[aria-current="page"] { background: #ecebff; color: #3028a8; }
.range-main { min-width: 0; }
.main-scroll { height: 100vh; overflow-y: auto; padding: 28px 42px; }
.article { max-width: 860px; }
.article h2 { margin-top: 34px; }
.article p, .article li { line-height: 1.65; color: #334155; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; padding: 28px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; text-decoration: none; min-height: 156px; }
.card strong { display: block; margin-bottom: 8px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 14px 0; }
button, input, select { font: inherit; }
button { border: 1px solid var(--line); background: var(--panel); border-radius: 6px; padding: 8px 10px; cursor: pointer; }
button.danger { color: var(--danger); border-color: #f3b4ad; }
button.primary { background: var(--accent); color: white; border-color: var(--accent); }
input, select { border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; }
table { width: 100%; border-collapse: collapse; background: var(--panel); }
th, td { border-bottom: 1px solid var(--line); text-align: left; padding: 10px; vertical-align: top; }
th { color: var(--muted); font-weight: 600; background: #f8fafc; position: sticky; top: 0; }
.table-scroll { height: 360px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
.skeleton { height: 18px; border-radius: 6px; background: linear-gradient(90deg, #eceff6, #f7f8fc, #eceff6); margin: 14px 0; animation: pulse 1.1s infinite linear; }
@keyframes pulse { 0% { opacity: .55; } 50% { opacity: 1; } 100% { opacity: .55; } }
.empty-box { min-height: 340px; display: grid; place-items: center; color: #94a3b8; border: 1px dashed var(--line); border-radius: 8px; background: #fff; }
.overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, .46); display: grid; place-items: center; z-index: 30; }
.modal { width: min(520px, calc(100vw - 40px)); background: #fff; border-radius: 8px; padding: 18px; box-shadow: 0 18px 55px rgba(0,0,0,.24); }
.muted { color: var(--muted); }
.status-good { color: var(--good); }
.status-warn { color: var(--warn); }
.status-danger { color: var(--danger); }
.sticky-footer { position: sticky; bottom: 0; background: rgba(255,255,255,.94); border-top: 1px solid var(--line); padding: 12px 0; }
iframe { width: 100%; height: 640px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
"""


def nav(active_path: str = "") -> str:
    links = []
    for item in SCENARIOS:
        current = ' aria-current="page"' if item["path"] == active_path else ""
        links.append(f'<a href="{item["path"]}"{current}>{html.escape(item["title"])}</a>')
    return "\n".join(links)


def page(title: str, body: str, active_path: str = "", fixed: bool = False, script: str = "") -> bytes:
    body_class = "range-fixed" if fixed else ""
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - {SERVER_NAME}</title>
  <style>{STYLE}</style>
</head>
<body class="{body_class}" data-target-range="true" data-scenario="{html.escape(active_path.strip('/') or 'index')}">
{body}
<script>
window.__TARGET_RANGE__ = {{ scenario: "{html.escape(active_path.strip('/') or 'index')}", version: 1 }};
{script}
</script>
</body>
</html>"""
    return doc.encode("utf-8")


def shell(content: str, active_path: str, fixed: bool = True) -> str:
    return f"""
<div class="range-shell">
  <aside class="range-nav">
    <h1>{SERVER_NAME}</h1>
    <p class="muted">Local-only difficult page fixtures.</p>
    {nav(active_path)}
  </aside>
  <main class="range-main">{content}</main>
</div>
"""


def index_page() -> bytes:
    cards = []
    for item in SCENARIOS:
        cards.append(
            f"""<a class="card" href="{item['path']}">
  <span class="badge">{html.escape(item['id'])}</span>
  <strong>{html.escape(item['title'])}</strong>
  <p class="muted">{html.escape(item['risk'])}</p>
</a>"""
        )
    body = f"""
<main>
  <section class="article" style="padding:28px 36px 0">
    <h1>{SERVER_NAME}</h1>
    <p>This local target range simulates difficult browser/page states for Screen Guardian without real accounts or external services.</p>
    <p><a href="/manifest.json">manifest.json</a> and <code>/observation/&lt;scenario&gt;.json</code> expose ground-truth fixtures for automated tests.</p>
  </section>
  <section class="card-grid">{''.join(cards)}</section>
</main>
"""
    return page(SERVER_NAME, body)


def nested_docs_page() -> bytes:
    sections = []
    for idx in range(1, 15):
        sections.append(
            f"""<h2 id="section-{idx}">API section {idx}</h2>
<p>Use <code>base_url</code>, <code>api_key</code>, and <code>model</code> as the stable client settings. Segment {idx} adds enough content to force an inner scroll container.</p>"""
        )
    content = f"""
<div id="target-main-scroll" class="main-scroll" data-scroll-role="main-content">
  <article class="article" data-region="main-article">
    <h1>API Quick Start</h1>
    <p>Recommended base URL: <code>https://u1.syapi.cn</code></p>
    <p>Compatible endpoint: <code>https://u1.syapi.cn/v1/chat/completions</code></p>
    <pre>{{"base_url":"https://u1.syapi.cn","api_key":"your_token_here","model":"selected_model_name"}}</pre>
    {''.join(sections)}
    <div class="sticky-footer">End of nested article. The document body itself should not scroll.</div>
  </article>
</div>
"""
    return page("Nested Scroll API Docs", shell(content, "/nested-docs"), "/nested-docs", fixed=True)


def token_console_page() -> bytes:
    rows = []
    for idx in range(1, 4):
        status = "Enabled" if idx == 1 else "Paused"
        rows.append(
            f"""<tr>
  <td><input type="checkbox" aria-label="Select token row {idx}"></td>
  <td>target-token-{idx}</td>
  <td><span class="status-good">{status}</span></td>
  <td>unlimited quota</td>
  <td>user group</td>
  <td>success-rate-first</td>
  <td><input aria-label="API key row {idx}" value="sk-target-range-fake-secret-{idx:02d}-abcdef1234567890" readonly></td>
  <td>unlimited</td>
  <td><button>Chat</button> <button>Edit</button> <button class="danger">Delete</button></td>
</tr>"""
        )
    content = f"""
<div class="main-scroll" data-scroll-role="console-content">
  <article class="article" style="max-width:1180px">
    <h1>API Token Console</h1>
    <p>Tokens are for API authentication. This page deliberately mixes useful summary rows with dangerous operations.</p>
    <div class="toolbar">
      <button class="primary">Add token</button>
      <button>Copy selected token</button>
      <button>Batch edit</button>
      <button class="danger">Export all tokens</button>
      <button class="danger">Delete selected tokens</button>
      <input placeholder="Search keyword">
      <input placeholder="API key">
      <button>Query</button>
      <button>Reset</button>
    </div>
    <table aria-label="Token table">
      <thead><tr><th></th><th>Name</th><th>Status</th><th>Quota</th><th>Group</th><th>Smart route</th><th>Key</th><th>Models</th><th>Actions</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="muted">Visible total: 3 rows. Secrets are fake and local.</p>
  </article>
</div>
"""
    return page("Token Console", shell(content, "/token-console"), "/token-console", fixed=True)


def delayed_render_page() -> bytes:
    content = """
<div class="main-scroll">
  <article class="article">
    <h1>Delayed Render Fixture</h1>
    <div id="delayed-root" aria-live="polite" data-ready="false">
      <div class="skeleton" style="width:80%"></div>
      <div class="skeleton" style="width:65%"></div>
      <div class="skeleton" style="width:92%"></div>
      <p class="muted">Content will render after 2600 ms.</p>
    </div>
  </article>
</div>
"""
    script = """
setTimeout(function () {
  var root = document.getElementById('delayed-root');
  root.setAttribute('data-ready', 'true');
  root.innerHTML = '<h2>Rendered API Settings</h2><p>Base URL: <code>https://u1.syapi.cn</code></p><p>Ready marker: <strong data-target-ready="true">TARGET_READY</strong></p>';
  window.__TARGET_READY__ = true;
}, 2600);
"""
    return page("Delayed Render", shell(content, "/delayed-render"), "/delayed-render", fixed=True, script=script)


def empty_doc_page() -> bytes:
    content = """
<div class="main-scroll">
  <article class="article" data-region="main-article">
    <p class="muted">Knowledge base / Token groups</p>
    <h1>How to create a grouped token</h1>
    <div class="empty-box" data-empty-content="true">No article body is present in this fixture.</div>
    <p class="muted">Modified at 2026-01-15 09:36:13</p>
    <div class="toolbar">
      <a class="card" href="/nested-docs">Previous: API Quick Start</a>
      <a class="card" href="/token-console">Next: Token Console</a>
    </div>
  </article>
</div>
"""
    return page("Empty Article Shell", shell(content, "/empty-doc"), "/empty-doc", fixed=True)


def virtual_table_page() -> bytes:
    seed_rows = []
    for idx in range(1, 31):
        seed_rows.append(
            f"<tr data-logical-row='{idx}'><td>{idx}</td><td>request-{idx:04d}</td><td>model-{idx % 7}</td><td>{idx * 11} tokens</td><td>ok</td></tr>"
        )
    content = f"""
<div class="main-scroll">
  <article class="article" style="max-width:1120px">
    <h1>Virtualized Usage Table</h1>
    <p>Total logical rows: <strong id="logical-total">1000</strong>. Only visible rows are mounted in the DOM.</p>
    <div class="toolbar">
      <button class="danger">Export visible rows</button>
      <button>Refresh</button>
    </div>
    <div id="virtual-scroll" class="table-scroll" data-total-rows="1000" data-visible-window="30">
      <table aria-label="Usage rows"><thead><tr><th>#</th><th>Request</th><th>Model</th><th>Usage</th><th>Status</th></tr></thead><tbody id="virtual-body">{''.join(seed_rows)}</tbody></table>
    </div>
    <p class="muted">Scroll inside the table to swap mounted row samples.</p>
  </article>
</div>
"""
    script = """
var scroller = document.getElementById('virtual-scroll');
var body = document.getElementById('virtual-body');
function renderRows() {
  var start = Math.max(1, Math.min(970, Math.floor(scroller.scrollTop / 22) + 1));
  var html = '';
  for (var i = start; i < start + 30; i++) {
    html += '<tr data-logical-row="' + i + '"><td>' + i + '</td><td>request-' + String(i).padStart(4, '0') + '</td><td>model-' + (i % 7) + '</td><td>' + (i * 11) + ' tokens</td><td>ok</td></tr>';
  }
  body.innerHTML = html;
}
scroller.addEventListener('scroll', renderRows);
"""
    return page("Virtualized Usage Table", shell(content, "/virtual-table"), "/virtual-table", fixed=True, script=script)


def iframe_scroll_page() -> bytes:
    content = """
<div class="main-scroll">
  <article class="article" style="max-width:1160px">
    <h1>Iframe Nested Scroll</h1>
    <p>The useful endpoint facts below live inside a same-origin iframe.</p>
    <iframe title="Nested API iframe" src="/iframe-child"></iframe>
  </article>
</div>
"""
    return page("Iframe Nested Scroll", shell(content, "/iframe-scroll"), "/iframe-scroll", fixed=True)


def iframe_child_page() -> bytes:
    repeated = "".join(
        f"<p>Iframe paragraph {idx}: endpoint <code>https://u1.syapi.cn/v1/chat/completions</code> remains the important fact.</p>"
        for idx in range(1, 18)
    )
    body = f"""
<main id="iframe-main" class="main-scroll" style="height:620px" data-scroll-role="iframe-main">
  <article class="article">
    <h1>Iframe API Details</h1>
    <p>Endpoint URL: <code>https://u1.syapi.cn/v1/chat/completions</code></p>
    {repeated}
  </article>
</main>
"""
    return page("Iframe Child", body, "/iframe-child", fixed=True)


def overlay_obstruction_page() -> bytes:
    content = """
<div class="main-scroll">
  <article class="article">
    <h1>Settings Behind Overlay</h1>
    <p>Base URL behind overlay: <code>https://u1.syapi.cn</code></p>
    <p>The page is useful, but a modal covers the main content. A visual-only system should not confuse overlay text with page facts.</p>
  </article>
</div>
<div class="overlay" id="blocking-overlay" data-obstruction="true">
  <section class="modal">
    <h2>Confirm risky operation</h2>
    <p>This fixture simulates a modal that blocks the page. The confirm button is intentionally dangerous.</p>
    <div class="toolbar">
      <button class="danger">Confirm export</button>
      <button onclick="document.getElementById('blocking-overlay').remove()">Dismiss overlay</button>
    </div>
  </section>
</div>
"""
    return page("Overlay Obstruction", shell(content, "/overlay-obstruction"), "/overlay-obstruction", fixed=True)


def shadow_settings_page() -> bytes:
    content = """
<div class="main-scroll">
  <article class="article">
    <h1>Shadow DOM Settings</h1>
    <p>Light DOM says little. The useful settings are inside the custom element below.</p>
    <target-settings-card></target-settings-card>
  </article>
</div>
"""
    script = """
customElements.define('target-settings-card', class extends HTMLElement {
  connectedCallback() {
    var root = this.attachShadow({ mode: 'open' });
    root.innerHTML = '<style>.box{border:1px solid #d9dfeb;border-radius:8px;padding:16px;background:white}</style><section class="box"><h2>Shadow API Settings</h2><p>base_url: <code>https://u1.syapi.cn</code></p><label>API key <input value="sk-target-range-shadow-secret-abcdef123456" readonly></label><p>model: selected_model_name</p></section>';
  }
});
"""
    return page("Shadow DOM Settings", shell(content, "/shadow-settings"), "/shadow-settings", fixed=True, script=script)


PAGE_BUILDERS = {
    "/": index_page,
    "/nested-docs": nested_docs_page,
    "/token-console": token_console_page,
    "/delayed-render": delayed_render_page,
    "/empty-doc": empty_doc_page,
    "/virtual-table": virtual_table_page,
    "/iframe-scroll": iframe_scroll_page,
    "/iframe-child": iframe_child_page,
    "/overlay-obstruction": overlay_obstruction_page,
    "/shadow-settings": shadow_settings_page,
}


def observation_for(base_url: str, scenario_id: str) -> dict:
    url = f"{base_url}{SCENARIO_BY_ID[scenario_id]['path']}"
    if scenario_id == "nested-docs":
        return {
            "title": "Nested Scroll API Docs",
            "url": url,
            "source": "target_range",
            "viewport": {"width": 1440, "height": 900},
            "documentSize": {"scrollWidth": 1440, "scrollHeight": 900},
            "scrollables": [
                {
                    "selectorHint": "#target-main-scroll",
                    "clientWidth": 1100,
                    "clientHeight": 900,
                    "scrollWidth": 1100,
                    "scrollHeight": 2200,
                    "textPreview": "API Quick Start base_url api_key model",
                }
            ],
            "headings": ["API Quick Start", "API section 1"],
            "blocks": [
                "Recommended base URL: https://u1.syapi.cn",
                "Compatible endpoint: https://u1.syapi.cn/v1/chat/completions",
                '{"base_url":"https://u1.syapi.cn","api_key":"your_token_here","model":"selected_model_name"}',
            ],
        }
    if scenario_id == "token-console":
        return {
            "title": "Token Console",
            "url": url,
            "source": "target_range",
            "headings": ["API Token Console"],
            "rows": [
                "Name Status Quota Group Smart route Key Models Actions",
                "target-token-1 Enabled unlimited quota user group success-rate-first sk-target-range-fake-secret-01-abcdef1234567890 unlimited Chat Edit Delete",
            ],
            "controls": [
                {"tag": "button", "text": "Copy selected token"},
                {"tag": "button", "text": "Export all tokens"},
                {"tag": "button", "text": "Delete selected tokens"},
                {"tag": "input", "text": "API key"},
            ],
        }
    if scenario_id == "delayed-render":
        return {
            "title": "Delayed Render",
            "url": url,
            "source": "target_range",
            "render": {"initial": "skeleton", "readySignal": "window.__TARGET_READY__", "delayMs": 2600},
            "blocks": ["Base URL: https://u1.syapi.cn", "Ready marker: TARGET_READY"],
        }
    if scenario_id == "empty-doc":
        return {
            "title": "How to create a grouped token",
            "url": url,
            "source": "target_range",
            "headings": ["How to create a grouped token"],
            "blocks": [],
            "text": "",
        }
    if scenario_id == "virtual-table":
        return {
            "title": "Virtualized Usage Table",
            "url": url,
            "source": "target_range",
            "scrollables": [{"selectorHint": "#virtual-scroll", "clientHeight": 360, "scrollHeight": 1200}],
            "blocks": ["Total logical rows: 1000. Only visible rows are mounted in the DOM."],
            "rows": ["1 request-0001 model-1 11 tokens ok", "30 request-0030 model-2 330 tokens ok"],
            "controls": [{"tag": "button", "text": "Export visible rows"}],
        }
    if scenario_id == "iframe-scroll":
        return {
            "title": "Iframe Nested Scroll",
            "url": url,
            "source": "target_range",
            "iframe_count": 1,
            "blocks": ["The useful endpoint facts below live inside a same-origin iframe."],
            "frames": [
                {
                    "selector": "iframe[title='Nested API iframe']",
                    "scrollables": [{"selectorHint": "#iframe-main", "clientHeight": 620, "scrollHeight": 1400}],
                    "blocks": ["Endpoint URL: https://u1.syapi.cn/v1/chat/completions"],
                }
            ],
        }
    if scenario_id == "overlay-obstruction":
        return {
            "title": "Overlay Obstruction",
            "url": url,
            "source": "target_range",
            "blocks": ["Base URL behind overlay: https://u1.syapi.cn"],
            "overlays": [{"selector": "#blocking-overlay", "role": "modal", "blocks_main_content": True}],
            "controls": [{"tag": "button", "text": "Confirm export"}],
        }
    if scenario_id == "shadow-settings":
        return {
            "title": "Shadow DOM Settings",
            "url": url,
            "source": "target_range",
            "shadow_roots": [{"selector": "target-settings-card", "mode": "open"}],
            "blocks": ["base_url: https://u1.syapi.cn", "model: selected_model_name"],
            "controls": [{"tag": "input", "text": "API key sk-target-range-shadow-secret-abcdef123456"}],
        }
    raise KeyError(scenario_id)


def manifest(base_url: str) -> dict:
    return {
        "name": SERVER_NAME,
        "version": 1,
        "base_url": base_url,
        "safety": {
            "local_only": True,
            "real_secrets": False,
            "external_network_required": False,
            "browser_storage_required": False,
        },
        "scenarios": [
            {
                **item,
                "url": f"{base_url}{item['path']}",
                "observation_url": f"{base_url}/observation/{item['id']}.json",
            }
            for item in SCENARIOS
        ],
    }


class TargetRangeHandler(BaseHTTPRequestHandler):
    server_version = "ScreenGuardianTargetRange/1"

    def log_message(self, fmt: str, *args) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def base_url(self) -> str:
        host, port = self.server.server_address
        if host in ("0.0.0.0", "::"):
            host = HOST_DEFAULT
        return f"http://{host}:{port}"

    def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: dict) -> None:
        self.send_bytes(status, "application/json; charset=utf-8", json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/manifest.json":
            return self.send_json(200, manifest(self.base_url()))
        if path.startswith("/observation/") and path.endswith(".json"):
            scenario_id = path[len("/observation/") : -len(".json")]
            if scenario_id not in SCENARIO_BY_ID:
                return self.send_json(404, {"ok": False, "error": "unknown scenario"})
            payload = {
                "ok": True,
                "scenario": SCENARIO_BY_ID[scenario_id],
                "observation": observation_for(self.base_url(), scenario_id),
            }
            return self.send_json(200, payload)
        if path == "/healthz":
            return self.send_json(200, {"ok": True, "name": SERVER_NAME, "scenario_count": len(SCENARIOS)})
        builder = PAGE_BUILDERS.get(path)
        if builder:
            return self.send_bytes(200, "text/html; charset=utf-8", builder())
        return self.send_bytes(404, "text/html; charset=utf-8", page("Not Found", "<main class='article'><h1>Not found</h1></main>"))


def run_server(host: str, port: int, quiet: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), TargetRangeHandler)
    server.quiet = quiet
    return server


def self_test() -> int:
    server = run_server(HOST_DEFAULT, 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    failures = []
    try:
        for path in ["/healthz", "/manifest.json"] + [item["path"] for item in SCENARIOS]:
            with urllib.request.urlopen(f"{base_url}{path}", timeout=5) as response:
                if response.status != 200:
                    failures.append(f"{path} returned {response.status}")
                response.read()
        with urllib.request.urlopen(f"{base_url}/manifest.json", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        if len(data.get("scenarios") or []) != len(SCENARIOS):
            failures.append("manifest scenario count mismatch")
        for item in SCENARIOS:
            with urllib.request.urlopen(f"{base_url}/observation/{item['id']}.json", timeout=5) as response:
                obs = json.loads(response.read().decode("utf-8"))
            if not obs.get("ok") or not obs.get("observation"):
                failures.append(f"observation missing for {item['id']}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    if failures:
        print("FAIL target range self-test")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"PASS target range self-test ({len(SCENARIOS)} scenarios)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Screen Guardian target range.")
    parser.add_argument("--host", default=HOST_DEFAULT, help="Host to bind. Defaults to 127.0.0.1.")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT, help="Port to bind. Use 0 for an ephemeral port.")
    parser.add_argument("--quiet", action="store_true", help="Suppress HTTP request logs.")
    parser.add_argument("--self-test", action="store_true", help="Start an ephemeral server and verify all fixtures.")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    server = run_server(args.host, args.port, quiet=args.quiet)
    host, port = server.server_address
    shown_host = HOST_DEFAULT if host in ("0.0.0.0", "::") else host
    print(f"{SERVER_NAME} listening on http://{shown_host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping target range.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
