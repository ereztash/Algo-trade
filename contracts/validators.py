from pydantic import BaseModel
from typing import Optional, Literal
from uuid import UUID

class BarEvent(BaseModel):
    schema: int = 1
    ts_utc: float
    tz: Literal['UTC']
    conid: int
    symbol: str
    primary_exchange: str
    rth_flag: bool
    bar: dict  # {o,h,l,c,v}
    src: Literal['ibkr_rt','ibkr_hist','alt_hist']
    adj_flags: dict  # {split: bool, dividend: bool}
    ingest_id: UUID

class TickEvent(BaseModel):
    schema: int = 1
    ts_utc: float
    conid: int
    bid: float
    ask: float
    bid_sz: float
    ask_sz: float
    last: float
    last_sz: float
    level2: Optional[dict]
    src: Literal['ibkr_rt']
    ingest_id: UUID

class OFIEvent(BaseModel):
    ts_utc: float
    conid: int
    ofi_z: float

class OrderIntent(BaseModel):
    ts_utc: float
    conid: int
    side: Literal['BUY','SELL']
    qty: float
    tif: Literal['DAY','IOC','GTC']
    price: Optional[float]
    meta: dict

class ExecutionReport(BaseModel):
    ts_utc: float
    order_id: str
    conid: int
    fill_px: float
    fill_qty: float
    status: Literal['FILLED','PARTIAL','REJECTED']
    slippage: float
