# ChatGPT and Claude integration through MCP

Yes: one cascadeflow MCP server can expose cost-aware routing as a tool to ChatGPT,
Claude, Claude Desktop, and other MCP clients. The initial integration is tool-first
and deliberately has no required UI.

```text
ChatGPT / Claude
    -> small MCP tool call (query + knowledge ID + optional concise handoff)
    -> cascadeflow MCP server
       -> server-side knowledge resolver
       -> draft / verifier / direct provider calls
    <- answer + compact routing and cost trace
```

This brings cascadeflow logic into a conversation, but it does not replace the host
application's own model. The host model still decides to call the tool, and
cascadeflow then makes its provider calls. That extra host turn and latency must be
included in the end-to-end economics.

## Server factory

Install the optional SDK on Python 3.10+:

```bash
pip install "cascadeflow[mcp]"
```

Create a configured agent and keep knowledge lookup behind the MCP server:

```python
from cascadeflow import CascadeAgent, KnowledgeSnapshot
from cascadeflow.integrations.mcp import create_mcp_server

async def resolve_knowledge(key: str, version: str | None):
    content, resolved_version = await knowledge_store.load(key, version)
    return KnowledgeSnapshot(
        key=key,
        version=resolved_version,
        content=content,
        cache_ttl="1h",
    )

mcp = create_mcp_server(
    agent,
    knowledge_resolver=resolve_knowledge,
    include_ui=True,  # Optional portable routing/savings panel
)

# Local desktop transport:
mcp.run(transport="stdio")

# Remote ChatGPT/Claude transport:
# mcp.run(transport="streamable-http")
```

The `cascadeflow_run` tool accepts:

- `query`: the current request;
- `knowledge_key` and optional `knowledge_version`: server-side selection only;
- `conversation_context`: an optional concise factual handoff when prior turns are
  genuinely required. It is bounded by default to prevent accidental transcript
  replay.

The tool returns the answer plus a compact model, routing, cost, latency, and
knowledge-version trace. It never returns the private knowledge content.

## Host choices

- **ChatGPT:** deploy a public HTTPS Streamable HTTP endpoint (normally `/mcp`) and
  add it as a custom MCP connection in developer mode. OpenAI's current plugin
  documentation describes [building the MCP server](https://developers.openai.com/plugins/build/mcp-server)
  and [connecting it to ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt).
- **Claude and Claude Desktop:** use the same public Streamable HTTP endpoint as a
  remote custom connector. Claude Desktop can also package a local stdio server as
  a desktop extension. See Anthropic's [remote connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
  and [desktop extension guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).

Production remote deployments should use authentication, tenant-scoped knowledge
authorization, rate limits, audit logs, TLS, and a public endpoint reachable by the
host. Do not pass provider API keys as MCP tool arguments.

## MCP Apps / interactive UI

Set `include_ui=True` to register a self-contained routing panel through the standard
[MCP Apps extension](https://modelcontextprotocol.io/docs/extensions/apps). The tool
declares `_meta.ui.resourceUri`, plus ChatGPT's compatibility alias, and serves a
versioned `ui://` resource using `text/html;profile=mcp-app`. It shows the selected
model, route, knowledge identity, cost, savings, and latency in a sandboxed view.

The panel is progressive enhancement: `cascadeflow_run` remains fully usable in
clients that do not render MCP Apps, and the default `include_ui=False` keeps the
server tool-only. The HTML has no external scripts or network requests. Hosts fetch
and cache the UI resource separately; it is not appended to model context or to each
provider query. Tool results remain compact structured data, while private knowledge
continues to stay behind the server-side resolver.

The UI itself does not remove the host-model turn. In ChatGPT or Claude, the host
still selects and invokes `cascadeflow_run`, then cascadeflow pays for its own routed
provider calls. On subscription desktop products that host turn is normally part of
the product plan. For API-based hosts, include the orchestration model's tokens in
the end-to-end cost comparison; use a small host model or direct application
integration when that extra turn would erase the cascade savings.

Run the deterministic transport benchmark with the MCP extra installed:

```bash
python scripts/benchmark-mcp-app.py
```

It verifies that enabling the panel changes neither the model-visible tool schema
nor the provider query/result. The only additions are small host-only `_meta` and a
separately fetched, cacheable `ui://` resource.
