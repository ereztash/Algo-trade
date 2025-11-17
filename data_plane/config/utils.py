# -*- coding: utf-8 -*-
"""
data_plane.config.utils — hardened config loader with Vault (hvac) support.

שיפורים עיקריים לעומת הגרסה הקודמת:
- שימוש ב־hvac אם זמין לטעינת סודות מ-Vault (ממשק KV v2 ו-v1).
- fallback ל־requests במידה ו-hvac לא מותקן אך VAULT מסומנת.
- stricter validators (port range, fractions, positive windows, cache path expansion).
- DP_ALLOW_CONFIG_WRITE guard לשמירה בטוחה של sample config.
- strict / non-strict modes: ב־strict נזרקות שגיאות ולידציה.
- קריאות עזר ל־CI: smoke_test ו-health_check.
- מסמך ברור ל־ENV overrides (prefix + __ nesting).
- מנגנון מיגרציה סטאב (extensible).
"""
from __future__ import annotations

import os
import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple, Sequence
from pathlib import Path

# external deps
try:
    import yaml
except Exception as e:  # pragma: no cover
    raise ImportError("Missing dependency 'PyYAML'. Install via `pip install pyyaml`. Error: " + str(e))

try:
    from pydantic import BaseModel, Field, ValidationError, validator
except Exception as e:  # pragma: no cover
    raise ImportError("Missing dependency 'pydantic'. Install via `pip install pydantic`. Error: " + str(e))

# Import audit logger and secrets manager
try:
    from data_plane.config.audit_logger import get_audit_logger, audit_secret_access, audit_config_access, audit_vault_access
    _HAS_AUDIT = True
except ImportError:
    _HAS_AUDIT = False
    logger.debug("Audit logger not available")

try:
    from data_plane.config.secrets_manager import get_secrets_manager
    _HAS_SECRETS_MANAGER = True
except ImportError:
    _HAS_SECRETS_MANAGER = False
    logger.debug("Secrets manager not available")

# hvac is optional; prefer it for Vault integration
try:
    import hvac

    _HAS_HVAC = True
except Exception:
    _HAS_HVAC = False

# requests is optional fallback for simple Vault HTTP access
try:
    import requests

    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# -----------------------
# Pydantic models
# -----------------------
class BrokerConfig(BaseModel):
    name: Optional[str] = Field(None, description="Broker name (e.g., IBKR)")
    host: Optional[str] = Field(None, description="Broker host / endpoint")
    port: Optional[int] = Field(None, description="Broker port")
    username: Optional[str] = None
    password: Optional[str] = None
    paper: bool = Field(True, description="Paper/sandbox mode")

    @validator("port")
    def port_range(cls, v):
        if v is None:
            return v
        if not (0 < v < 65536):
            raise ValueError("port must be in 1..65535")
        return v

class DataConfig(BaseModel):
    provider: str = Field("local", description="Data provider id")
    cache_path: str = Field("data/cache", description="Local cache dir for data")
    historical_window_days: int = Field(365 * 3, description="Default lookback window")
    assets_file: str = Field("data/assets.csv", description="Path to assets manifest")

    @validator("cache_path")
    def expand_cache_path(cls, v: str) -> str:
        return str(Path(v).expanduser())

    @validator("historical_window_days")
    def positive_window(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("historical_window_days must be positive")
        return v

class ExecutionConfig(BaseModel):
    enabled: bool = Field(False)
    default_slippage: float = Field(0.001)
    max_position_risk: float = Field(0.05)

    @validator("default_slippage", "max_position_risk")
    def in_unit_interval(cls, v):
        if not (0 <= v <= 1):
            raise ValueError("fractions must be between 0 and 1")
        return v

class LoggingConfig(BaseModel):
    level: str = Field("WARNING")
    fmt: str = Field("%(asctime)s %(levelname)s [%(name)s] %(message)s")

class DataPlaneConfig(BaseModel):
    schema_version: str = Field("0.1.0", description="Config schema version")
    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    extras: Dict[str, Any] = Field(default_factory=dict)

    @validator("schema_version")
    def non_empty_version(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("schema_version must be a non-empty string")
        return v

# -----------------------
# constants & env guards
# -----------------------
DEFAULT_CONFIG_PATH = Path(os.environ.get("DATA_PLANE_CONFIG", "config/data_plane.yaml"))
ENV_PREFIX = os.environ.get("DATA_PLANE_ENV_PREFIX", "DP_")
_ALLOW_CONFIG_WRITE = os.environ.get("DP_ALLOW_CONFIG_WRITE", "0") == "1"

# -----------------------
# internal helpers: load yaml, env overrides, deep merge
# -----------------------
def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.debug("config: %s not found; return empty", path)
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data

def _env_overrides(prefix: str = ENV_PREFIX) -> Dict[str, Any]:
    """
    Parse env vars with prefix, nesting via double-underscore.
    Example: DP_BROKER__HOST=host -> {'broker': {'host': 'host'}}
    Supports JSON decoding of values.
    """
    out: Dict[str, Any] = {}
    pref = prefix.upper()
    sensitive_keys = {"password", "token", "key", "secret", "credential"}

    for k, v in os.environ.items():
        if not k.startswith(pref):
            continue
        rest = k[len(pref):]
        parts = rest.split("__")
        node = out
        for p in parts[:-1]:
            key = p.lower()
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        final_key = parts[-1].lower()
        try:
            parsed = json.loads(v)
        except Exception:
            parsed = v
        node[final_key] = parsed

        # Audit secret access from environment variables
        if _HAS_AUDIT and any(sk in final_key.lower() for sk in sensitive_keys):
            full_key = ".".join(p.lower() for p in parts)
            audit_secret_access(full_key, "environment", success=True)

    return out

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    res = dict(a)
    for k, v in b.items():
        if k in res and isinstance(res[k], dict) and isinstance(v, dict):
            res[k] = _deep_merge(res[k], v)
        else:
            res[k] = v
    return res

# -----------------------
# Vault integration: hvac preferred, requests fallback
# -----------------------
def _fetch_secret_from_vault_hvac(vault_path: str) -> Dict[str, Any]:
    """
    Use hvac client to fetch secrets.
    Supports:
      - kv v2 path: secret/data/<path>  -> client.secrets.kv.v2.read_secret_version
      - kv v1 path: secret/<path>       -> client.secrets.kv.v1.read_secret
    Returns dict of secrets or empty dict on failure.
    """
    addr = os.environ.get("VAULT_ADDR")
    token = os.environ.get("VAULT_TOKEN")
    if not addr or not token:
        logger.debug("Vault not configured (VAULT_ADDR/VAULT_TOKEN missing)")
        if _HAS_AUDIT:
            audit_vault_access(vault_path, "read", success=False)
        return {}
    if not _HAS_HVAC:
        logger.debug("hvac not available")
        if _HAS_AUDIT:
            audit_vault_access(vault_path, "read", success=False)
        return {}
    try:
        client = hvac.Client(url=addr, token=token)
        if not client.is_authenticated():
            logger.warning("Vault client not authenticated")
            if _HAS_AUDIT:
                audit_vault_access(vault_path, "read", success=False)
        # try kv v2 pattern
        # if path starts with 'secret/data/' -> treat as kv v2; mount is part before '/data'
        p = vault_path.lstrip("/")
        result = {}
        if "/data/" in p:
            mount, _, rel = p.partition("/data/")
            try:
                resp = client.secrets.kv.v2.read_secret_version(path=rel, mount_point=mount)
                if resp and isinstance(resp, dict) and "data" in resp and "data" in resp["data"]:
                    result = resp["data"]["data"]
                elif resp and isinstance(resp, dict) and "data" in resp:
                    result = resp["data"]
                if result:
                    if _HAS_AUDIT:
                        audit_vault_access(vault_path, "read", success=True)
                    return result
            except Exception as e:
                logger.debug("hvac kv.v2 read failed for %s: %s", vault_path, e)
        # try kv v1 or direct read
        try:
            resp = client.secrets.kv.v1.read_secret(path=p)
            if resp and isinstance(resp, dict) and "data" in resp:
                result = resp["data"]
                if result:
                    if _HAS_AUDIT:
                        audit_vault_access(vault_path, "read", success=True)
                    return result
        except Exception:
            # last attempt: generic read
            try:
                resp = client.secrets.kv.v2.read_secret_version(path=p)
                if resp and "data" in resp and "data" in resp["data"]:
                    result = resp["data"]["data"]
                    if result:
                        if _HAS_AUDIT:
                            audit_vault_access(vault_path, "read", success=True)
                        return result
            except Exception as e:
                logger.debug("hvac generic read failed for %s: %s", vault_path, e)
        if _HAS_AUDIT:
            audit_vault_access(vault_path, "read", success=False)
        return {}
    except Exception as e:
        logger.warning("hvac Vault fetch error for %s: %s", vault_path, e)
        if _HAS_AUDIT:
            audit_vault_access(vault_path, "read", success=False)
        return {}

def _fetch_secret_from_vault_requests(vault_path: str) -> Dict[str, Any]:
    """
    Simple HTTP-based Vault fetcher (fallback). Requires VAULT_ADDR & VAULT_TOKEN.
    """
    addr = os.environ.get("VAULT_ADDR")
    token = os.environ.get("VAULT_TOKEN")
    if not addr or not token:
        logger.debug("Vault not configured (VAULT_ADDR/VAULT_TOKEN missing)")
        return {}
    if not _HAS_REQUESTS:
        logger.debug("requests not available for Vault fallback")
        return {}
    url = addr.rstrip("/") + "/v1/" + vault_path.lstrip("/")
    headers = {"X-Vault-Token": token}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        # handle v2 structure
        if "data" in data and isinstance(data["data"], dict):
            if "data" in data["data"]:
                return data["data"]["data"] if isinstance(data["data"]["data"], dict) else {}
            return data["data"]
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Vault HTTP fetch error for %s: %s", vault_path, e)
        return {}

def _fetch_secret_from_vault(vault_path: str) -> Dict[str, Any]:
    """
    High-level fetch: prefer hvac, else requests, else return {}.
    """
    if _HAS_HVAC:
        return _fetch_secret_from_vault_hvac(vault_path)
    elif _HAS_REQUESTS:
        return _fetch_secret_from_vault_requests(vault_path)
    else:
        logger.debug("No hvac/requests available to fetch from Vault")
        return {}

def _fetch_secret_from_encrypted_file() -> Dict[str, Any]:
    """
    Fetch secrets from encrypted local file using SecretsManager.
    Returns dict of secrets or empty dict on failure.
    """
    if not _HAS_SECRETS_MANAGER:
        logger.debug("Secrets manager not available")
        return {}

    try:
        manager = get_secrets_manager()
        if manager is None:
            logger.debug("Encrypted secrets disabled or not configured")
            return {}

        secrets = manager.get_all_secrets()
        if secrets:
            logger.debug("Loaded %d secrets from encrypted file", len(secrets))
            if _HAS_AUDIT:
                for key in secrets.keys():
                    audit_secret_access(key, "encrypted_file", success=True)
        return secrets
    except Exception as e:
        logger.warning("Failed to fetch secrets from encrypted file: %s", e)
        if _HAS_AUDIT:
            audit_secret_access("*", "encrypted_file", success=False)
        return {}

# -----------------------
# config construction + migrations
# -----------------------
@lru_cache(maxsize=1)
def _build_config_obj(path: Optional[Path] = None, env_prefix: str = ENV_PREFIX, strict: bool = False) -> DataPlaneConfig:
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH

    # Audit config file access
    if _HAS_AUDIT:
        audit_config_access(str(cfg_path), "read", success=True)

    yaml_map = _load_yaml_file(cfg_path)
    env_map = _env_overrides(prefix=env_prefix)
    merged = _deep_merge(yaml_map or {}, env_map or {})

    # Priority order for secrets:
    # 1. Environment variables (highest priority - already in merged)
    # 2. Vault (if enabled)
    # 3. Encrypted local file (if enabled)
    # 4. YAML config (lowest priority - already in merged)

    # Option 1: Incorporate encrypted local secrets if enabled
    if os.environ.get("DP_USE_ENCRYPTED_SECRETS", "0") == "1":
        encrypted_secrets = _fetch_secret_from_encrypted_file()
        if encrypted_secrets:
            # Merge encrypted secrets (lower priority than env vars)
            merged = _deep_merge({"broker": encrypted_secrets.get("broker", encrypted_secrets)}, merged)
            logger.debug("Merged encrypted local secrets into config")

    # Option 2: Incorporate Vault secrets if enabled (takes precedence over encrypted file)
    if os.environ.get("DP_USE_VAULT", "0") == "1":
        vpath = os.environ.get("DP_VAULT_PATH", "")
        if vpath:
            vault_map = _fetch_secret_from_vault(vpath) or {}
            # vault_map expected to contain nested keys; merge under 'broker' if present
            merged = _deep_merge({"broker": vault_map.get("broker", vault_map)}, merged)
            logger.debug("Merged Vault secrets into config")
    try:
        cfg = DataPlaneConfig.parse_obj(merged)
    except ValidationError as ve:
        logger.error("Config validation error: %s", ve)
        if strict:
            raise
        logger.warning("Returning default DataPlaneConfig due to validation errors (non-strict).")
        return DataPlaneConfig()

    cfg = _migrate_if_needed(cfg)

    # ensure data.cache_path exists if possible
    try:
        Path(cfg.data.cache_path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.debug("Could not ensure cache dir %s: %s", cfg.data.cache_path, e)

    # If broker password missing but Vault configured, attempt a targeted fetch:
    if (not cfg.broker.password) and os.environ.get("DP_USE_VAULT", "0") == "1":
        # allow DP_VAULT_PATH_PASSWORD to be set to directly fetch password key
        pw_path = os.environ.get("DP_VAULT_PATH_PASSWORD")
        if pw_path:
            pw_map = _fetch_secret_from_vault(pw_path)
            if isinstance(pw_map, dict):
                # common keys: 'password', 'broker_password', etc.
                for k in ("password", "broker_password", "pwd"):
                    if k in pw_map:
                        cfg.broker.password = pw_map[k]
                        logger.debug("Broker password loaded from Vault path %s (key=%s)", pw_path, k)
                        break

    return cfg

def _migrate_if_needed(cfg: DataPlaneConfig) -> DataPlaneConfig:
    # Placeholder for schema migration logic.
    # Example usage: if cfg.schema_version == '0.1.0': perform migration steps and bump to '0.2.0'
    return cfg

def get_config(path: Optional[str] = None, env_prefix: str = ENV_PREFIX, strict: bool = False) -> DataPlaneConfig:
    if path:
        return _build_config_obj(path=Path(path), env_prefix=env_prefix, strict=strict)
    return _build_config_obj(path=None, env_prefix=env_prefix, strict=strict)

def reload_config(path: Optional[str] = None, env_prefix: str = ENV_PREFIX, strict: bool = False) -> DataPlaneConfig:
    _build_config_obj.cache_clear()
    return get_config(path=path, env_prefix=env_prefix, strict=strict)

# -----------------------
# logging application, health and smoke
# -----------------------
def apply_logging_from_config(cfg: Optional[DataPlaneConfig] = None):
    try:
        cfg = cfg or get_config()
        lvl = getattr(logging, cfg.logging.level.upper(), None)
        if not isinstance(lvl, int):
            logger.warning("Unknown logging level in config: %s", cfg.logging.level)
            lvl = logging.WARNING
        root = logging.getLogger()
        root.setLevel(lvl)
        for h in root.handlers:
            try:
                h.setFormatter(logging.Formatter(cfg.logging.fmt))
            except Exception:
                continue
        logger.debug("Applied logging from config: %s", cfg.logging.level)
    except Exception as e:
        logger.exception("Failed to apply logging: %s", e)

def _check_environment(required: Optional[Sequence[str]] = None) -> Dict[str, Tuple[bool, Optional[str]]]:
    DEFAULT_REQUIRED_PACKAGES = ("pyyaml", "pydantic")
    reqs = tuple(required) if required is not None else DEFAULT_REQUIRED_PACKAGES
    results: Dict[str, Tuple[bool, Optional[str]]] = {}
    for pkg in reqs:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "installed")
            results[pkg] = (True, str(ver))
        except Exception as e:
            results[pkg] = (False, str(e))
    return results

def health_check(strict: bool = False) -> Dict[str, Any]:
    env = _check_environment()
    modules = {"hvac": _HAS_HVAC, "requests": _HAS_REQUESTS}
    status = {"env": env, "modules": modules}
    if strict:
        missing = [k for k, v in env.items() if not v[0]]
        if missing:
            raise RuntimeError(f"Missing critical packages: {missing}")
    return status

def smoke_test() -> Tuple[bool, str]:
    try:
        cfg = get_config(strict=False)
        apply_logging_from_config(cfg)
        ok = bool(cfg and cfg.data and (cfg.broker is not None))
        if not ok:
            return False, "config incomplete"
        # if DP_USE_VAULT=1 but no hvac/requests, fail smoke
        if os.environ.get("DP_USE_VAULT", "0") == "1" and not (_HAS_HVAC or _HAS_REQUESTS):
            return False, "Vault requested but no hvac/requests available"
        return True, "smoke ok"
    except Exception as e:
        return False, f"smoke failed: {e}"

# -----------------------
# safe sample config writing
# -----------------------
def save_sample_config(path: Optional[str] = None, overwrite: bool = False, only_if_missing: bool = True) -> Path:
    dest = Path(path) if path else DEFAULT_CONFIG_PATH
    if dest.exists() and only_if_missing and not overwrite:
        logger.info("Sample config already exists at %s (not overwriting)", dest)
        return dest
    if dest.exists() and not overwrite and not _ALLOW_CONFIG_WRITE:
        # guard behavior: do not overwrite unless explicitly allowed via DP_ALLOW_CONFIG_WRITE
        raise PermissionError("Config write disabled by DP_ALLOW_CONFIG_WRITE env guard")
    sample = DataPlaneConfig().dict()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(sample, fh, sort_keys=False, allow_unicode=True)
    logger.info("Wrote sample config to %s", dest)
    return dest

# -----------------------
# module init
# -----------------------
def _module_init():
    try:
        cfg = get_config(strict=False)
        apply_logging_from_config(cfg)
        logger.debug("data_plane.config.utils initialized using %s", DEFAULT_CONFIG_PATH)
    except Exception as e:
        logger.warning("data_plane.config.utils init warning: %s", e)

_module_init()
