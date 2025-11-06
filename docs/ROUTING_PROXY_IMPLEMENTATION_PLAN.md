# CascadeFlow Routing Proxy - Implementation Plan

**Date:** 2025-10-29
**Status:** Detailed Technical Roadmap
**Version:** v0.3.0 MVP (Phase 1)

---

## Overview

This document provides a detailed, step-by-step implementation plan for the CascadeFlow Routing Proxy MVP (Phase 1), focusing on Anthropic API compatibility with auto-cascade routing.

**Goal:** Self-hosted proxy that acts as drop-in replacement for Anthropic API with 40-80% automatic cost savings.

---

## Phase 1: MVP Implementation (v0.3.0)

**Timeline:** 2-3 weeks
**Priority:** HIGH

### Milestone 1: Project Structure & Dependencies (Days 1-2)

#### 1.1 Create Directory Structure

```
cascadeflow/
├── proxy/                    # NEW
│   ├── __init__.py
│   ├── server.py            # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── anthropic.py     # /v1/messages endpoint
│   │   └── health.py        # /health, /metrics
│   ├── models/
│   │   ├── __init__.py
│   │   ├── anthropic.py     # Pydantic models for Anthropic API
│   │   └── config.py        # Proxy configuration models
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py          # API key validation
│   │   └── logging.py       # Request/response logging
│   ├── cascade/
│   │   ├── __init__.py
│   │   └── router.py        # Cascade routing logic
│   └── cli.py               # CLI commands
├── tests/
│   └── proxy/               # NEW
│       ├── test_anthropic_endpoint.py
│       ├── test_cascade_routing.py
│       └── test_integration.py
└── setup.py                 # Update with proxy dependencies
```

**Validation:**
- [ ] Directory structure created
- [ ] `__init__.py` files in place
- [ ] Imports work (`from cascadeflow.proxy import server`)

#### 1.2 Add Dependencies

Update `setup.py` / `pyproject.toml`:

```python
# Add to install_requires
dependencies = [
    # Existing
    "anthropic>=0.28.0",
    "openai>=1.0.0",
    "pydantic>=2.0.0",

    # NEW for proxy
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pyyaml>=6.0.0",
    "python-dotenv>=1.0.0",
    "prometheus-client>=0.19.0",  # For metrics
]

# Add extras for proxy
extras_require = {
    "proxy": [
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pyyaml>=6.0.0",
        "prometheus-client>=0.19.0",
    ],
    # ... existing extras
}
```

**Validation:**
- [ ] `pip install -e .[proxy]` works
- [ ] All dependencies install without errors
- [ ] Can import `fastapi`, `uvicorn`, `pyyaml`

---

### Milestone 2: Configuration System (Days 2-3)

#### 2.1 Configuration Models

Create `cascadeflow/proxy/models/config.py`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

class CascadeRule(BaseModel):
    """Configuration for cascade routing"""
    request_model: str = Field(..., description="Model name in incoming request")
    draft_model: str = Field(..., description="Cheaper draft model to try first")
    verifier_model: str = Field(..., description="Expensive verifier model for escalation")
    quality_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Confidence threshold")

class ServerConfig(BaseModel):
    """Server configuration"""
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    workers: int = Field(1, description="Number of worker processes")
    log_level: str = Field("info", description="Logging level")

class AuthMode(str, Enum):
    """Authentication modes"""
    NONE = "none"
    API_KEY = "api_key"
    PASS_THROUGH = "pass_through"

class AuthConfig(BaseModel):
    """Authentication configuration"""
    mode: AuthMode = AuthMode.NONE
    api_keys: List[str] = Field(default_factory=list, description="Valid API keys")

class ProxyConfig(BaseModel):
    """Root proxy configuration"""
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    cascade_rules: List[CascadeRule] = Field(default_factory=list)
    api_keys: Dict[str, str] = Field(default_factory=dict, description="Provider API keys")

    @classmethod
    def from_yaml(cls, path: str) -> 'ProxyConfig':
        """Load configuration from YAML file"""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> 'ProxyConfig':
        """Load configuration from environment variables"""
        import os
        return cls(
            api_keys={
                "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
                "openai": os.getenv("OPENAI_API_KEY", ""),
                "groq": os.getenv("GROQ_API_KEY", ""),
            }
        )
```

#### 2.2 Default Configuration File

Create `cascadeflow-proxy.example.yaml`:

```yaml
# CascadeFlow Proxy Configuration Example
# Copy to cascadeflow-proxy.yaml and customize

server:
  host: 0.0.0.0
  port: 8000
  workers: 1
  log_level: info

auth:
  mode: none  # Options: none, api_key, pass_through
  api_keys: []  # Add your proxy API keys here

cascade_rules:
  # Anthropic cascade: Sonnet → Haiku
  - request_model: "claude-3-5-sonnet-20241022"
    draft_model: "claude-3-5-haiku-20241022"
    verifier_model: "claude-3-5-sonnet-20241022"
    quality_threshold: 0.7

  # Anthropic cascade: Opus → Sonnet
  - request_model: "claude-3-opus-20240229"
    draft_model: "claude-3-5-sonnet-20241022"
    verifier_model: "claude-3-opus-20240229"
    quality_threshold: 0.75

api_keys:
  # Load from environment variables (recommended)
  anthropic: ${ANTHROPIC_API_KEY}
  openai: ${OPENAI_API_KEY}
  groq: ${GROQ_API_KEY}
```

**Validation:**
- [ ] `ProxyConfig.from_yaml()` loads config correctly
- [ ] `ProxyConfig.from_env()` reads environment variables
- [ ] Validation errors on invalid config (e.g., quality_threshold > 1.0)
- [ ] Default config file provided

---

### Milestone 3: Anthropic API Models (Days 3-4)

#### 3.1 Request/Response Models

Create `cascadeflow/proxy/models/anthropic.py`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum

class MessageRole(str, Enum):
    """Message role"""
    USER = "user"
    ASSISTANT = "assistant"

class ContentBlock(BaseModel):
    """Content block"""
    type: Literal["text"] = "text"
    text: str

class Message(BaseModel):
    """Message in conversation"""
    role: MessageRole
    content: str | List[ContentBlock]

class AnthropicRequest(BaseModel):
    """Anthropic /v1/messages request"""
    model: str
    messages: List[Message]
    max_tokens: int = Field(1024, ge=1, le=8192)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=0)
    system: Optional[str] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None

class Usage(BaseModel):
    """Token usage"""
    input_tokens: int
    output_tokens: int

class AnthropicResponse(BaseModel):
    """Anthropic /v1/messages response"""
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[ContentBlock]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Usage

class ErrorResponse(BaseModel):
    """Error response"""
    type: Literal["error"] = "error"
    error: Dict[str, Any]
```

**Validation:**
- [ ] Request parsing works with official Anthropic SDK requests
- [ ] Response format matches official Anthropic API exactly
- [ ] Validation errors for invalid requests

---

### Milestone 4: Cascade Routing Logic (Days 4-6)

#### 4.1 Cascade Router

Create `cascadeflow/proxy/cascade/router.py`:

```python
from typing import Optional
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.result import CascadeResult
from cascadeflow.proxy.models.config import CascadeRule

class CascadeRouter:
    """Routes requests through cascade logic"""

    def __init__(self, api_keys: dict):
        """
        Initialize router with API keys

        Args:
            api_keys: Dictionary of provider API keys (anthropic, openai, groq)
        """
        self.api_keys = api_keys
        self._agents_cache = {}  # Cache CascadeAgent instances

    def get_cascade_rule(
        self,
        requested_model: str,
        cascade_rules: list[CascadeRule]
    ) -> Optional[CascadeRule]:
        """
        Find cascade rule for requested model

        Args:
            requested_model: Model name from request
            cascade_rules: List of cascade rules from config

        Returns:
            Matching CascadeRule or None (pass-through)
        """
        for rule in cascade_rules:
            if rule.request_model == requested_model:
                return rule
        return None

    def get_or_create_agent(self, rule: CascadeRule) -> CascadeAgent:
        """
        Get cached CascadeAgent or create new one

        Args:
            rule: Cascade rule configuration

        Returns:
            CascadeAgent instance
        """
        cache_key = f"{rule.draft_model}|{rule.verifier_model}"

        if cache_key in self._agents_cache:
            return self._agents_cache[cache_key]

        # Parse model provider from name
        # Assume format: "claude-*" = anthropic, "gpt-*" = openai, "llama-*" = groq
        def get_provider(model_name: str) -> str:
            if model_name.startswith("claude"):
                return "anthropic"
            elif model_name.startswith("gpt"):
                return "openai"
            elif model_name.startswith("llama"):
                return "groq"
            else:
                return "anthropic"  # Default

        # Create agent
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name=rule.draft_model,
                    provider=get_provider(rule.draft_model),
                    quality_threshold=rule.quality_threshold,
                ),
                ModelConfig(
                    name=rule.verifier_model,
                    provider=get_provider(rule.verifier_model),
                    quality_threshold=0.95,  # Verifier should accept everything
                ),
            ],
            api_keys=self.api_keys,
        )

        self._agents_cache[cache_key] = agent
        return agent

    async def route(
        self,
        requested_model: str,
        messages: list,
        max_tokens: int,
        cascade_rules: list[CascadeRule],
        **kwargs
    ) -> CascadeResult:
        """
        Route request through cascade logic

        Args:
            requested_model: Model name from request
            messages: List of messages
            max_tokens: Max tokens to generate
            cascade_rules: Cascade rules from config
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            CascadeResult with response
        """
        # Find cascade rule
        rule = self.get_cascade_rule(requested_model, cascade_rules)

        if rule is None:
            # No cascade rule → pass-through to requested model
            # Create single-model agent
            from cascadeflow import CascadeAgent, ModelConfig

            provider = self._get_provider(requested_model)
            agent = CascadeAgent(
                models=[
                    ModelConfig(
                        name=requested_model,
                        provider=provider,
                    )
                ],
                api_keys=self.api_keys,
            )

            # Format messages for CascadeAgent
            prompt = self._format_messages_to_prompt(messages)

            # Run (no cascade)
            return await agent.run(prompt, max_tokens=max_tokens)

        # Cascade rule found → run cascade
        agent = self.get_or_create_agent(rule)

        # Format messages for CascadeAgent
        prompt = self._format_messages_to_prompt(messages)

        # Run cascade
        return await agent.run(prompt, max_tokens=max_tokens)

    def _get_provider(self, model_name: str) -> str:
        """Get provider from model name"""
        if model_name.startswith("claude"):
            return "anthropic"
        elif model_name.startswith("gpt"):
            return "openai"
        elif model_name.startswith("llama"):
            return "groq"
        else:
            return "anthropic"

    def _format_messages_to_prompt(self, messages: list) -> str:
        """
        Convert messages array to single prompt string

        TODO: This is simplified. Should preserve message structure.
        For MVP, concatenate user messages.
        """
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle content as string or list
            if isinstance(content, list):
                content = " ".join([
                    block.get("text", "")
                    for block in content
                    if block.get("type") == "text"
                ])

            if role == "user":
                prompt_parts.append(content)

        return "\n\n".join(prompt_parts)
```

**Validation:**
- [ ] Cascade rule matching works
- [ ] Agent caching works (same rule → same agent instance)
- [ ] Pass-through works when no rule matches
- [ ] Message formatting works

---

### Milestone 5: Anthropic Endpoint (Days 6-8)

#### 5.1 Route Handler

Create `cascadeflow/proxy/routes/anthropic.py`:

```python
from fastapi import APIRouter, HTTPException, Depends, Header
from cascadeflow.proxy.models.anthropic import (
    AnthropicRequest,
    AnthropicResponse,
    ContentBlock,
    Usage,
    ErrorResponse,
)
from cascadeflow.proxy.models.config import ProxyConfig
from cascadeflow.proxy.cascade.router import CascadeRouter
from typing import Optional
import uuid
import time

router = APIRouter()

# Global state (injected via dependency)
_cascade_router: Optional[CascadeRouter] = None
_proxy_config: Optional[ProxyConfig] = None

def get_cascade_router() -> CascadeRouter:
    """Dependency: Get cascade router"""
    if _cascade_router is None:
        raise HTTPException(500, "Cascade router not initialized")
    return _cascade_router

def get_proxy_config() -> ProxyConfig:
    """Dependency: Get proxy config"""
    if _proxy_config is None:
        raise HTTPException(500, "Proxy config not initialized")
    return _proxy_config

@router.post("/v1/messages", response_model=AnthropicResponse)
async def create_message(
    request: AnthropicRequest,
    router: CascadeRouter = Depends(get_cascade_router),
    config: ProxyConfig = Depends(get_proxy_config),
    x_api_key: Optional[str] = Header(None),
):
    """
    Anthropic-compatible /v1/messages endpoint

    Accepts requests in Anthropic Messages API format,
    routes through cascade logic, returns Anthropic-compatible response.
    """
    try:
        # TODO: Authentication (Phase 3)
        # if config.auth.mode == AuthMode.API_KEY:
        #     validate_api_key(x_api_key, config.auth.api_keys)

        # Check streaming (not supported in MVP)
        if request.stream:
            raise HTTPException(
                400,
                detail="Streaming not supported yet. Set stream=false."
            )

        # Route through cascade
        result = await router.route(
            requested_model=request.model,
            messages=[msg.model_dump() for msg in request.messages],
            max_tokens=request.max_tokens,
            cascade_rules=config.cascade_rules,
        )

        # Format response
        response = AnthropicResponse(
            id=f"msg_{uuid.uuid4().hex}",
            type="message",
            role="assistant",
            content=[
                ContentBlock(
                    type="text",
                    text=result.response,
                )
            ],
            model=request.model,  # Return requested model, not actual
            stop_reason="end_turn",
            usage=Usage(
                input_tokens=result.input_tokens or 0,
                output_tokens=result.output_tokens or 0,
            ),
        )

        return response

    except Exception as e:
        # Return Anthropic-compatible error
        raise HTTPException(
            status_code=500,
            detail={
                "type": "error",
                "error": {
                    "type": "internal_error",
                    "message": str(e),
                }
            }
        )
```

**Validation:**
- [ ] Endpoint accepts Anthropic SDK requests
- [ ] Response format matches Anthropic API exactly
- [ ] Cascade routing triggered correctly
- [ ] Error handling works

---

### Milestone 6: FastAPI Server (Days 8-10)

#### 6.1 Main Server Application

Create `cascadeflow/proxy/server.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from cascadeflow.proxy.models.config import ProxyConfig
from cascadeflow.proxy.cascade.router import CascadeRouter
from cascadeflow.proxy.routes import anthropic, health
import logging
import time

logger = logging.getLogger(__name__)

def create_app(config: ProxyConfig) -> FastAPI:
    """
    Create FastAPI application

    Args:
        config: Proxy configuration

    Returns:
        FastAPI app instance
    """
    app = FastAPI(
        title="CascadeFlow Routing Proxy",
        description="Intelligent AI routing proxy with automatic cost optimization",
        version="0.3.0",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize cascade router
    cascade_router = CascadeRouter(api_keys=config.api_keys)

    # Store in app state (for dependency injection)
    app.state.cascade_router = cascade_router
    app.state.proxy_config = config

    # Update route dependencies
    anthropic._cascade_router = cascade_router
    anthropic._proxy_config = config

    # Include routes
    app.include_router(anthropic.router, tags=["Anthropic"])
    app.include_router(health.router, tags=["Health"])

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"{request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Log response
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} "
            f"{response.status_code} {duration:.2f}ms"
        )

        # Add cascade metadata headers
        if hasattr(response, "headers"):
            # TODO: Extract from cascade result
            pass

        return response

    return app

def run_server(config: ProxyConfig):
    """
    Run proxy server

    Args:
        config: Proxy configuration
    """
    import uvicorn

    app = create_app(config)

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level,
        workers=config.server.workers,
    )
```

#### 6.2 Health/Metrics Endpoints

Create `cascadeflow/proxy/routes/health.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        version="0.3.0",
    )

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (TODO: Phase 3)"""
    return {
        "requests_total": 0,
        "requests_cascade": 0,
        "requests_passthrough": 0,
    }
```

**Validation:**
- [ ] Server starts without errors
- [ ] `/health` endpoint returns 200
- [ ] `/v1/messages` endpoint accessible
- [ ] CORS headers present
- [ ] Request logging works

---

### Milestone 7: CLI Tool (Days 10-11)

#### 7.1 CLI Commands

Create `cascadeflow/proxy/cli.py`:

```python
import click
import os
from pathlib import Path
from cascadeflow.proxy.models.config import ProxyConfig
from cascadeflow.proxy.server import run_server

@click.group()
def proxy():
    """CascadeFlow Routing Proxy commands"""
    pass

@proxy.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
@click.option("--log-level", default="info", help="Logging level")
def start(config, host, port, log_level):
    """Start CascadeFlow proxy server"""

    # Load configuration
    if config:
        click.echo(f"Loading config from: {config}")
        proxy_config = ProxyConfig.from_yaml(config)
    else:
        click.echo("No config file specified, loading from environment")
        proxy_config = ProxyConfig.from_env()

    # Override with CLI args
    proxy_config.server.host = host
    proxy_config.server.port = port
    proxy_config.server.log_level = log_level

    # Validate API keys
    if not proxy_config.api_keys.get("anthropic"):
        click.echo("Warning: ANTHROPIC_API_KEY not set", err=True)

    click.echo(f"Starting CascadeFlow proxy on {host}:{port}")
    click.echo(f"Cascade rules: {len(proxy_config.cascade_rules)}")

    # Run server
    run_server(proxy_config)

@proxy.command()
def init():
    """Initialize proxy configuration"""
    config_path = Path("cascadeflow-proxy.yaml")

    if config_path.exists():
        click.echo(f"Config file already exists: {config_path}", err=True)
        return

    # Copy example config
    example_config = """# CascadeFlow Proxy Configuration
server:
  host: 0.0.0.0
  port: 8000
  log_level: info

auth:
  mode: none

cascade_rules:
  - request_model: "claude-3-5-sonnet-20241022"
    draft_model: "claude-3-5-haiku-20241022"
    verifier_model: "claude-3-5-sonnet-20241022"
    quality_threshold: 0.7

api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
"""

    with open(config_path, "w") as f:
        f.write(example_config)

    click.echo(f"Created config file: {config_path}")
    click.echo("Edit the file and run: cascadeflow proxy start --config cascadeflow-proxy.yaml")

# Register with main CLI (if exists)
# In main cascadeflow CLI:
# @click.group()
# def cli():
#     pass
#
# cli.add_command(proxy)
```

**Update main CLI** (`cascadeflow/__main__.py` or similar):

```python
import click
from cascadeflow.proxy.cli import proxy

@click.group()
def cli():
    """CascadeFlow CLI"""
    pass

cli.add_command(proxy)

if __name__ == "__main__":
    cli()
```

**Validation:**
- [ ] `cascadeflow proxy start` works
- [ ] `cascadeflow proxy init` creates config file
- [ ] `--help` shows correct usage
- [ ] CLI errors handled gracefully

---

### Milestone 8: Integration Tests (Days 11-13)

#### 8.1 Anthropic SDK Integration Test

Create `tests/proxy/test_integration.py`:

```python
import pytest
import asyncio
from anthropic import Anthropic, AsyncAnthropic
from cascadeflow.proxy.models.config import ProxyConfig, CascadeRule
from cascadeflow.proxy.server import create_app
from fastapi.testclient import TestClient
import os

@pytest.fixture
def proxy_config():
    """Test proxy configuration"""
    return ProxyConfig(
        cascade_rules=[
            CascadeRule(
                request_model="claude-3-5-sonnet-20241022",
                draft_model="claude-3-5-haiku-20241022",
                verifier_model="claude-3-5-sonnet-20241022",
                quality_threshold=0.7,
            )
        ],
        api_keys={
            "anthropic": os.getenv("ANTHROPIC_API_KEY", "test-key"),
        }
    )

@pytest.fixture
def test_client(proxy_config):
    """Test client for proxy server"""
    app = create_app(proxy_config)
    return TestClient(app)

def test_health_endpoint(test_client):
    """Test health endpoint"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_anthropic_endpoint_basic(test_client):
    """Test basic /v1/messages request"""
    response = test_client.post(
        "/v1/messages",
        json={
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "What is 2+2?"}
            ],
            "max_tokens": 100,
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Validate response format
    assert data["type"] == "message"
    assert data["role"] == "assistant"
    assert "content" in data
    assert len(data["content"]) > 0
    assert data["content"][0]["type"] == "text"
    assert len(data["content"][0]["text"]) > 0
    assert data["model"] == "claude-3-5-sonnet-20241022"
    assert "usage" in data

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
def test_anthropic_sdk_integration(test_client, proxy_config):
    """
    Test with actual Anthropic SDK

    This validates that the proxy response format is 100% compatible
    with the official Anthropic SDK.
    """
    # Start test server
    # Note: In real tests, use pytest-asyncio and run server in background

    # Create Anthropic client pointing to proxy
    client = Anthropic(
        api_key="test-key",  # Proxy doesn't validate in MVP
        base_url="http://testserver",  # TestClient handles this
    )

    # Make request through SDK
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[
            {"role": "user", "content": "What is Python?"}
        ]
    )

    # Validate SDK can parse response
    assert message.role == "assistant"
    assert len(message.content) > 0
    assert message.content[0].text
    assert message.model == "claude-3-5-sonnet-20241022"
    assert message.usage.input_tokens > 0
    assert message.usage.output_tokens > 0

@pytest.mark.asyncio
async def test_cascade_routing(proxy_config):
    """Test that cascade routing actually works"""
    from cascadeflow.proxy.cascade.router import CascadeRouter

    router = CascadeRouter(api_keys=proxy_config.api_keys)

    # Route with cascade rule
    result = await router.route(
        requested_model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=100,
        cascade_rules=proxy_config.cascade_rules,
    )

    # Validate cascade result
    assert result.response
    assert result.draft_model == "claude-3-5-haiku-20241022"
    # Note: Acceptance depends on quality, so can't assert here

def test_streaming_not_supported(test_client):
    """Test that streaming returns error in MVP"""
    response = test_client.post(
        "/v1/messages",
        json={
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "stream": True,
        }
    )

    assert response.status_code == 400
    assert "streaming" in response.json()["detail"].lower()
```

**Validation:**
- [ ] All tests pass
- [ ] Anthropic SDK can parse responses
- [ ] Cascade routing works
- [ ] Error handling works

---

### Milestone 9: Documentation (Days 13-15)

#### 9.1 Quick Start Guide

Create `docs/proxy/quickstart.md`:

```markdown
# CascadeFlow Proxy - Quick Start

Get started with CascadeFlow Routing Proxy in 5 minutes.

## Installation

```bash
pip install cascadeflow[proxy]
```

## Setup

1. Set your API keys:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

2. Initialize configuration:
```bash
cascadeflow proxy init
```

This creates `cascadeflow-proxy.yaml`:
```yaml
cascade_rules:
  - request_model: "claude-3-5-sonnet-20241022"
    draft_model: "claude-3-5-haiku-20241022"
    verifier_model: "claude-3-5-sonnet-20241022"
    quality_threshold: 0.7

api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
```

3. Start the proxy:
```bash
cascadeflow proxy start
```

Server starts on `http://localhost:8000`

## Usage

### With Anthropic SDK (Python)

```python
from anthropic import Anthropic

# Point SDK to proxy instead of official API
client = Anthropic(
    api_key="your-key",  # Any key works in MVP
    base_url="http://localhost:8000"  # Proxy URL
)

# Use normally - automatic cost optimization!
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ]
)

print(message.content[0].text)
```

**What happens:**
1. Proxy receives request for Sonnet
2. Tries Haiku first (draft model)
3. If quality good → returns Haiku response (60% savings!)
4. If quality bad → escalates to Sonnet

**Result:** 40-80% cost savings automatically!

### With Claude Code

1. Configure Claude Code to use proxy:
```bash
export ANTHROPIC_BASE_URL="http://localhost:8000"
```

2. Use Claude Code normally - automatic savings!

## Monitoring

View logs:
```bash
cascadeflow proxy start --log-level debug
```

Check health:
```bash
curl http://localhost:8000/health
```

## Next Steps

- [Configuration Reference](configuration.md)
- [Claude Code Integration](claude-code.md)
- [Cost Savings Calculator](savings.md)
```

#### 9.2 Claude Code Integration Guide

Create `docs/proxy/claude-code.md`:

```markdown
# Integrating CascadeFlow Proxy with Claude Code

Save 40-80% on Claude Code costs with zero code changes.

## Setup

1. Install and start CascadeFlow Proxy:
```bash
pip install cascadeflow[proxy]
cascadeflow proxy start
```

2. Configure Claude Code to use proxy:
```bash
# Set proxy URL
export ANTHROPIC_BASE_URL="http://localhost:8000"

# Keep your API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

3. Use Claude Code normally!

## How It Works

Claude Code makes API calls to Anthropic's servers:
```
Claude Code → https://api.anthropic.com/v1/messages
```

With proxy:
```
Claude Code → http://localhost:8000/v1/messages (proxy)
              ↓
          Try Haiku (cheap)
              ↓
        Quality check
              ↓
     Good? → Return Haiku (60% savings!)
     Bad?  → Escalate to Sonnet
```

**Result:** Same experience, automatic cost optimization!

## Cost Savings Example

**Without proxy:**
- 1000 requests/month to Sonnet
- Avg 1K tokens/request
- Cost: ~$3.00/month

**With proxy (60% acceptance):**
- 600 requests use Haiku (accepted)
- 400 requests escalate to Sonnet
- Cost: ~$1.20/month

**Savings: 60%!**

## Monitoring

Check proxy logs to see cascade decisions:
```
INFO: POST /v1/messages
INFO: Draft accepted (confidence: 0.85) - saved 60%
INFO: POST /v1/messages
INFO: Draft rejected (confidence: 0.45) - escalated to verifier
```

## Advanced: Custom Rules

Edit `cascadeflow-proxy.yaml`:

```yaml
cascade_rules:
  # More aggressive savings (lower threshold)
  - request_model: "claude-3-5-sonnet-20241022"
    draft_model: "claude-3-5-haiku-20241022"
    verifier_model: "claude-3-5-sonnet-20241022"
    quality_threshold: 0.6  # Lower = more acceptance, higher savings
```

## Troubleshooting

**Issue:** Claude Code can't connect to proxy

**Solution:** Ensure proxy is running:
```bash
curl http://localhost:8000/health
```

**Issue:** Responses seem slower

**Solution:** First request is slower (cold start). Subsequent requests are fast.
```

**Validation:**
- [ ] Documentation complete and clear
- [ ] Examples tested and work
- [ ] All links valid
- [ ] Screenshots/diagrams added

---

### Milestone 10: Final Testing & Release (Days 15-16)

#### 10.1 End-to-End Testing

**Test scenarios:**

1. **Basic flow:**
   - [ ] Start proxy
   - [ ] Make request with Anthropic SDK
   - [ ] Verify response format
   - [ ] Verify cascade worked

2. **Cascade acceptance:**
   - [ ] Simple query (should accept Haiku)
   - [ ] Complex query (should escalate to Sonnet)
   - [ ] Verify cost savings

3. **Pass-through:**
   - [ ] Request model with no cascade rule
   - [ ] Verify passes through to requested model

4. **Error handling:**
   - [ ] Invalid request format
   - [ ] Missing API key
   - [ ] Provider API error

5. **Claude Code integration:**
   - [ ] Configure Claude Code to use proxy
   - [ ] Run simple coding task
   - [ ] Verify it works normally
   - [ ] Check proxy logs for cascade decisions

#### 10.2 Performance Testing

**Benchmark:**

```python
# benchmarks/proxy_performance.py
import asyncio
import time
from anthropic import AsyncAnthropic

async def benchmark_proxy():
    """Benchmark proxy performance"""
    client = AsyncAnthropic(
        api_key="test-key",
        base_url="http://localhost:8000"
    )

    queries = [
        "What is Python?",
        "Explain quantum computing",
        "What is 2+2?",
        # ... 50 queries
    ]

    start_time = time.time()

    tasks = [
        client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": q}]
        )
        for q in queries
    ]

    results = await asyncio.gather(*tasks)

    duration = time.time() - start_time

    print(f"Processed {len(queries)} queries in {duration:.2f}s")
    print(f"Average: {duration/len(queries):.2f}s per query")
    print(f"Throughput: {len(queries)/duration:.2f} queries/sec")

asyncio.run(benchmark_proxy())
```

**Target metrics:**
- [ ] Throughput: >10 queries/sec (single worker)
- [ ] Latency: <2s per query (including LLM call)
- [ ] Proxy overhead: <50ms

#### 10.3 Release Checklist

- [ ] All tests passing
- [ ] Documentation complete
- [ ] Examples tested
- [ ] Performance benchmarks acceptable
- [ ] README updated
- [ ] CHANGELOG created
- [ ] Version bumped to 0.3.0
- [ ] PyPI package built and tested
- [ ] GitHub release created
- [ ] Announcement prepared

---

## Success Criteria

### MVP Acceptance Criteria

**Functional:**
- [ ] `/v1/messages` endpoint 100% compatible with Anthropic SDK
- [ ] Auto-cascade working (Sonnet → Haiku)
- [ ] Pass-through working (no cascade rule)
- [ ] Error handling working

**Performance:**
- [ ] 40-60% cost savings in benchmarks
- [ ] Proxy overhead <50ms
- [ ] No crashes under load (100 concurrent requests)

**Integration:**
- [ ] Works with official Anthropic Python SDK
- [ ] Works with Claude Code (verified)
- [ ] Configuration via YAML working
- [ ] CLI tool working

**Documentation:**
- [ ] Quick start guide complete
- [ ] Claude Code integration guide complete
- [ ] API reference complete
- [ ] Examples working

**Quality:**
- [ ] >80% test coverage
- [ ] All integration tests passing
- [ ] No critical bugs
- [ ] Code reviewed

---

## Timeline Summary

| Week | Milestones | Key Deliverables |
|------|-----------|------------------|
| **Week 1** | M1-M4 | Project structure, config system, API models, cascade router |
| **Week 2** | M5-M8 | Anthropic endpoint, FastAPI server, CLI tool, integration tests |
| **Week 3** | M9-M10 | Documentation, final testing, release |

**Total:** 2-3 weeks for MVP

---

## Risk Mitigation

### High-Risk Items

1. **Anthropic API compatibility**
   - **Risk:** Response format doesn't match exactly
   - **Mitigation:** Integration tests with official SDK, continuous validation

2. **Performance overhead**
   - **Risk:** Proxy adds too much latency
   - **Mitigation:** Async/await, connection pooling, benchmarking

3. **Cascade logic complexity**
   - **Risk:** CascadeAgent.run() doesn't work well in proxy context
   - **Mitigation:** Thorough testing, message formatting validation

### Medium-Risk Items

1. **Configuration complexity**
   - **Risk:** Users struggle with YAML config
   - **Mitigation:** Good defaults, `cascadeflow proxy init`, clear docs

2. **Error handling**
   - **Risk:** Unexpected errors crash proxy
   - **Mitigation:** Comprehensive try/catch, graceful degradation

---

## Post-MVP (Phase 2 & 3)

**Phase 2: OpenAI Compatibility (v0.4.0)**
- `/v1/chat/completions` endpoint
- GPT-4 → GPT-4o-mini cascade
- Multi-provider support

**Phase 3: Production Features (v0.5.0)**
- Authentication
- Rate limiting
- Streaming
- Monitoring dashboard
- Docker deployment

---

## Conclusion

This implementation plan provides a clear, step-by-step roadmap to build the CascadeFlow Routing Proxy MVP in 2-3 weeks.

**Next step:** Begin Milestone 1 (Project Structure & Dependencies)

**Status:** READY FOR IMPLEMENTATION ✅
