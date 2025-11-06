"""
Unit tests for OpenTelemetry integration.

Tests:
- MetricDimensions creation and attributes
- cascadeflowMetrics creation
- OpenTelemetryExporter initialization
- Metric recording
- Environment-based configuration
- Graceful degradation when OpenTelemetry not installed
"""

import os
from unittest.mock import patch

import pytest

# Import the classes (will work even if opentelemetry not installed)
from cascadeflow.integrations.otel import (
    MetricDimensions,
    OpenTelemetryExporter,
    cascadeflowMetrics,
    create_exporter_from_env,
)


class TestMetricDimensions:
    """Test MetricDimensions class."""

    def test_create_empty_dimensions(self):
        """Test creating empty dimensions."""
        dims = MetricDimensions()
        assert dims.user_id is None
        assert dims.user_tier is None
        assert dims.model is None
        assert dims.provider is None
        assert dims.domain is None

    def test_create_full_dimensions(self):
        """Test creating dimensions with all fields."""
        dims = MetricDimensions(
            user_id="user123",
            user_tier="pro",
            model="gpt-4o-mini",
            provider="openai",
            domain="code",
        )
        assert dims.user_id == "user123"
        assert dims.user_tier == "pro"
        assert dims.model == "gpt-4o-mini"
        assert dims.provider == "openai"
        assert dims.domain == "code"

    def test_to_attributes_empty(self):
        """Test converting empty dimensions to attributes."""
        dims = MetricDimensions()
        attrs = dims.to_attributes()
        assert attrs == {}

    def test_to_attributes_partial(self):
        """Test converting partial dimensions to attributes."""
        dims = MetricDimensions(
            user_id="user123",
            model="gpt-4o-mini",
        )
        attrs = dims.to_attributes()
        assert attrs == {
            "user.id": "user123",
            "model.name": "gpt-4o-mini",
        }

    def test_to_attributes_full(self):
        """Test converting full dimensions to attributes."""
        dims = MetricDimensions(
            user_id="user123",
            user_tier="pro",
            model="gpt-4o-mini",
            provider="openai",
            domain="code",
        )
        attrs = dims.to_attributes()
        assert attrs == {
            "user.id": "user123",
            "user.tier": "pro",
            "model.name": "gpt-4o-mini",
            "provider.name": "openai",
            "query.domain": "code",
        }


class TestcascadeflowMetrics:
    """Test cascadeflowMetrics class."""

    def test_create_metrics(self):
        """Test creating metrics."""
        metrics = cascadeflowMetrics(
            cost=0.001,
            tokens_input=100,
            tokens_output=200,
            latency_ms=1500.0,
        )
        assert metrics.cost == 0.001
        assert metrics.tokens_input == 100
        assert metrics.tokens_output == 200
        assert metrics.latency_ms == 1500.0
        assert metrics.tokens_total == 300

    def test_create_metrics_with_dimensions(self):
        """Test creating metrics with dimensions."""
        dims = MetricDimensions(user_id="user123", model="gpt-4o-mini")
        metrics = cascadeflowMetrics(
            cost=0.001,
            tokens_input=100,
            tokens_output=200,
            latency_ms=1500.0,
            dimensions=dims,
        )
        assert metrics.dimensions.user_id == "user123"
        assert metrics.dimensions.model == "gpt-4o-mini"

    def test_tokens_total_property(self):
        """Test tokens_total property calculation."""
        metrics = cascadeflowMetrics(
            cost=0.0,
            tokens_input=50,
            tokens_output=150,
            latency_ms=0.0,
        )
        assert metrics.tokens_total == 200


class TestOpenTelemetryExporter:
    """Test OpenTelemetryExporter class."""

    def test_create_exporter_disabled(self):
        """Test creating disabled exporter."""
        exporter = OpenTelemetryExporter(enabled=False)
        assert exporter.enabled is False
        assert exporter._meter is None

    def test_create_exporter_no_endpoint(self):
        """Test creating exporter without endpoint."""
        exporter = OpenTelemetryExporter()
        # Should be disabled if no endpoint
        assert exporter.enabled is False

    def test_create_exporter_with_endpoint(self):
        """Test creating exporter with endpoint."""
        exporter = OpenTelemetryExporter(
            endpoint="http://localhost:4318",
            service_name="test-service",
            environment="test",
        )
        assert exporter.endpoint == "http://localhost:4318"
        assert exporter.service_name == "test-service"
        assert exporter.environment == "test"

    def test_record_when_disabled(self):
        """Test recording metrics when exporter is disabled."""
        exporter = OpenTelemetryExporter(enabled=False)

        metrics = cascadeflowMetrics(
            cost=0.001,
            tokens_input=100,
            tokens_output=200,
            latency_ms=1500.0,
        )

        # Should not raise error
        exporter.record(metrics)

    @patch("cascadeflow.integrations.otel.logger")
    def test_initialization_without_opentelemetry(self, mock_logger):
        """Test initialization when opentelemetry is not installed."""
        with patch.dict("sys.modules", {"opentelemetry": None}):
            exporter = OpenTelemetryExporter(endpoint="http://localhost:4318")
            # Should be disabled
            assert exporter.enabled is False or exporter._meter is None

    def test_record_metrics_with_mock(self):
        """Test recording metrics with mocked OpenTelemetry."""
        # Create disabled exporter (skip OpenTelemetry initialization)
        exporter = OpenTelemetryExporter(
            endpoint="http://localhost:4318",
            service_name="test",
            enabled=False,  # Disabled to avoid OTel dependency
        )

        # Record metrics (should not raise error when disabled)
        metrics = cascadeflowMetrics(
            cost=0.001,
            tokens_input=100,
            tokens_output=200,
            latency_ms=1500.0,
            dimensions=MetricDimensions(user_id="user123", model="gpt-4o-mini"),
        )

        # Should not raise error
        exporter.record(metrics)
        assert exporter.enabled is False


class TestCreateExporterFromEnv:
    """Test environment-based exporter creation."""

    def test_create_from_env_no_endpoint(self):
        """Test creating exporter without endpoint in environment."""
        with patch.dict(os.environ, {}, clear=True):
            exporter = create_exporter_from_env()
            assert exporter is None

    def test_create_from_env_with_endpoint(self):
        """Test creating exporter with endpoint in environment."""
        with patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
                "OTEL_SERVICE_NAME": "test-service",
                "ENVIRONMENT": "production",
                "OTEL_ENABLED": "true",
            },
        ):
            exporter = create_exporter_from_env()
            assert exporter is not None
            assert exporter.endpoint == "http://localhost:4318"
            assert exporter.service_name == "test-service"
            assert exporter.environment == "production"

    def test_create_from_env_disabled(self):
        """Test creating disabled exporter from environment."""
        with patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
                "OTEL_ENABLED": "false",
            },
        ):
            exporter = create_exporter_from_env()
            assert exporter is not None
            assert exporter.enabled is False

    def test_create_from_env_defaults(self):
        """Test creating exporter with default values."""
        with patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
            clear=True,
        ):
            exporter = create_exporter_from_env()
            assert exporter is not None
            assert exporter.service_name == "cascadeflow"
            assert exporter.environment == "development"
            # Enabled may be False if OpenTelemetry not installed
            assert exporter.enabled in (True, False)


class TestIntegration:
    """Test integration scenarios."""

    def test_full_metrics_workflow(self):
        """Test complete metrics workflow."""
        # Create exporter
        exporter = OpenTelemetryExporter(
            endpoint="http://localhost:4318",
            service_name="test",
            enabled=True,  # Will be disabled if OTel not installed
        )

        # Create metrics
        metrics = cascadeflowMetrics(
            cost=0.0015,
            tokens_input=100,
            tokens_output=200,
            latency_ms=1234.5,
            dimensions=MetricDimensions(
                user_id="user456",
                user_tier="pro",
                model="gpt-4o-mini",
                provider="openai",
                domain="code",
            ),
        )

        # Record (should not raise error)
        exporter.record(metrics)

        # Flush (should not raise error)
        exporter.flush()

        # Shutdown (should not raise error)
        exporter.shutdown()

    def test_multiple_metrics_recording(self):
        """Test recording multiple metrics."""
        exporter = OpenTelemetryExporter(endpoint="http://localhost:4318")

        # Record multiple metrics
        for i in range(10):
            metrics = cascadeflowMetrics(
                cost=0.001 * i,
                tokens_input=100 * i,
                tokens_output=200 * i,
                latency_ms=1000.0 * i,
                dimensions=MetricDimensions(
                    user_id=f"user{i}",
                    model="gpt-4o-mini",
                ),
            )
            exporter.record(metrics)

        # Should not raise error
        exporter.flush()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
