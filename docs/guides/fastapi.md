# FastAPI Integration Guide

Complete guide to integrating CascadeFlow with FastAPI for production APIs.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Design](#api-design)
4. [Streaming Responses](#streaming-responses)
5. [Request Validation](#request-validation)
6. [Error Handling](#error-handling)
7. [Monitoring & Stats](#monitoring--stats)
8. [Deployment](#deployment)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

---

## Overview

FastAPI is a modern, fast web framework for building APIs with Python. It integrates perfectly with CascadeFlow for production AI applications.

### Why FastAPI + CascadeFlow?

- ✅ **Async/Await** - Native async support matches CascadeFlow
- ✅ **Type Safety** - Pydantic validation for requests/responses
- ✅ **Auto Docs** - Interactive API documentation (Swagger/ReDoc)
- ✅ **Performance** - High throughput for AI workloads
- ✅ **Streaming** - SSE support for real-time responses
- ✅ **Production Ready** - Built-in features for deployment

---

## Quick Start

### Installation

```bash
pip install cascadeflow[all] fastapi uvicorn sse-starlette
```

### Minimal Example

```python
from fastapi import FastAPI
from cascadeflow import CascadeAgent, ModelConfig

app = FastAPI()
agent = None

@app.on_event("startup")
async def startup():
    global agent
    agent = CascadeAgent(models=[
        ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig("gpt-4o", provider="openai", cost=0.00625),
    ])

@app.post("/query")
async def query(text: str, max_tokens: int = 100):
    result = await agent.run(text, max_tokens=max_tokens)
    return {
        "content": result.content,
        "model": result.model_used,
        "cost": result.total_cost
    }
```

**Run:**
```bash
uvicorn main:app --reload
```

**Test:**
```bash
curl -X POST "http://localhost:8000/query?text=What%20is%20AI?&max_tokens=100"
```

---

## API Design

### RESTful Endpoints

**Standard pattern:**
```
POST   /api/query          # Non-streaming query
GET    /api/query/stream   # Streaming query (SSE)
GET    /api/stats          # Usage statistics
GET    /health             # Health check
```

### Request/Response Models

```python
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    max_tokens: int = Field(default=100, ge=1, le=4000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    force_direct: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Explain quantum computing",
                "max_tokens": 200,
                "temperature": 0.7
            }
        }

class QueryResponse(BaseModel):
    content: str
    model_used: str
    cost: float
    latency_ms: float
    cascaded: bool
    draft_accepted: Optional[bool] = None
```

### Endpoint Implementation

```python
@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """Process a query and return complete response."""
    
    result = await agent.run(
        query=request.query,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        force_direct=request.force_direct
    )
    
    return QueryResponse(
        content=result.content,
        model_used=result.model_used,
        cost=result.total_cost,
        latency_ms=result.latency_ms,
        cascaded=result.cascaded or False,
        draft_accepted=result.draft_accepted
    )
```

---

## Streaming Responses

### Server-Sent Events (SSE)

FastAPI supports streaming with SSE for real-time responses:

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/api/query/stream")
async def stream_query(
    query: str = Query(..., min_length=1),
    max_tokens: int = Query(100, ge=1, le=4000)
):
    """Stream response as Server-Sent Events."""
    
    async def event_generator():
        async for event in agent.text_streaming_manager.stream(
            query=query,
            max_tokens=max_tokens
        ):
            # Format as SSE
            event_data = {
                "type": event.type.value,
                "content": event.content,
                "data": event.data or {}
            }
            yield f"data: {json.dumps(event_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
```

### Client-Side Consumption

**JavaScript:**
```javascript
const eventSource = new EventSource(
    'http://localhost:8000/api/query/stream?query=Explain%20AI&max_tokens=200'
);

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'chunk') {
        // Append text chunk
        document.getElementById('response').textContent += data.content;
    } else if (data.type === 'complete') {
        // Response complete
        console.log('Cost:', data.data.result.total_cost);
        eventSource.close();
    }
};
```

**Python:**
```python
import httpx

async with httpx.AsyncClient() as client:
    async with client.stream(
        'GET',
        'http://localhost:8000/api/query/stream',
        params={'query': 'Explain AI', 'max_tokens': 200}
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if data['type'] == 'chunk':
                    print(data['content'], end='', flush=True)
```

**cURL:**
```bash
curl -N "http://localhost:8000/api/query/stream?query=Explain%20AI&max_tokens=200"
```

---

## Request Validation

### Pydantic Models

FastAPI uses Pydantic for automatic validation:

```python
from pydantic import BaseModel, Field, validator

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    max_tokens: int = Field(default=100, ge=1, le=4000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()
    
    @validator('temperature')
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError('Temperature must be between 0 and 2')
        return v
```

### Query Parameters

```python
@app.get("/api/query")
async def query_get(
    query: str = Query(..., min_length=1, max_length=500),
    max_tokens: int = Query(100, ge=1, le=4000),
    temperature: float = Query(0.7, ge=0.0, le=2.0)
):
    """GET endpoint with query parameters."""
    result = await agent.run(query, max_tokens=max_tokens, temperature=temperature)
    return {"content": result.content}
```

### Custom Validation

```python
from fastapi import HTTPException

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    # Custom business logic validation
    if len(request.query.split()) > 500:
        raise HTTPException(
            status_code=400,
            detail="Query too long (max 500 words)"
        )
    
    # Rate limiting check
    if not await rate_limiter.check(request.user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
    
    result = await agent.run(request.query)
    return result
```

---

## Error Handling

### Global Exception Handlers

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "validation_error", "detail": str(exc)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An error occurred"}
    )
```

### Endpoint-Level Error Handling

```python
@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    try:
        result = await agent.run(request.query)
        return {"content": result.content}
    
    except BudgetExceededError:
        raise HTTPException(
            status_code=402,
            detail="Budget exceeded"
        )
    
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
    
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timeout"
        )
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

---

## Monitoring & Stats

### Usage Statistics

```python
from datetime import datetime

stats = {
    "total_queries": 0,
    "total_cost": 0.0,
    "models_used": {},
    "start_time": datetime.now()
}

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    result = await agent.run(request.query)
    
    # Update stats
    stats["total_queries"] += 1
    stats["total_cost"] += result.total_cost
    stats["models_used"][result.model_used] = \
        stats["models_used"].get(result.model_used, 0) + 1
    
    return result

@app.get("/api/stats")
async def get_stats():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    avg_cost = stats["total_cost"] / stats["total_queries"] \
        if stats["total_queries"] > 0 else 0
    
    return {
        "total_queries": stats["total_queries"],
        "total_cost": stats["total_cost"],
        "avg_cost_per_query": avg_cost,
        "models_used": stats["models_used"],
        "uptime_seconds": uptime
    }
```

### Health Checks

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if agent is not None else "unhealthy",
        "version": "1.0.0",
        "agent_initialized": agent is not None,
        "uptime_seconds": (datetime.now() - stats["start_time"]).total_seconds()
    }

@app.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not ready")
    return {"status": "ready"}

@app.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}
```

### Prometheus Metrics (Optional)

```python
from prometheus_client import Counter, Histogram, generate_latest

query_counter = Counter('cascadeflow_queries_total', 'Total queries')
query_duration = Histogram('cascadeflow_query_duration_seconds', 'Query duration')
query_cost = Histogram('cascadeflow_query_cost_dollars', 'Query cost')

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    query_counter.inc()
    
    with query_duration.time():
        result = await agent.run(request.query)
    
    query_cost.observe(result.total_cost)
    return result

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

---

## Deployment

### Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and run:**
```bash
docker build -t cascadeflow-api .
docker run -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY cascadeflow-api
```

### Uvicorn Production

```bash
# Single worker
uvicorn main:app --host 0.0.0.0 --port 8000

# Multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Environment Variables

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    anthropic_api_key: Optional[str] = None
    daily_budget: float = 10.0
    rate_limit: int = 60
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Kubernetes

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cascadeflow-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cascadeflow-api
  template:
    metadata:
      labels:
        app: cascadeflow-api
    spec:
      containers:
      - name: api
        image: cascadeflow-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /liveness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

---

## Best Practices

### 1. Use Lifespan Management

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global agent
    agent = CascadeAgent(models=[...])
    yield
    # Shutdown
    # Cleanup if needed

app = FastAPI(lifespan=lifespan)
```

### 2. Enable CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Add Request Logging

```python
import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    return response
```

### 4. Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

@app.post("/api/query")
@limiter.limit("60/minute")
async def query_endpoint(request: Request, query_req: QueryRequest):
    result = await agent.run(query_req.query)
    return result
```

### 5. Background Tasks

```python
from fastapi import BackgroundTasks

def log_query_result(query: str, result: dict):
    # Log to database, analytics, etc.
    pass

@app.post("/api/query")
async def query_endpoint(
    request: QueryRequest,
    background_tasks: BackgroundTasks
):
    result = await agent.run(request.query)
    background_tasks.add_task(log_query_result, request.query, result.to_dict())
    return result
```

---

## Examples

### Complete Application

See [`examples/fastapi_integration.py`](../../examples/fastapi_integration.py) for a complete, production-ready example with:
- RESTful and streaming endpoints
- Request validation
- Error handling
- Statistics tracking
- Health checks
- Lifespan management

### Testing

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_query_endpoint():
    response = client.post(
        "/api/query",
        json={"query": "What is Python?", "max_tokens": 100}
    )
    assert response.status_code == 200
    assert "content" in response.json()

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

---

## Next Steps

- **Production Guide**: See [production.md](production.md) for deployment patterns
- **Custom Validation**: See [custom_validation.md](custom_validation.md) for quality control
- **Monitoring**: Add Prometheus, Grafana for metrics
- **Authentication**: Add JWT, OAuth2 for security

---

**Questions?** Check the [FAQ](faq.md) or open an issue on GitHub.