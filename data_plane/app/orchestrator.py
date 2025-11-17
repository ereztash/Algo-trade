# data_plane/app/orchestrator.py — Orchestrator for the data plane (real-time + historical)
import asyncio
import logging
from uuid import uuid4
from typing import Dict, Any
from data_plane.connectors.ibkr.producers_rt import producer_rt
from data_plane.connectors.ibkr.producers_hist import producer_hist
from data_plane.normalization.normalize import normalize


logger = logging.getLogger(__name__)


def is_tick(ev: Dict[str, Any]) -> bool:
    """Check if event is a tick event."""
    return ev.get('event_type') == 'tick_event' or ('bid' in ev and 'ask' in ev)


def is_bar(ev: Dict[str, Any]) -> bool:
    """Check if event is a bar event."""
    return ev.get('event_type') == 'bar_event' or ('open' in ev and 'high' in ev)


async def run_data_plane(universe, ib_mkt, bus, pm, tddi_sm, time_svc, ntp_guard, fresh_mon, ofi_calc, store, comp_gate, kappa, metrics, validator):
    """
    Orchestrator for the data plane: real-time + historical processing.

    Flow:
    1. Consume raw market data from market_raw topic
    2. Normalize data into BarEvent/TickEvent
    3. Validate with schema validators
    4. Apply QA gates (NTP, freshness, completeness)
    5. Calculate OFI for tick events
    6. Publish validated events to market_events and ofi_events topics
    7. Store in database
    """
    logger.info("Data Plane started - consuming from 'market_raw' topic")

    # Spawn producers for real-time and historical data
    asyncio.create_task(producer_rt(universe, ib_mkt, bus, pm, tddi_sm))
    asyncio.create_task(producer_hist(universe, ib_mkt, bus, pm))

    # Consume raw -> normalize -> validate -> QA -> publish -> store -> TDDI
    async for raw in bus.consume(topic="market_raw"):
        ingest_id = uuid4()

        try:
            # Pacing per-endpoint
            endpoint = raw.get('endpoint', 'default')
            if not pm.allow(endpoint):
                pm.enqueue_retry(raw)
                continue

            # Normalization against contracts
            ev = normalize(raw, ingest_id)

            # Validate normalized event based on type
            if is_bar(ev):
                result = validator.validate_bar_event(ev, raise_on_error=False)
            elif is_tick(ev):
                result = validator.validate_tick_event(ev, raise_on_error=False)
            else:
                logger.warning(f"Unknown event type: {ev.get('event_type')}")
                await bus.publish_to_dlq("market_raw", raw, "Unknown event type")
                continue

            # If validation failed, skip this event (already sent to DLQ by validator)
            if not result.is_valid:
                logger.error(f"Validation failed: {result.errors}")
                metrics.inc("validation_failures")
                continue

            # Use validated data
            validated_ev = result.validated_data

            # QA: NTP Guard + Freshness
            ts_utc = validated_ev.timestamp if hasattr(validated_ev, 'timestamp') else None
            if ts_utc and not ntp_guard.accept(ts_utc):
                metrics.inc("ntp_rejects")
                continue

            if hasattr(validated_ev, '__dict__'):
                fresh_mon.observe(validated_ev)

            # OFI from Quotes/L2 (for TickEvent only)
            if is_tick(ev):
                ofi_ev = ofi_calc.on_tick(validated_ev)
                if ofi_ev:
                    # Validate OFI event before publishing
                    ofi_result = validator.validate_ofi_event(
                        ofi_ev if isinstance(ofi_ev, dict) else ofi_ev.__dict__,
                        raise_on_error=False
                    )
                    if ofi_result.is_valid:
                        store.write_ofi(ofi_result.validated_data)
                        # Publish validated OFI event to Kafka
                        await bus.publish(
                            "ofi_events",
                            ofi_result.validated_data.dict() if hasattr(ofi_result.validated_data, 'dict') else ofi_result.validated_data,
                            key=validated_ev.symbol if hasattr(validated_ev, 'symbol') else None
                        )

            # Storage with idempotency
            if is_bar(ev):
                store.write_bar(validated_ev)
            else:
                store.write_tick(validated_ev)

            # Publish validated event to Kafka for strategy consumption
            event_dict = validated_ev.dict() if hasattr(validated_ev, 'dict') else validated_ev
            await bus.publish(
                "market_events",
                event_dict,
                key=validated_ev.symbol if hasattr(validated_ev, 'symbol') else None
            )

            # Completeness panel update
            if hasattr(validated_ev, 'conid'):
                comp_gate.update(validated_ev)
                if comp_gate.below_target(asset=validated_ev.conid):
                    metrics.alert("completeness_drop", conid=validated_ev.conid)

            # Update kappa and trigger TDDI+hysteresis
            # panel_returns and news_counters need to be available
            # κ = kappa.compute(panel_returns(), news_counters())
            # prev_state = tddi_sm.state
            # tddi_sm.update(κ)
            # if tddi_sm.state != prev_state:
            #    rewire_rt_subscriptions(ib_mkt, tddi_sm.state)

        except Exception as e:
            logger.error(f"Error processing market event: {e}", exc_info=True)
            metrics.inc("processing_errors")
            await bus.publish_to_dlq("market_raw", raw, f"Processing error: {str(e)}")
            continue
