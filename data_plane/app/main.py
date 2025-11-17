# main.py — אתחול כל הרכיבים המרכזיים של המערכת
from data_plane.config.utils import load_yaml
from data_plane.app.time_service import init_time_service
from data_plane.monitoring.metrics_exporter import init_metrics_exporter
from shared.logging import init_structured_logger
from data_plane.bus.kafka_adapter import KafkaAdapter
from data_plane.bus.topic_initializer import initialize_kafka_topics, get_kafka_config
from data_plane.storage.writer import StorageWriter
from data_plane.pacing.pacing_manager import PacingManager
from data_plane.qa.ntp_guard import NTPGuard
from data_plane.qa.completeness_gate import CompletenessGate
from data_plane.qa.freshness_monitor import FreshnessMonitor
from data_plane.normalization.ofi_from_quotes import OFICalculator
from data_plane.tddi.kappa_engine import KappaEngine
from data_plane.tddi.state_manager import StateManager
from data_plane.connectors.ibkr.client import IBKRMarketClient
from order_plane.broker.ibkr_exec_client import IBKRExecClient
from data_plane.app.orchestrator import run_data_plane
from order_plane.app.orchestrator import run_order_plane
from apps.strategy_loop.main import run_strategy

# Import validators from each plane
from data_plane.validation.message_validator import DataPlaneValidator
from order_plane.validation.message_validator import OrderPlaneValidator
from apps.strategy_loop.validation.message_validator import StrategyPlaneValidator

import asyncio


async def main_async():
    # Load configurations
    cfg        = load_yaml('data_plane/config/settings.yaml')
    pacing_tbl = load_yaml('data_plane/config/pacing.yaml')
    universe   = load_yaml('data_plane/config/assets_universe.yaml')
    topics     = load_yaml('contracts/topics.yaml')

    # Get Kafka configuration
    kafka_cfg  = get_kafka_config('data_plane/config/kafka.yaml')

    # Initialize core services
    time_svc   = init_time_service()
    metrics    = init_metrics_exporter()
    logger     = init_structured_logger()

    # Initialize Kafka Message Bus
    logger.info("Initializing Kafka Message Bus...")
    bus        = KafkaAdapter(kafka_cfg)

    # Create Kafka topics (if they don't exist)
    await initialize_kafka_topics(bus, 'data_plane/config/kafka.yaml')
    logger.info("Kafka topics initialized successfully")

    # Initialize validators for each plane
    data_validator     = DataPlaneValidator(strict_mode=False)  # Non-strict for production
    order_validator    = OrderPlaneValidator(strict_mode=False)
    strategy_validator = StrategyPlaneValidator(strict_mode=False)

    # Initialize other services
    store      = StorageWriter(cfg.get('db'))
    pm         = PacingManager(pacing_tbl)
    ntp_guard  = NTPGuard(cfg.get('qa', {}).get('ntp_drift_ms'))
    comp_gate  = CompletenessGate(cfg.get('qa', {}).get('target_completeness'))
    fresh_mon  = FreshnessMonitor(cfg.get('sla', {}).get('market_rt_p95_ms'))
    ofi_calc   = OFICalculator(cfg.get('ofi'))
    kappa      = KappaEngine(cfg.get('tddi'))
    tddi_sm    = StateManager(cfg.get('tddi'))

    # Initialize IBKR clients
    ib_mkt     = IBKRMarketClient(cfg.get('ibkr', {}).get('market'))
    ib_exec    = IBKRExecClient(cfg.get('ibkr', {}).get('exec'))

    logger.info("Starting all planes in async distributed mode...")
    logger.info("🚀 Data Plane: Produces to market_events, ofi_events")
    logger.info("🚀 Strategy Plane: Consumes market_events → Produces order_intents")
    logger.info("🚀 Order Plane: Consumes order_intents → Produces exec_reports")

    # Run all planes concurrently with async Kafka message bus
    await asyncio.gather(
        run_data_plane(universe, ib_mkt, bus, pm, tddi_sm, time_svc, ntp_guard, fresh_mon, ofi_calc, store, comp_gate, kappa, metrics, data_validator),
        run_order_plane(bus, ib_exec, logger, metrics, order_validator),
        run_strategy(bus, strategy_validator)
    )

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Shutting down.")


if __name__ == "__main__":
    main()
