"""Paygentic integration example (explicit opt-in).

Requirements:
    export PAYGENTIC_API_KEY="..."
    export PAYGENTIC_MERCHANT_ID="..."
    export PAYGENTIC_BILLABLE_METRIC_ID="..."

Run:
    python examples/integrations/paygentic_usage.py
"""

from __future__ import annotations

import asyncio

from cascadeflow.integrations.paygentic import PaygenticClient, PaygenticConfig, PaygenticUsageReporter
from cascadeflow.proxy.models import ProxyResult, ProxyUsage


async def main() -> None:
    config = PaygenticConfig.from_env()
    client = PaygenticClient(config)
    reporter = PaygenticUsageReporter(client, quantity_mode="tokens")

    result = ProxyResult(
        status_code=200,
        headers={},
        data={"ok": True},
        provider="openai",
        model="gpt-5-mini",
        latency_ms=123.0,
        usage=ProxyUsage(input_tokens=120, output_tokens=80, total_tokens=200),
        cost=0.0014,
    )

    response = await reporter.report_proxy_result(
        result=result,
        customer_id="cust_demo_123",
        request_id="req_demo_123",
        metadata={"environment": "dev", "app": "paygentic-example"},
    )

    print("Paygentic response:", response)


if __name__ == "__main__":
    asyncio.run(main())
