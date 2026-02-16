import { PaygenticClient, PaygenticUsageReporter } from '../src';

async function main() {
  const apiKey = process.env.PAYGENTIC_API_KEY;
  const merchantId = process.env.PAYGENTIC_MERCHANT_ID;
  const billableMetricId = process.env.PAYGENTIC_BILLABLE_METRIC_ID;

  if (!apiKey || !merchantId || !billableMetricId) {
    throw new Error('Missing PAYGENTIC_API_KEY, PAYGENTIC_MERCHANT_ID, or PAYGENTIC_BILLABLE_METRIC_ID');
  }

  const client = new PaygenticClient({
    apiKey,
    merchantId,
    billableMetricId,
  });

  const reporter = new PaygenticUsageReporter(client, { quantityMode: 'tokens' });

  const response = await reporter.reportProxyUsage({
    customerId: 'cust_demo_123',
    requestId: 'req_demo_123',
    result: {
      provider: 'openai',
      model: 'gpt-5-mini',
      usage: {
        inputTokens: 120,
        outputTokens: 70,
        totalTokens: 190,
      },
      cost: 0.0012,
      latencyMs: 180,
    },
    metadata: {
      environment: 'dev',
      app: 'quickstart-demo',
    },
  });

  console.log('Paygentic usage event response:', response);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
