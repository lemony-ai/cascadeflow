import { describe, expect, it, vi } from 'vitest';

import {
  PaygenticClient,
  PaygenticUsageReporter,
  createIdempotencyKey,
} from '../src';

describe('@cascadeflow/paygentic', () => {
  it('creates deterministic idempotency keys', () => {
    const a = createIdempotencyKey('usage', 'cust_1', 'req_1', 42);
    const b = createIdempotencyKey('usage', 'cust_1', 'req_1', 42);
    const c = createIdempotencyKey('usage', 'cust_1', 'req_2', 42);

    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });

  it('sends usage event payload with auth + idempotency headers', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe('https://api.paygentic.test/v0/usage');
      expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer key_123');
      expect((init?.headers as Record<string, string>)['Idempotency-Key']).toBe('idem_1');

      const body = JSON.parse(String(init?.body));
      expect(body.customerId).toBe('cust_1');
      expect(body.merchantId).toBe('merchant_1');
      expect(body.properties[0].billableMetricId).toBe('metric_1');
      expect(body.properties[0].quantity).toBe(150);

      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    const client = new PaygenticClient(
      {
        apiKey: 'key_123',
        merchantId: 'merchant_1',
        billableMetricId: 'metric_1',
        baseUrl: 'https://api.paygentic.test',
      },
      fetchMock as unknown as typeof fetch
    );

    const response = await client.createUsageEvent({
      customerId: 'cust_1',
      quantity: 150,
      timestamp: '2026-02-16T20:00:00.000Z',
      idempotencyKey: 'idem_1',
      metadata: { source: 'test' },
    });

    expect(response).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('maps proxy result tokens into usage event', async () => {
    const client = {
      createIdempotencyKey: vi.fn(() => 'idem_from_reporter'),
      createUsageEvent: vi.fn(async () => ({ eventId: 'evt_1' })),
    } as unknown as PaygenticClient;

    const reporter = new PaygenticUsageReporter(client, { quantityMode: 'tokens' });
    const response = await reporter.reportProxyUsage({
      customerId: 'cust_42',
      requestId: 'req_42',
      result: {
        provider: 'openai',
        model: 'gpt-4o-mini',
        latencyMs: 12,
        cost: 0.001,
        usage: { inputTokens: 100, outputTokens: 50, totalTokens: 150 },
      },
    });

    expect(response).toEqual({ eventId: 'evt_1' });
    expect((client.createUsageEvent as any).mock.calls[0][0].quantity).toBe(150);
  });

  it('is fail-open by default in reporter', async () => {
    const client = {
      createIdempotencyKey: vi.fn(() => 'idem_1'),
      createUsageEvent: vi.fn(async () => {
        throw new Error('temporary outage');
      }),
    } as unknown as PaygenticClient;

    const reporter = new PaygenticUsageReporter(client, { quantityMode: 'requests' });
    const result = await reporter.reportProxyUsage({
      customerId: 'cust_1',
      requestId: 'req_1',
      result: { provider: 'openai', model: 'gpt-4o-mini' },
    });

    expect(result).toBeNull();
  });
});
