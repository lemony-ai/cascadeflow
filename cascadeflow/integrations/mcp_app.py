"""Self-contained MCP Apps view for cascadeflow routing results."""

from __future__ import annotations

ROUTING_APP_URI = "ui://cascadeflow/route-v1.html"
ROUTING_APP_MIME_TYPE = "text/html;profile=mcp-app"

ROUTING_APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>cascadeflow route</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --line: #dbe3ee;
      --accent: #0f766e;
      --accent-soft: #ccfbf1;
      --good: #15803d;
    }
    :root[data-theme="dark"] {
      --bg: #10151f;
      --card: #171e2b;
      --text: #ecf3ff;
      --muted: #9cabc1;
      --line: #2c384c;
      --accent: #5eead4;
      --accent-soft: #123c3a;
      --good: #86efac;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 12px;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell {
      max-width: 760px;
      margin: 0 auto;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--card);
    }
    .header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .brand { font-weight: 750; letter-spacing: -.02em; }
    .badge {
      padding: 4px 9px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }
    .summary { margin: 12px 0 0; color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-top: 14px;
    }
    .metric { min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: 12px; }
    .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
    .value { margin-top: 4px; overflow-wrap: anywhere; font-weight: 700; }
    .value.good { color: var(--good); }
    .details {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 6px 12px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      font-size: 12px;
    }
    .details dt { color: var(--muted); }
    .details dd { margin: 0; overflow-wrap: anywhere; text-align: right; }
    .foot { margin-top: 12px; color: var(--muted); font-size: 11px; }
    @media (max-width: 560px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <main class="shell" aria-live="polite">
    <div class="header">
      <div class="brand">cascadeflow</div>
      <div class="badge" id="status">Routing…</div>
    </div>
    <p class="summary" id="summary">Waiting for the cost-aware route result.</p>
    <section class="grid" aria-label="Route metrics">
      <div class="metric"><div class="label">Model</div><div class="value" id="model">—</div></div>
      <div class="metric"><div class="label">Cost</div><div class="value" id="cost">—</div></div>
      <div class="metric"><div class="label">Saved</div><div class="value good" id="saved">—</div></div>
      <div class="metric"><div class="label">Latency</div><div class="value" id="latency">—</div></div>
    </section>
    <dl class="details">
      <dt>Strategy</dt><dd id="strategy">—</dd>
      <dt>Knowledge</dt><dd id="knowledge">None selected</dd>
    </dl>
    <div class="foot">Knowledge is resolved server-side and is not embedded in this view.</div>
  </main>
  <script>
    (() => {
      const byId = (id) => document.getElementById(id);
      let initialized = false;
      const money = (value) => Number.isFinite(Number(value))
        ? "$" + Number(value).toFixed(Number(value) < 0.01 ? 6 : 4)
        : "—";
      const text = (id, value) => { byId(id).textContent = value ?? "—"; };

      function applyHostContext(context) {
        if (context && context.theme) document.documentElement.dataset.theme = context.theme;
      }

      function structuredResult(result) {
        if (result && result.structuredContent) return result.structuredContent;
        const block = result && Array.isArray(result.content) && result.content.find((x) => x.type === "text");
        if (!block) return null;
        try { return JSON.parse(block.text); } catch (_) { return null; }
      }

      function render(result) {
        const data = structuredResult(result);
        if (!data) {
          text("status", "Unavailable");
          text("summary", "The route completed without a structured trace.");
          return;
        }
        const accepted = data.draft_accepted === true;
        text("status", accepted ? "Draft accepted" : (data.cascaded ? "Escalated" : "Complete"));
        text("summary", accepted
          ? "The lower-cost draft met the quality threshold."
          : (data.cascaded ? "cascadeflow escalated to protect answer quality." : "The route completed directly."));
        text("model", data.model_used);
        text("cost", money(data.total_cost));
        text("saved", money(data.cost_saved));
        text("latency", Number.isFinite(Number(data.latency_ms)) ? Math.round(Number(data.latency_ms)) + " ms" : "—");
        text("strategy", data.routing_strategy);
        const knowledge = data.knowledge || {};
        text("knowledge", knowledge.identity || knowledge.key || "None selected");
        sendSize();
      }

      function post(message) { window.parent.postMessage(message, "*"); }
      function sendSize() {
        if (!initialized) return;
        post({
          jsonrpc: "2.0",
          method: "ui/notifications/size-changed",
          params: { height: document.documentElement.scrollHeight }
        });
      }

      window.addEventListener("message", (event) => {
        if (event.source !== window.parent || !event.data || event.data.jsonrpc !== "2.0") return;
        const message = event.data;
        if (message.id === "cascadeflow-init" && message.result) {
          applyHostContext(message.result.hostContext);
          post({ jsonrpc: "2.0", method: "ui/notifications/initialized" });
          initialized = true;
          sendSize();
        } else if (message.method === "ui/notifications/host-context-changed") {
          applyHostContext(message.params);
        } else if (message.method === "ui/notifications/tool-input") {
          text("status", "Routing…");
        } else if (message.method === "ui/notifications/tool-result") {
          render(message.params);
        } else if (message.method === "ui/notifications/tool-cancelled") {
          text("status", "Cancelled");
          text("summary", (message.params && message.params.reason) || "The route was cancelled.");
        }
      });

      if ("ResizeObserver" in window) {
        new ResizeObserver(sendSize).observe(document.documentElement);
      }
      post({
        jsonrpc: "2.0",
        id: "cascadeflow-init",
        method: "ui/initialize",
        params: {
          appInfo: { name: "cascadeflow route", version: "1.0.0" },
          appCapabilities: {},
          protocolVersion: "2026-01-26"
        }
      });
    })();
  </script>
</body>
</html>
"""

__all__ = ["ROUTING_APP_HTML", "ROUTING_APP_MIME_TYPE", "ROUTING_APP_URI"]
