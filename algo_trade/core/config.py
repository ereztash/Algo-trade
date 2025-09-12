# -*- coding: utf-8 -*-
"""
config.py
ניהול קונפיגורציה וטעינה מקובץ YAML
"""


import yaml
from typing import Dict

CFG = None
def load_config(filepath: str = 'targets.yaml') -> Dict:
	"""טוען או יוצר קובץ קונפיגורציה."""
	global CFG
	try:
		with open(filepath, 'r', encoding='utf-8') as file:
			config = yaml.safe_load(file)
			print(f"✅ קובץ קונפיגורציה {filepath} נטען בהצלחה.")
			CFG = config
			return config
	except FileNotFoundError:
		print(f"❌ קובץ קונפיגורציה {filepath} לא נמצא.")
		default_config = {
			"SEED": 42,
			"DAYS": 252 * 2,
			"N": 60,
			"START_PRICE": 100.0,
			"MU_DAILY": 0.0002,
			"SIGMA_DAILY": 0.015,
			"MOM_H": 20,
			"REV_H": 5,
			"VOL_H": 20,
			"POS_H": 60,
			"TSX_H": 30,
			"SIF_H_FAST": 5,
			"SIF_H_SLOW": 20,
			"ORTHO_WIN": 252,
			"REGIME_WIN": 60,
			"COV_EWMA_HL": {"Calm": 60, "Normal": 30, "Storm": 10},
			"GROSS_LIM": {"Calm": 2.5, "Normal": 2.0, "Storm": 1.0},
			"NET_LIM": {"Calm": 1.0, "Normal": 0.8, "Storm": 0.4},
			"VOL_TARGET": 0.10,
			"BOX_LIM": 0.25,
			"TURNOVER_PEN": 0.002,
			"RIDGE_PEN": 1e-4,
			"LAMBDA_INIT": 5e-4,
			"LAMBDA_EMA_RHO": 0.1,
			"SLIP_BETA": 0.7,
			"POV_CAP": 0.08,
			"ADV_CAP": 0.10,
			"KILL_PNL": -0.05,
			"COV_DRIFT": 0.10,
			"PSR_KILL_SWITCH": 0.20,
			"MAX_DD_KILL_SWITCH": 0.15,
			"PRINT_EVERY": 25,
			"NUM_STRATEGIES": 6,
			"BAYESIAN_OPTIMIZATION": {
				"ITERATIONS": 50,
				"SEARCH_SPACE": {
					"MOM_H": [10, 30],
					"REV_H": [3, 10],
					"TURNOVER_PEN": [0.001, 0.005],
					"RIDGE_PEN": [1e-5, 1e-3]
				}
			},
			"CSCV_M": 16,
			"LINUCB_ALPHA": 0.1
		}
		with open(filepath, 'w', encoding='utf-8') as file:
			yaml.dump(default_config, file, allow_unicode=True, default_flow_style=False)
		print("✅ קובץ ברירת מחדל 'targets.yaml' נוצר. נא עדכן אותו בהתאם לצרכים.")
		CFG = default_config
		return default_config
	except yaml.YAMLError as e:
		print(f"❌ שגיאה בקריאת קובץ YAML: {e}")
		return None

if __name__ == "__main__":
		# בדיקה עצמאית: טען קונפיגורציה וודא יצירה/טעינה
		config = load_config()
		print("קונפיגורציה:")
		print(config)
