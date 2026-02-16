# @cascadeflow/paygentic

Optional Paygentic billing integration for **cascadeflow**.

This package is intentionally integration-scoped and opt-in:
- Not required for `@cascadeflow/core`
- Not auto-enabled
- You explicitly create and use the Paygentic client/reporter

## Install

```bash
pnpm add @cascadeflow/core @cascadeflow/paygentic
```

## Quick Start (TypeScript)

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
});

await reporter.reportProxyUsage({
  customerId: 'cust_123',
  requestId: 'req_abc',
  result: {
    provider: 'openai',
    model: 'gpt-4o-mini',
    usage: { inputTokens: 120, outputTokens: 80, totalTokens: 200 },
    cost: 0.0013,
    latencyMs: 95,
  },
});
```

## Lifecycle Helpers

You can also call Paygentic APIs directly:

```ts
await paygentic.createCustomer({
  email: 'dev@example.com',
  name: 'Dev User',
  address: {
    line1: 'Main Street 1',
    city: 'Zurich',
    country: 'CH',
    postalCode: '8000',
  },
});

await paygentic.createSubscription({
  planId: 'plan_basic',
  name: 'cascadeflow starter',
  customerId: 'cust_123',
});
```

See `examples/basic-usage.ts` for a complete flow.
