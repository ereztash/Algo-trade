"""
HTTP server for exposing Prometheus metrics.

Provides /metrics endpoint that returns metrics in Prometheus exposition format.
Uses aiohttp for async HTTP serving.
"""

import logging
import asyncio
from typing import Optional

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY

from data_plane.monitoring.metrics_exporter import MetricsCollector


logger = logging.getLogger(__name__)


class MetricsServer:
    """
    HTTP server for exposing Prometheus metrics.

    Serves metrics on /metrics endpoint in Prometheus format.
    Supports health checks on /health and /readiness endpoints.
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        host: str = '0.0.0.0',
        port: int = 8000,
    ):
        """
        Initialize metrics server.

        Args:
            metrics_collector: MetricsCollector instance
            host: Server host (default: 0.0.0.0)
            port: Server port (default: 8000)
        """
        self.metrics_collector = metrics_collector
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None

        # Setup routes
        self.app.router.add_get('/metrics', self.metrics_handler)
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/readiness', self.readiness_handler)

        logger.info(f"Initialized MetricsServer on {host}:{port}")

    async def metrics_handler(self, request: web.Request) -> web.Response:
        """
        Handle /metrics endpoint.

        Returns metrics in Prometheus exposition format.
        """
        try:
            metrics_output = generate_latest(self.metrics_collector.registry)
            return web.Response(
                body=metrics_output,
                content_type=CONTENT_TYPE_LATEST,
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}", exc_info=True)
            return web.Response(
                status=500,
                text=f"Error generating metrics: {str(e)}",
            )

    async def health_handler(self, request: web.Request) -> web.Response:
        """
        Handle /health endpoint.

        Returns service health status.
        """
        return web.json_response({
            'status': 'healthy',
            'service': self.metrics_collector.service_name,
            'type': self.metrics_collector.service_type.value,
        })

    async def readiness_handler(self, request: web.Request) -> web.Response:
        """
        Handle /readiness endpoint.

        Returns service readiness status.
        """
        return web.json_response({
            'status': 'ready',
            'service': self.metrics_collector.service_name,
        })

    async def start(self) -> None:
        """Start the metrics server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

        logger.info(f"Metrics server started on http://{self.host}:{self.port}/metrics")
        logger.info(f"Health endpoint available at http://{self.host}:{self.port}/health")

    async def stop(self) -> None:
        """Stop the metrics server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Metrics server stopped")

    async def run_forever(self) -> None:
        """Run the server indefinitely."""
        await self.start()
        try:
            # Keep running until cancelled
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Metrics server cancelled")
        finally:
            await self.stop()


# ============================================================================
# Convenience Functions
# ============================================================================

async def start_metrics_server(
    metrics_collector: MetricsCollector,
    host: str = '0.0.0.0',
    port: int = 8000,
) -> MetricsServer:
    """
    Start metrics server.

    Args:
        metrics_collector: MetricsCollector instance
        host: Server host
        port: Server port

    Returns:
        MetricsServer instance

    Example:
        >>> from data_plane.monitoring.metrics_exporter import init_metrics_exporter
        >>> metrics = init_metrics_exporter('data_plane')
        >>> server = await start_metrics_server(metrics, port=8000)
    """
    server = MetricsServer(metrics_collector, host, port)
    await server.start()
    return server


def run_metrics_server_sync(
    metrics_collector: MetricsCollector,
    host: str = '0.0.0.0',
    port: int = 8000,
) -> None:
    """
    Run metrics server synchronously (blocking).

    Args:
        metrics_collector: MetricsCollector instance
        host: Server host
        port: Server port

    Example:
        >>> from data_plane.monitoring.metrics_exporter import init_metrics_exporter
        >>> metrics = init_metrics_exporter('data_plane')
        >>> run_metrics_server_sync(metrics, port=8000)  # Blocks
    """
    async def run():
        server = MetricsServer(metrics_collector, host, port)
        await server.run_forever()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Metrics server interrupted")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Example usage
    import sys
    from data_plane.monitoring.metrics_exporter import init_metrics_exporter

    # Parse arguments
    service_type = sys.argv[1] if len(sys.argv) > 1 else 'data_plane'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    # Initialize metrics and server
    metrics = init_metrics_exporter(service_type)

    # Add some sample metrics
    if service_type == 'data_plane':
        metrics.inc('ticks_received', source='ibkr_rt', symbol='SPY')
        metrics.inc('bars_received', source='ibkr_hist', symbol='SPY', duration='1d')
        metrics.observe('data_freshness', 0.150, source='ibkr_rt', symbol='SPY')
        metrics.set('completeness_score', 0.95, symbol='SPY')
    elif service_type == 'order_plane':
        metrics.inc('orders_received', strategy='COMPOSITE', symbol='SPY')
        metrics.observe('total_fill_latency', 0.523, symbol='SPY')
    elif service_type == 'strategy_plane':
        metrics.set('portfolio_gross_exposure', 500000.0)
        metrics.set('pnl_total', 12500.50)
        metrics.set('regime_state', 1.0)  # Normal

    print(f"Starting {service_type} metrics server on port {port}...")
    print(f"Metrics available at: http://localhost:{port}/metrics")
    print(f"Health check at: http://localhost:{port}/health")
    print("Press Ctrl+C to stop")

    run_metrics_server_sync(metrics, port=port)
