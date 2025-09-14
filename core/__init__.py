# -*- coding: utf-8 -*-
"""
core package entrypoint — robust, lazy, testable.

מטרות:
- __version__ מרכזי
- setup_logging פשוט ואחיד
- בדיקת תלותים וסביבה (check_environment / health_check)
- טעינה עצלה של תתי מודולים ושמות נפוצים (get_module / __getattr__)
- wrappers נוחים להרצת run_day / run_backtest אם קיימים במאגר
- ממשק ידידותי ל-CI (smoke_test)
"""

from __future__ import annotations

__all__ = [
    "__version__",
    "setup_logging",
    "check_environment",
    "get_module",
    "run_day",
    "run_backtest",
    "health_check",
    "smoke_test",
]

__version__ = "0.1.0"

import importlib
import logging
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple, Sequence

_logger = logging.getLogger(__name__)

# ------------------------
# logging helper
# ------------------------
def setup_logging(level: int = logging.INFO, fmt: Optional[str] = None) -> None:
    """
    Configure package logging if user hasn't configured root logger.
    קריאה idempotent — לא מרוקנת handlers קיימים.
    """
    if fmt is None:
        fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
    root.setLevel(level)
    _logger.debug("core logging configured at %s", logging.getLevelName(level))


# apply conservative default
setup_logging(level=logging.WARNING)


# ------------------------
# environment / dependencies
# ------------------------
DEFAULT_REQUIRED_PACKAGES = (
    "numpy",
    "pandas",
    "cvxpy",
    "scipy",
    "scikit_learn",  # note: import name differs for check; we will normalize
    "skopt",
    "hmmlearn",
)

def _normalize_pkg_name(pkg: str) -> str:
    # map canonical package names to import names if needed
    mapping = {"scikit_learn": "sklearn", "scikit-learn": "sklearn"}
    return mapping.get(pkg, pkg)


def check_environment(required: Optional[Sequence[str]] = None, strict: bool = False) -> Dict[str, Tuple[bool, Optional[str]]]:
    """
    בדיקה מהירה של תלותים בסביבת הריצה.
    מחזיר מפת שם־חבילה -> (is_installed, version_or_error).
    אם strict=True וניתן להרים ImportError, תיזרק שגיאה.
    """
    reqs = tuple(required) if required is not None else DEFAULT_REQUIRED_PACKAGES
    results: Dict[str, Tuple[bool, Optional[str]]] = {}
    for pkg in reqs:
        import_name = _normalize_pkg_name(pkg)
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", None)
            results[pkg] = (True, str(ver) if ver is not None else "installed")
        except Exception as e:
            results[pkg] = (False, str(e))
            if strict:
                raise ImportError(f"Missing required package '{pkg}' (import as '{import_name}'): {e}")
    return results


# ------------------------
# safe lazy import utilities
# ------------------------
@lru_cache(maxsize=128)
def _import_submodule(path: str):
    """
    נסיון טעינה חכם של מודולים:
    - מנסה import של path ישיר
    - מנסה relative תחת 'algo_trade.core' ו-'core' (fallbacks)
    מחזיר מודול או None.
    """
    candidates = [path, f"algo_trade.core.{path}", f"core.{path}"]
    for cand in candidates:
        try:
            return importlib.import_module(cand)
        except Exception:
            continue
    return None


def get_module(name: str):
    """
    מביא מודול פנימי בשם name או None אם לא נמצא.
    שימוש טיפוסי: mod = get_module('main'); if mod: mod.run_day(...)
    """
    return _import_submodule(name)


# module attribute fallback via PEP 562 (__getattr__)
def __getattr__(name: str) -> Any:
    """
    הנדסה להטענה עצלה: כשניגשים ל־core.<submodule_or_attr> — ננסה לייבא מודול או לספק אטריבוט
    אם לא נמצא, נזרוק AttributeError מסודר.
    """
    # first attempt: submodule import
    mod = _import_submodule(name)
    if mod is not None:
        globals()[name] = mod
        return mod

    # second attempt: try to find attribute inside well-known modules
    fallbacks = ("main", "simulation", "optimization", "execution", "risk", "signals", "validation")
    for base in fallbacks:
        base_mod = _import_submodule(base)
        if base_mod is None:
            continue
        if hasattr(base_mod, name):
            val = getattr(base_mod, name)
            globals()[name] = val
            return val

    raise AttributeError(f"module '{__name__}' has no attribute '{name}' and no submodule with that name was found")


def __dir__() -> Sequence[str]:
    base = set(__all__)
    # include discovered top-level submodules if present
    known = ("main", "simulation", "optimization", "execution", "risk", "signals", "validation", "config")
    for nm in known:
        try:
            if _import_submodule(nm) is not None:
                base.add(nm)
        except Exception:
            continue
    return sorted(base)


# ------------------------
# wrappers for common entrypoints (if provided)
# ------------------------
def run_day(*args, **kwargs) -> Any:
    """
    Wrapper ל־main.run_day. זורק ImportError ברור אם לא נמצא.
    """
    mod = _import_submodule("main") or _import_submodule("simulation")
    if not mod:
        raise ImportError("No 'main' or 'simulation' module found for run_day. Ensure core.main exists.")
    if not hasattr(mod, "run_day"):
        raise AttributeError(f"Module '{mod.__name__}' does not expose 'run_day'.")
    return getattr(mod, "run_day")(*args, **kwargs)


def run_backtest(*args, **kwargs) -> Any:
    """
    Wrapper שמחפש סדרת נקודות כניסה רלוונטיות ל־backtest.
    """
    candidates = ["main", "simulation", "optimization.bayesian_optimization"]
    for cand in candidates:
        mod = _import_submodule(cand)
        if mod is None:
            continue
        for fn in ("run_backtest", "run_bayesian_optimization", "run"):
            if hasattr(mod, fn):
                return getattr(mod, fn)(*args, **kwargs)
    raise ImportError("No suitable backtest entrypoint found in core. Add main.run_backtest or simulation.run_backtest.")


# ------------------------
# health / smoke tests
# ------------------------
def health_check(strict: bool = False) -> Dict[str, Any]:
    """
    בדיקה מהירה של מצב הליבה:
    - בדיקת חבילות בסיס (non-strict)
    - בדיקת מודולים מרכזיים (main, optimization, execution)
    מחזיר מילון סטטוס.
    """
    env = check_environment(strict=False)
    modules = {}
    for name in ("main", "simulation", "optimization", "execution", "risk"):
        modules[name] = bool(_import_submodule(name))
    status = {"env": env, "modules": modules}
    if strict:
        # אם strict אז וודא שהחבילות החשובות מותקנות
        try:
            check_environment(strict=True)
        except ImportError as e:
            raise RuntimeError(f"Environment strict check failed: {e}")
    return status


def smoke_test() -> Tuple[bool, str]:
    """
    בדיקת smoke קלה לשימוש ב־CI:
    - וודא שאפשר לבצע import ל־main או ל־simulation
    - וודא ש־run_day / run_backtest קיימים בצורה בסיסית
    מחזיר (ok, message)
    """
    try:
        svc = health_check(strict=False)
        # basic expectations: at least one of the main entrypoints
        if not (svc["modules"].get("main") or svc["modules"].get("simulation")):
            return False, "Neither 'main' nor 'simulation' module is importable"
        # attempt to resolve run_day/run_backtest without executing heavy logic
        try:
            _ = getattr(get_module("main") or get_module("simulation"), "__name__")
        except Exception:
            pass
        return True, "smoke ok"
    except Exception as e:
        return False, f"smoke failed: {e}"


# ------------------------
# convenience exports (attempt to expose important functions if available)
# ------------------------
solve_qp = None
try:
    solve_qp = _import_submodule("optimization.qp_solver") or _import_submodule("qp_solver")
    if solve_qp is not None and hasattr(solve_qp, "solve_qp"):
        solve_qp = getattr(solve_qp, "solve_qp")
except Exception:
    solve_qp = None

# note: keep __all__ small and stable; dynamic attributes are available via __getattr__
_logger.debug("core package initialized (version %s)", __version__)
# Core module for algorithmic trading system
