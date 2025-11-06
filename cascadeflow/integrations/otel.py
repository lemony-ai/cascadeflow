"""OpenTelemetry integration for cascadeflow metrics export.

This module provides OpenTelemetry-based metric export for production observability.
Exports cost, token, and latency metrics to any OpenTelemetry-compatible backend
(Grafana, Datadog, CloudWatch, Prometheus, etc.).

Key Features:
- Cost tracking per user/model/provider
- Token usage tracking (input + output)
- Latency histograms for performance monitoring
- Automatic dimension tagging (user, model, provider, tier)
- Compatible with all OpenTelemetry backends

Example:
    >>> from cascadeflow.integrations.otel import OpenTelemetryExporter
    >>> from cascadeflow import CascadeAgent
    >>>
    >>> # Initialize exporter
    >>> exporter = OpenTelemetryExporter(
    ...     endpoint="http://localhost:4318",  # OTLP HTTP endpoint
    ...     service_name="cascadeflow-prod"
    ... )
    >>>
    >>> # Use with CascadeAgent
    >>> agent = CascadeAgent(
    ...     models=[...],
    ...     telemetry_exporter=exporter
    ... )
    >>>
    >>> # Metrics are automatically exported
    >>> response = await agent.run("Hello", user_id="user123")
    >>> # → Cost metric exported to Grafana
    >>> # → Token metric exported to Grafana
    >>> # → Latency metric exported to Grafana
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricDimensions:
    """Dimensions for metric tagging.

    These dimensions allow filtering and grouping metrics by:
    - User (track costs per user)
    - Model (compare model performance)
    - Provider (compare provider performance)
    - Tier (compare free vs pro users)
    - Domain (compare domain-specific performance)
    """

    user_id: Optional[str] = None
    user_tier: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    domain: Optional[str] = None

    def to_attributes(self) -> dict[str, str]:
        """Convert dimensions to OpenTelemetry attributes."""
        attrs = {}
        if self.user_id:
            attrs["user.id"] = self.user_id
        if self.user_tier:
            attrs["user.tier"] = self.user_tier
        if self.model:
            attrs["model.name"] = self.model
        if self.provider:
            attrs["provider.name"] = self.provider
        if self.domain:
            attrs["query.domain"] = self.domain
        return attrs


@dataclass
class cascadeflowMetrics:
    """Metric values for a single cascadeflow execution.

    Contains all the metrics we want to export:
    - Cost (in USD)
    - Tokens (input + output)
    - Latency (in milliseconds)
    - Dimensions (user, model, provider, etc.)
    """

    cost: float
    tokens_input: int
    tokens_output: int
    latency_ms: float
    dimensions: MetricDimensions = field(default_factory=MetricDimensions)

    @property
    def tokens_total(self) -> int:
        """Total tokens (input + output)."""
        return self.tokens_input + self.tokens_output


class OpenTelemetryExporter:
    """OpenTelemetry-based metrics exporter.

    Exports cascadeflow metrics to any OpenTelemetry-compatible backend:
    - Grafana Cloud
    - Datadog
    - AWS CloudWatch
    - Prometheus
    - Honeycomb
    - New Relic
    - And more...

    Metrics Exported:
    1. cascadeflow.cost.total - Total cost in USD (Counter)
    2. cascadeflow.tokens.input - Input tokens (Counter)
    3. cascadeflow.tokens.output - Output tokens (Counter)
    4. cascadeflow.latency - Request latency in ms (Histogram)

    All metrics include dimensions:
    - user.id (if provided)
    - user.tier (if provided)
    - model.name
    - provider.name
    - query.domain (if provided)

    Example:
        >>> exporter = OpenTelemetryExporter(
        ...     endpoint="http://localhost:4318",
        ...     service_name="my-app"
        ... )
        >>>
        >>> # Record a metric
        >>> exporter.record(cascadeflowMetrics(
        ...     cost=0.001,
        ...     tokens_input=100,
        ...     tokens_output=200,
        ...     latency_ms=1500,
        ...     dimensions=MetricDimensions(
        ...         user_id="user123",
        ...         user_tier="pro",
        ...         model="gpt-4o-mini",
        ...         provider="openai"
        ...     )
        ... ))
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        service_name: str = "cascadeflow",
        environment: Optional[str] = None,
        enabled: bool = True,
    ):
        """Initialize OpenTelemetry exporter.

        Args:
            endpoint: OTLP HTTP endpoint (e.g., http://localhost:4318)
                     If None, reads from OTEL_EXPORTER_OTLP_ENDPOINT env var
            service_name: Service name for metrics (default: "cascadeflow")
            environment: Environment name (e.g., "prod", "staging")
                        If None, reads from ENVIRONMENT env var
            enabled: Enable/disable metric export (default: True)
        """
        self.enabled = enabled
        self.service_name = service_name
        self.environment = environment or os.getenv("ENVIRONMENT", "development")

        # Get endpoint from parameter or environment
        self.endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

        if not self.endpoint and self.enabled:
            logger.warning(
                "OpenTelemetry endpoint not configured. "
                "Set OTEL_EXPORTER_OTLP_ENDPOINT or pass endpoint parameter. "
                "Metrics will not be exported."
            )
            self.enabled = False

        # Initialize OpenTelemetry (lazy - only if opentelemetry is installed)
        self._meter = None
        self._metrics = {}

        if self.enabled:
            self._initialize_otel()

    def _initialize_otel(self):
        """Initialize OpenTelemetry SDK (lazy).

        This method tries to import and initialize OpenTelemetry.
        If opentelemetry-api is not installed, metrics export is disabled.
        """
        try:
            from opentelemetry import metrics
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource

            # Create resource with service name and environment
            resource = Resource(
                attributes={
                    SERVICE_NAME: self.service_name,
                    DEPLOYMENT_ENVIRONMENT: self.environment,
                }
            )

            # Create OTLP exporter
            otlp_exporter = OTLPMetricExporter(
                endpoint=f"{self.endpoint}/v1/metrics",
                timeout=10,
            )

            # Create metric reader (exports every 60 seconds)
            reader = PeriodicExportingMetricReader(
                otlp_exporter,
                export_interval_millis=60000,  # 60 seconds
            )

            # Create meter provider
            provider = MeterProvider(
                resource=resource,
                metric_readers=[reader],
            )

            # Set global meter provider
            metrics.set_meter_provider(provider)

            # Get meter for this library
            self._meter = metrics.get_meter("cascadeflow", version="0.2.0")

            # Create metrics
            self._metrics = {
                "cost": self._meter.create_counter(
                    name="cascadeflow.cost.total",
                    description="Total cost in USD",
                    unit="USD",
                ),
                "tokens_input": self._meter.create_counter(
                    name="cascadeflow.tokens.input",
                    description="Input tokens consumed",
                    unit="tokens",
                ),
                "tokens_output": self._meter.create_counter(
                    name="cascadeflow.tokens.output",
                    description="Output tokens generated",
                    unit="tokens",
                ),
                "latency": self._meter.create_histogram(
                    name="cascadeflow.latency",
                    description="Request latency in milliseconds",
                    unit="ms",
                ),
            }

            logger.info(
                f"OpenTelemetry exporter initialized: {self.endpoint} "
                f"(service={self.service_name}, env={self.environment})"
            )

        except ImportError as e:
            logger.warning(
                f"OpenTelemetry not installed ({e}). "
                "Metrics will not be exported. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            self.enabled = False

    def record(self, metrics: cascadeflowMetrics):
        """Record metrics to OpenTelemetry.

        This method exports metrics to the configured OTLP endpoint.
        Metrics are batched and exported every 60 seconds.

        Args:
            metrics: cascadeflowMetrics to export
        """
        if not self.enabled or not self._meter:
            return

        try:
            # Get attributes from dimensions
            attributes = metrics.dimensions.to_attributes()

            # Record metrics
            self._metrics["cost"].add(metrics.cost, attributes)
            self._metrics["tokens_input"].add(metrics.tokens_input, attributes)
            self._metrics["tokens_output"].add(metrics.tokens_output, attributes)
            self._metrics["latency"].record(metrics.latency_ms, attributes)

            logger.debug(
                f"Recorded metrics: cost=${metrics.cost:.4f}, "
                f"tokens={metrics.tokens_total}, "
                f"latency={metrics.latency_ms:.0f}ms "
                f"(user={metrics.dimensions.user_id}, model={metrics.dimensions.model})"
            )

        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")

    def flush(self):
        """Force flush metrics to backend.

        Normally metrics are exported every 60 seconds.
        Call this method to force immediate export (useful for testing).
        """
        if not self.enabled or not self._meter:
            return

        try:
            # Force flush via meter provider
            from opentelemetry import metrics

            provider = metrics.get_meter_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush()
                logger.debug("Forced flush of metrics to OpenTelemetry backend")
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")

    def shutdown(self):
        """Shutdown OpenTelemetry exporter.

        Call this when your application is shutting down to ensure
        all metrics are exported before exit.
        """
        if not self.enabled or not self._meter:
            return

        try:
            from opentelemetry import metrics

            provider = metrics.get_meter_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()
                logger.info("OpenTelemetry exporter shutdown complete")
        except Exception as e:
            logger.error(f"Failed to shutdown OpenTelemetry: {e}")


# Convenience function for creating exporter from environment variables
def create_exporter_from_env() -> Optional[OpenTelemetryExporter]:
    """Create OpenTelemetry exporter from environment variables.

    Reads configuration from:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP HTTP endpoint (required)
    - OTEL_SERVICE_NAME: Service name (default: "cascadeflow")
    - ENVIRONMENT: Environment name (default: "development")
    - OTEL_ENABLED: Enable/disable export (default: "true")

    Returns:
        OpenTelemetryExporter if configured, None otherwise

    Example:
        >>> # Set environment variables
        >>> os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        >>> os.environ["OTEL_SERVICE_NAME"] = "my-app"
        >>>
        >>> # Create exporter
        >>> exporter = create_exporter_from_env()
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return None

    service_name = os.getenv("OTEL_SERVICE_NAME", "cascadeflow")
    environment = os.getenv("ENVIRONMENT", "development")
    enabled = os.getenv("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")

    return OpenTelemetryExporter(
        endpoint=endpoint,
        service_name=service_name,
        environment=environment,
        enabled=enabled,
    )
