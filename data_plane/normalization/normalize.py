# data_plane/normalization/normalize.py
# from contracts.validators import BarEvent, TickEvent # Assuming these are defined

def normalize(raw, ingest_id):
  """
  Normalizes raw data into BarEvent or TickEvent based on contract.
  """
  # This is a simplified placeholder.
  # In a real scenario, you'd have robust type checking and mapping.
  if hasattr(raw, 'type') and raw.type == "bar":
     # return BarEvent(...)
     pass
  if hasattr(raw, 'type') and raw.type == "tick":
     # return TickEvent(...)
     pass
  return None
