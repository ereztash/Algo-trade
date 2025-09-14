import yaml
import logging
import asyncio
from typing import Dict
from uuid import uuid4

from ibkr_client import IBKRMarketClient, IBKRExecClient
from kafka_adapter import KafkaAdapter
from storage_writer import StorageWriter
from pacing_manager import PacingManager
from qa_monitors import NTPGuard, CompletenessGate, FreshnessMonitor
from tddi_engine import KappaEngine, StateManager
from order_plane import run_order_plane
from data_plane import run_data_plane
from strategy_loop import run_strategy_loop
from shared.contracts import BarEvent, TickEvent, OrderIntent
from shared.metrics import init_metrics_exporter
from shared.logger import init_structured_logger
from shared.errors import IBKRError

def main():
    """
    נקודת הכניסה הראשית של המערכת.
    מבצע אתחול של כל השירותים, המודולים והקונקשנים, ומפעיל את לולאות הפעולה המרכזיות.
    """
    try:
        # 0) אתחול על - תצורה, שירותים, בריאות
        print("Initializing system components...")
        cfg = load_yaml("settings.yaml")
        pacing_tbl = load_yaml("pacing.yaml")
        universe = load_yaml("assets_universe.yaml")

        time_svc = init_time_service()
        metrics = init_metrics_exporter()
        logger = init_structured_logger()

        bus = KafkaAdapter(cfg["bus"])
        store = StorageWriter(cfg["db"])
        pm = PacingManager(pacing_tbl)
        
        ntp_guard = NTPGuard(cfg["qa"]["ntp_drift_ms"])
        comp_gate = CompletenessGate(cfg["qa"]["target_completeness"])
        fresh_mon = FreshnessMonitor(cfg["sla"]["market_rt_p95_ms"])
        
        ofi_calc = OFICalculator(cfg["ofi"])
        kappa = KappaEngine(cfg["tddi"])
        tddi_sm = StateManager(cfg["tddi"])
        
        ib_mkt = IBKRMarketClient(cfg["ibkr"]["market"])
        ib_exec = IBKRExecClient(cfg["ibkr"]["exec"])

        assert ib_mkt.health().connected and ib_exec.health().connected
        
        logger.info("All services initialized and connected.")

        # 1) הפעלת מישורי הנתונים והאסטרטגיה בתהליכים נפרדים
        async def run_planes():
            # מריץ את מישור הנתונים ב-thread נפרד או תהליך אסינכרוני
            data_task = asyncio.create_task(run_data_plane(
                bus, store, pm, ntp_guard, fresh_mon, ofi_calc, kappa, tddi_sm
            ))
            
            # מריץ את לולאת האסטרטגיה ב-thread נפרד או תהליך אסינכרוני
            strategy_task = asyncio.create_task(run_strategy_loop(bus))

            # מריץ את מישור ההוראות ב-thread נפרד או תהליך אסינכרוני
            order_task = asyncio.create_task(run_order_plane(bus, ib_exec))
            
            await asyncio.gather(data_task, strategy_task, order_task)

        asyncio.run(run_planes())
    
    except Exception as e:
        logger.critical(f"A critical error occurred: {e}", exc_info=True)
        # כאן ניתן להוסיף מנגנון התראה חיצוני (pager, email וכו')
        # ...
        
def load_yaml(filepath: str) -> Dict:
    """טוען קובץ YAML ומחזיר מילון"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def init_time_service():
    """שירות זמן - מקור אמת ל-UTC"""
    # Placeholder for a real-time service, e.g., connecting to an NTP server.
    # For now, it will use the system clock.
    import datetime
    return datetime.datetime

if __name__ == "__main__":
    main()
