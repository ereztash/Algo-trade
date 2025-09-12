# -*- coding: utf-8 -*-
"""
simulation.py
סימולציית מחירים ותשואות
"""

import numpy as np
import pandas as pd
from .config import CFG

try:
	from .config import load_config
	config = load_config()
	rng = np.random.default_rng(config.get("SEED", 42))
except Exception:
	rng = np.random.default_rng(42)

def simulate_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
	"""מייצר סדרות תשואות נורמליות, ומחירים ע"י אינטגרציה אקספוננציאלית."""
	rets = rng.normal(CFG["MU_DAILY"], CFG["SIGMA_DAILY"], size=(CFG["DAYS"], CFG["N"]))
	rets = pd.DataFrame(rets, columns=[f"Asset_{i}" for i in range(CFG["N"])])
	px = CFG["START_PRICE"] * np.exp(rets.cumsum())
	return px, rets
