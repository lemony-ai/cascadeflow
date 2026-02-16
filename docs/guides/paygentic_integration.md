# Paygentic Integration Guide

Use Paygentic with cascadeflow as an **explicit opt-in integration** for usage-based billing.

## Design Principles

- Not installed or enabled by default for TypeScript
- Never auto-activated in Python
- Fail-open reporting: billing API failures do not break model responses

## TypeScript Setup

Install explicitly:

```bash
pnpm add @cascadeflow/core @cascadeflow/paygentic
```

Configure client:

```ts
import { PaygenticClient, PaygenticUsageReporter } from '@cascadeflow/paygentic';

const paygentic = new PaygenticClient({
  apiKey: process.env.PAYGENTIC_API_KEY!,
  merchantId: process.env.PAYGENTIC_MERCHANT_ID!,
  billableMetricId: process.env.PAYGENTIC_BILLABLE_METRIC_ID!,
  // sandbox: true,
});

const reporter = new PaygenticUsageReporter(paygentic, {
  quantityMode: 'tokens', // 'tokens' | 'cost_usd' | 'requests'
  // costScale: 1_000_000, // only used for cost_usd mode
});

await reporter.reportProxyUsage({
  customerId: 'cust_123',
  requestId: 'req_456',
  result: {
    provider: 'openai',
    model: 'gpt-5-mini',
    usage: { inputTokens: 120, outputTokens: 80, totalTokens: 200 },
    cost: 0.0013,
    latencyMs: 95,
  },
  metadata: { app: 'my-agent' },
});
```

## Python Setup

No auto wiring. You explicitly import and create the integration objects:

```python
from cascadeflow.integrations.paygentic import (
    PaygenticClient,
    PaygenticConfig,
    PaygenticUsageReporter,
)

config = PaygenticConfig(
    api_key="...",
    merchant_id="...",
    billable_metric_id="...",
    sandbox=False,
)

client = PaygenticClient(config)
reporter = PaygenticUsageReporter(
    client,
    quantity_mode="tokens",
    # cost_scale=1_000_000,  # only used for cost_usd mode
)

# Example with a proxy-style result object
await reporter.report_proxy_result(
    result=proxy_result,
    customer_id="cust_123",
    request_id="req_456",
    metadata={"app": "my-agent"},
)
```

You can also load config from env vars:

```bash
export PAYGENTIC_API_KEY="..."
export PAYGENTIC_MERCHANT_ID="..."
export PAYGENTIC_BILLABLE_METRIC_ID="..."
```

```python
from cascadeflow.integrations.paygentic import PaygenticClient, PaygenticConfig

client = PaygenticClient(PaygenticConfig.from_env())
```

## Lifecycle APIs (Both Runtimes)

Both integrations support:

- `createCustomer(...)`
- `createSubscription(...)`
- `createUsageEvent(...)`

Use these when you want cascadeflow to handle customer/subscription orchestration in your billing flow.

For customer creation, include `name` and an `address` object with at least:
`line1`, `city`, `country`, and `postalCode`.

## Quantity Modes

Choose what your meter tracks:

- `tokens`: total tokens per request
- `cost_usd`: request cost scaled into integer units (default scale: `1_000_000`)
- `requests`: one unit per completed request

Paygentic validates `quantity` as an integer. For `cost_usd`, cascadeflow scales the USD
cost into integer units before sending.

## Proxy Wrapping (Python)

For proxy/gateway flows, use `PaygenticProxyService` to report usage after successful proxy handling:

```python
from cascadeflow.proxy import ProxyService
from cascadeflow.integrations.paygentic import PaygenticProxyService

billing_proxy = PaygenticProxyService(
    service=proxy_service,
    reporter=reporter,
    # report_in_background=True is the default and avoids user-facing latency.
    # Set False if you require synchronous billing write confirmation.
    report_in_background=True,
)

result = await billing_proxy.handle(proxy_request)
```

The wrapper looks for `x-cascadeflow-customer-id` by default.
Reporting runs in the background by default, so request latency remains focused on
model execution rather than billing I/O.

## Notes

- Reporting is intentionally fail-open to preserve runtime stability.
- Use deterministic idempotency keys to prevent duplicate usage charges on retries.
- Keep raw prompt/response text out of billing metadata unless needed.
