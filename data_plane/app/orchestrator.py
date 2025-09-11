# data_plane/app/orchestrator.py — Orchestrator for the data plane (real-time + historical)
import asyncio
from uuid import uuid4
from data_plane.connectors.ibkr.producers_rt import producer_rt
from data_plane.connectors.ibkr.producers_hist import producer_hist
from data_plane.normalization.normalize import normalize
# Assuming other necessary imports for validators, is_tick, is_bar, etc.

async def run_data_plane(universe, ib_mkt, bus, pm, tddi_sm, time_svc, ntp_guard, fresh_mon, ofi_calc, store, comp_gate, kappa, metrics, validators):
  """
  Orchestrator for the data plane: real-time + historical processing.
  """
  # Spawn producers for real-time and historical data
  asyncio.create_task(producer_rt(universe, ib_mkt, bus, pm, tddi_sm))
  asyncio.create_task(producer_hist(universe, ib_mkt, bus, pm))

  # Consume raw -> normalize -> QA -> publish -> store -> TDDI
  async for raw in bus.consume(topic="market_raw"):
    ingest_id = uuid4()
    # raw.ts_utc = time_svc.now_utc() # Assuming time is set on raw message

    # Pacing per-endpoint
    if not pm.allow(raw.endpoint): 
       pm.enqueue_retry(raw)
       continue

    # Normalization against contracts
    ev = normalize(raw, ingest_id)
    if not validators.validate(ev): 
       bus.publish("DLQ_market_raw", raw, reason="schema_violation")
       continue

    # QA: NTP Guard + Freshness
    if not ntp_guard.accept(ev.ts_utc): 
       metrics.inc("ntp_rejects")
       continue
    fresh_mon.observe(ev)

    # OFI from Quotes/L2 (for TickEvent only)
    if is_tick(ev):
      ofi_ev = ofi_calc.on_tick(ev)
      if ofi_ev:
        store.write_ofi(ofi_ev)
        bus.publish("ofi_events", ofi_ev)

    # Storage with idempotency
    if is_bar(ev):
        store.write_bar(ev)
    else:
        store.write_tick(ev)

    # Publish for analysis/strategy
    bus.publish("market_events", ev)

    # Completeness panel update
    comp_gate.update(ev)
    if comp_gate.below_target(asset=ev.conid):
       metrics.alert("completeness_drop", conid=ev.conid)

    # Update kappa and trigger TDDI+hysteresis
    # panel_returns and news_counters need to be available
    # κ = kappa.compute(panel_returns(), news_counters()) 
    # prev_state = tddi_sm.state
    # tddi_sm.update(κ)
    # if tddi_sm.state != prev_state:
    #    rewire_rt_subscriptions(ib_mkt, tddi_sm.state)
