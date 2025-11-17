"""
Pacing Manager for API rate limiting and backpressure management.

Implements token bucket algorithm for per-endpoint rate limiting
to prevent API violations and ensure smooth operation.
"""
import time
import asyncio
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import yaml


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Implements the token bucket algorithm:
    - Bucket fills with tokens at a fixed rate
    - Each operation consumes tokens
    - Operations blocked when bucket is empty
    """
    capacity: int  # Maximum tokens
    refill_rate: float  # Tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)

        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate

    def get_available_tokens(self) -> float:
        """Get current number of available tokens."""
        self._refill()
        return self.tokens


@dataclass
class EndpointConfig:
    """Configuration for a rate-limited endpoint."""
    max_requests_per_second: float
    burst_capacity: int
    enabled: bool = True


class PacingManager:
    """
    Manages rate limiting for multiple API endpoints.

    Implements token bucket algorithm with configurable limits per endpoint.
    Provides backpressure mechanisms and retry queues.
    """

    def __init__(self, pacing_config: Dict[str, Any]):
        """
        Initialize PacingManager with configuration.

        Args:
            pacing_config: Dictionary with endpoint configurations
                Format:
                {
                    'endpoint_name': {
                        'max_requests_per_second': float,
                        'burst_capacity': int,
                        'enabled': bool
                    }
                }
        """
        self.buckets: Dict[str, TokenBucket] = {}
        self.retry_queues: Dict[str, deque] = {}
        self.stats: Dict[str, Dict[str, int]] = {}

        # Initialize buckets from config
        for endpoint, config in pacing_config.items():
            if isinstance(config, dict):
                endpoint_cfg = EndpointConfig(**config)

                if endpoint_cfg.enabled:
                    self.buckets[endpoint] = TokenBucket(
                        capacity=endpoint_cfg.burst_capacity,
                        refill_rate=endpoint_cfg.max_requests_per_second
                    )
                    self.retry_queues[endpoint] = deque(maxlen=10000)
                    self.stats[endpoint] = {
                        'allowed': 0,
                        'throttled': 0,
                        'retried': 0
                    }

    def allow(self, endpoint: str, code: Optional[str] = None) -> bool:
        """
        Check if request to endpoint is allowed under rate limit.

        Args:
            endpoint: Endpoint identifier
            code: Optional sub-identifier (e.g., security code)

        Returns:
            True if request is allowed, False if throttled
        """
        # If endpoint not configured, allow by default
        if endpoint not in self.buckets:
            return True

        # Try to consume a token
        if self.buckets[endpoint].consume(1):
            self.stats[endpoint]['allowed'] += 1
            return True
        else:
            self.stats[endpoint]['throttled'] += 1
            return False

    async def wait_for_capacity(self, endpoint: str, timeout: Optional[float] = None) -> bool:
        """
        Wait until capacity is available for endpoint.

        Args:
            endpoint: Endpoint identifier
            timeout: Maximum time to wait in seconds (None = no timeout)

        Returns:
            True if capacity became available, False if timed out
        """
        if endpoint not in self.buckets:
            return True

        wait_time = self.buckets[endpoint].get_wait_time(1)

        if timeout is not None and wait_time > timeout:
            return False

        await asyncio.sleep(wait_time)
        return self.buckets[endpoint].consume(1)

    def enqueue_retry(self, endpoint: str, message: Any):
        """
        Add message to retry queue for endpoint.

        Args:
            endpoint: Endpoint identifier
            message: Message to retry later
        """
        if endpoint in self.retry_queues:
            self.retry_queues[endpoint].append(message)

    def get_retry_queue(self, endpoint: str) -> deque:
        """
        Get retry queue for endpoint.

        Args:
            endpoint: Endpoint identifier

        Returns:
            Deque of messages waiting to retry
        """
        return self.retry_queues.get(endpoint, deque())

    def get_available_capacity(self, endpoint: str) -> Optional[float]:
        """
        Get available capacity for endpoint.

        Args:
            endpoint: Endpoint identifier

        Returns:
            Number of available tokens, or None if endpoint not configured
        """
        if endpoint not in self.buckets:
            return None
        return self.buckets[endpoint].get_available_tokens()

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all endpoints."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters."""
        for endpoint in self.stats:
            self.stats[endpoint] = {
                'allowed': 0,
                'throttled': 0,
                'retried': 0
            }


def load_pacing_config(config_path: str) -> PacingManager:
    """
    Load pacing configuration from YAML file.

    Args:
        config_path: Path to pacing.yaml configuration file

    Returns:
        Initialized PacingManager instance
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return PacingManager(config.get('endpoints', {}))
    except FileNotFoundError:
        # Return default configuration if file not found
        return get_default_pacing_manager()


def get_default_pacing_manager() -> PacingManager:
    """
    Get PacingManager with default IBKR rate limits.

    IBKR Rate Limits (conservative estimates):
    - Market Data: 100 req/sec burst, 50 req/sec sustained
    - Historical Data: 60 req/10min = 0.1 req/sec
    - Order Placement: 50 req/sec
    - Account Data: 1 req/sec
    """
    default_config = {
        'rt_marketdata': {
            'max_requests_per_second': 50.0,
            'burst_capacity': 100,
            'enabled': True
        },
        'historical_data': {
            'max_requests_per_second': 0.1,
            'burst_capacity': 60,
            'enabled': True
        },
        'order_placement': {
            'max_requests_per_second': 40.0,  # Conservative limit
            'burst_capacity': 50,
            'enabled': True
        },
        'account_data': {
            'max_requests_per_second': 1.0,
            'burst_capacity': 5,
            'enabled': True
        },
        'executions': {
            'max_requests_per_second': 10.0,
            'burst_capacity': 20,
            'enabled': True
        }
    }

    return PacingManager(default_config)
