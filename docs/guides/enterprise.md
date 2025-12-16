# Enterprise Configuration Guide

cascadeflow provides enterprise-grade HTTP configuration for organizations that need custom SSL/TLS settings, proxy support, and corporate PKI integration.

## Zero-Config Auto-Detection

cascadeflow automatically detects enterprise configuration from standard environment variables:

| Environment Variable | Purpose |
|---------------------|---------|
| `HTTPS_PROXY`, `HTTP_PROXY` | Proxy server URL |
| `SSL_CERT_FILE` | Custom CA certificate path |
| `REQUESTS_CA_BUNDLE` | Alternative CA bundle path |
| `CURL_CA_BUNDLE` | Alternative CA bundle path |
| `NO_PROXY` | Hosts to bypass proxy |

**Just set these environment variables** - no code changes required.

## HttpConfig Options

For explicit configuration, use the `http_config` (Python) or `httpConfig` (TypeScript) parameter:

### Python

```python
from cascadeflow import CascadeAgent, ModelConfig, HttpConfig

agent = CascadeAgent(
    models=[
        ModelConfig(
            name="gpt-4o",
            provider="openai",
            cost=0.00625,
            http_config=HttpConfig(
                proxy="http://proxy.corp.example.com:8080",
                ca_cert_path="/path/to/corporate-ca.pem",
                verify_ssl=True,  # Default: True
                timeout=60.0,     # Request timeout in seconds
            ),
        ),
    ],
)
```

### TypeScript

```typescript
import { CascadeAgent, ModelConfig, HttpConfig } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      httpConfig: {
        proxy: 'http://proxy.corp.example.com:8080',
        caCertPath: '/path/to/corporate-ca.pem',
        verifySsl: true,  // Default: true
        timeout: 60000,   // Request timeout in milliseconds
        maxRetries: 2,    // Number of retries
      },
    },
  ],
});
```

## Configuration Options

| Option | Python | TypeScript | Description |
|--------|--------|------------|-------------|
| Proxy URL | `proxy` | `proxy` | HTTP/HTTPS proxy server URL |
| CA Certificate | `ca_cert_path` | `caCertPath` | Path to custom CA certificate (PEM format) |
| SSL Verification | `verify_ssl` | `verifySsl` | Enable/disable SSL verification (default: `True`) |
| Timeout | `timeout` | `timeout` | Request timeout (Python: seconds, TS: milliseconds) |
| Max Retries | - | `maxRetries` | Maximum retry attempts |

## Common Enterprise Scenarios

### Corporate Proxy Server

```python
# Python
http_config = HttpConfig(proxy="http://proxy.corp.example.com:8080")

# Or set environment variable
# export HTTPS_PROXY=http://proxy.corp.example.com:8080
```

```typescript
// TypeScript
const httpConfig: HttpConfig = {
  proxy: 'http://proxy.corp.example.com:8080',
};
```

### Custom CA Certificate (Corporate PKI)

```python
# Python
http_config = HttpConfig(ca_cert_path="/etc/ssl/certs/corporate-ca.pem")

# Or set environment variable
# export SSL_CERT_FILE=/etc/ssl/certs/corporate-ca.pem
```

```typescript
// TypeScript
const httpConfig: HttpConfig = {
  caCertPath: '/etc/ssl/certs/corporate-ca.pem',
};
```

### Proxy with Custom CA

```python
# Python
http_config = HttpConfig(
    proxy="https://proxy.corp.example.com:8443",
    ca_cert_path="/etc/ssl/certs/corporate-ca.pem",
)
```

```typescript
// TypeScript
const httpConfig: HttpConfig = {
  proxy: 'https://proxy.corp.example.com:8443',
  caCertPath: '/etc/ssl/certs/corporate-ca.pem',
};
```

### Development Only: Disable SSL Verification

**Warning**: Only use in development/testing environments.

```python
# Python - NOT recommended for production
http_config = HttpConfig(verify_ssl=False)
```

```typescript
// TypeScript - NOT recommended for production
const httpConfig: HttpConfig = {
  verifySsl: false,
};
```

## Provider Support

| Provider | Python | TypeScript | Notes |
|----------|--------|------------|-------|
| OpenAI | Full | Full | SDK-based, all options supported |
| Anthropic | Full | Full | SDK-based, all options supported |
| Groq | Full | Full | SDK-based, all options supported |
| OpenRouter | Full | Via env vars | Fetch-based, uses system proxy |
| Together | Full | Via env vars | Fetch-based, uses system proxy |
| HuggingFace | Full | Via env vars | Fetch-based, uses system proxy |
| Ollama | Local | Local | Local server, no proxy needed |
| vLLM | Local | Local | Self-hosted, configure server directly |

**Note**: For fetch-based TypeScript providers, configure proxy at the system level using environment variables.

## Troubleshooting

### SSL Certificate Errors

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution**: Add your corporate CA certificate:

```bash
export SSL_CERT_FILE=/path/to/corporate-ca.pem
```

Or configure explicitly in code with `ca_cert_path`/`caCertPath`.

### Proxy Connection Errors

```
ProxyError: Unable to connect to proxy
```

**Solution**: Verify proxy URL and ensure no authentication issues:

```bash
# Test proxy connection
curl -x http://proxy.corp.example.com:8080 https://api.openai.com
```

### Timeout Errors

```
TimeoutError: Request timed out
```

**Solution**: Increase timeout for slow networks:

```python
# Python
http_config = HttpConfig(timeout=120.0)  # 2 minutes
```

```typescript
// TypeScript
const httpConfig: HttpConfig = { timeout: 120000 };  // 2 minutes
```

## Security Best Practices

1. **Never disable SSL verification in production** - Use custom CA certificates instead
2. **Store certificates in secure locations** - Restrict file permissions
3. **Use environment variables for sensitive config** - Avoid hardcoding proxy credentials
4. **Rotate credentials regularly** - If using authenticated proxies
5. **Audit proxy logs** - Monitor for unusual access patterns

## Related Documentation

- [Providers Guide](./providers.md) - Provider configuration
- [Production Guide](./production.md) - Production deployment
- [Performance Guide](./performance.md) - Performance optimization
