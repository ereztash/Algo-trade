# data_plane/connectors/ibkr/producers_hist.py
# from ...errors import IBKRError # Assuming custom error types

def plan_hist_batches(universe):
    # Logic to plan historical data batches
    ...
    return []

async def producer_hist(universe, ib_mkt, bus, pm):
  """
  Historical data producer from IBKR.
  """
  for batch in plan_hist_batches(universe):
    if not pm.allow("hist_TRADES_1m"): 
       pm.defer(batch)
       continue
    try:
      rows = await ib_mkt.request_hist(batch)
      for r in rows:
          await bus.publish("market_raw", r)
    except Exception as e: # Replace with specific IBKRError
      # pm.cooldown_by_code(e.code)
      # bus.publish("DLQ_hist", batch, reason=e.code)
      pass
