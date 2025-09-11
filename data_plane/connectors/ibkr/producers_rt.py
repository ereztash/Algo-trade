# data_plane/connectors/ibkr/producers_rt.py
def decide_whatToShow(state):
    # Logic to decide what to show based on TDDI state
    # e.g., TRADES/MIDPOINT/L1/(L2 if S1/S2)/(TBT if S2)
    return "TRADES"

async def producer_rt(universe, ib_mkt, bus, pm, tddi_sm):
  """
  Real-time data producer from IBKR.
  """
  for con in universe:
    wts = decide_whatToShow(tddi_sm.state)
    await ib_mkt.subscribe_rt(con, wts)

  async for msg in ib_mkt.rt_stream():
    if pm.allow("rt_marketdata"):
       await bus.publish("market_raw", msg)
    else:
       pm.enqueue_retry(msg)
