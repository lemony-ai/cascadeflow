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

mcp = create_mcp_server(agent, knowledge_resolver=resolve_knowledge)

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

An interactive routing panel is a useful second layer, not part of the routing
critical path. The standard [MCP Apps extension](https://modelcontextprotocol.io/extensions/apps/overview)
can render a sandboxed `ui://` resource for model choice, knowledge-version display,
and savings/latency traces. Keep `cascadeflow_run` fully usable without that UI so
tool behavior remains portable across hosts. If a host needs product-specific UI
metadata, add a thin host adapter around the same tool and server-side logic rather
than forking cascadeflow's routing implementation.
