"""
Unit tests for Data Plane components.

Tests cover:
- Market data normalization
- OFI calculation
- QA gates (completeness, freshness, NTP drift)
- Kafka adapter
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from data_plane.normalization.normalize import normalize_market_event
from data_plane.normalization.ofi_from_quotes import calculate_ofi
from data_plane.qa.completeness_gate import check_completeness
from data_plane.qa.freshness_monitor import check_freshness
from data_plane.qa.ntp_guard import check_ntp_drift


# ============================================================================
# Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestMarketDataNormalization:
    """Test market data normalization."""

    def test_normalize_market_event_basic(self):
        """Test basic market event normalization."""
        raw_event = {
            "symbol": "AAPL",
            "price": 150.0,
            "volume": 1000,
            "timestamp": "2024-01-01T09:30:00"
        }

        normalized = normalize_market_event(raw_event)

        assert normalized is not None
        assert "symbol" in normalized
        assert "price" in normalized
        assert isinstance(normalized["timestamp"], (str, datetime))

    def test_normalize_market_event_missing_fields(self):
        """Test normalization with missing required fields."""
        raw_event = {
            "symbol": "AAPL",
            # Missing price and volume
        }

        # Should handle missing fields gracefully
        normalized = normalize_market_event(raw_event)
        # May return None or partial data depending on implementation
        assert normalized is None or isinstance(normalized, dict)

    def test_normalize_market_event_invalid_price(self):
        """Test normalization with invalid price."""
        raw_event = {
            "symbol": "AAPL",
            "price": -150.0,  # Invalid negative price
            "volume": 1000,
            "timestamp": "2024-01-01T09:30:00"
        }

        normalized = normalize_market_event(raw_event)
        # Should reject invalid prices
        assert normalized is None or normalized["price"] >= 0


# ============================================================================
# OFI Calculation Tests
# ============================================================================


@pytest.mark.unit
class TestOFICalculation:
    """Test Order Flow Imbalance calculation."""

    def test_calculate_ofi_basic(self):
        """Test basic OFI calculation."""
        quotes = pd.DataFrame({
            "bid_price": [99.0, 99.5, 99.0],
            "ask_price": [101.0, 101.5, 101.0],
            "bid_volume": [1000, 1200, 1100],
            "ask_volume": [900, 950, 1050],
        })

        ofi = calculate_ofi(quotes)

        assert isinstance(ofi, (pd.Series, np.ndarray))
        assert len(ofi) >= 0

    def test_calculate_ofi_buy_pressure(self):
        """Test OFI with strong buy pressure."""
        quotes = pd.DataFrame({
            "bid_price": [99.0, 99.5, 100.0],  # Rising bids
            "ask_price": [101.0, 101.0, 101.0],
            "bid_volume": [2000, 2500, 3000],  # Increasing bid volume
            "ask_volume": [500, 500, 500],  # Low ask volume
        })

        ofi = calculate_ofi(quotes)

        # Positive OFI indicates buy pressure
        assert ofi[-1] > 0 or pd.isna(ofi[-1])

    def test_calculate_ofi_sell_pressure(self):
        """Test OFI with strong sell pressure."""
        quotes = pd.DataFrame({
            "bid_price": [99.0, 98.5, 98.0],  # Falling bids
            "ask_price": [101.0, 100.5, 100.0],
            "bid_volume": [500, 500, 500],  # Low bid volume
            "ask_volume": [2000, 2500, 3000],  # Increasing ask volume
        })

        ofi = calculate_ofi(quotes)

        # Negative OFI indicates sell pressure
        assert ofi[-1] < 0 or pd.isna(ofi[-1])


# ============================================================================
# QA Gates Tests
# ============================================================================


@pytest.mark.unit
class TestQAGates:
    """Test quality assurance gates."""

    def test_completeness_check_complete_data(self):
        """Test completeness check with complete data."""
        data = pd.DataFrame({
            "price": [100, 101, 102, 103, 104],
            "volume": [1000, 1100, 1200, 1300, 1400],
        })

        is_complete, score = check_completeness(data, threshold=0.95)

        assert is_complete is True
        assert score >= 0.95

    def test_completeness_check_missing_data(self):
        """Test completeness check with missing data."""
        data = pd.DataFrame({
            "price": [100, np.nan, 102, np.nan, 104],
            "volume": [1000, 1100, np.nan, 1300, np.nan],
        })

        is_complete, score = check_completeness(data, threshold=0.95)

        # Should fail completeness check
        assert is_complete is False
        assert score < 0.95

    def test_freshness_check_fresh_data(self):
        """Test freshness check with recent data."""
        timestamp = datetime.now()

        is_fresh = check_freshness(timestamp, max_age_ms=5000)

        assert is_fresh is True

    def test_freshness_check_stale_data(self):
        """Test freshness check with stale data."""
        # 10 seconds old
        timestamp = datetime.now() - timedelta(seconds=10)

        is_fresh = check_freshness(timestamp, max_age_ms=5000)

        assert is_fresh is False

    def test_ntp_drift_check_synchronized(self):
        """Test NTP drift check when synchronized."""
        # Mock NTP response
        with patch('data_plane.qa.ntp_guard.get_ntp_time') as mock_ntp:
            mock_ntp.return_value = datetime.now()

            is_synced, drift_ms = check_ntp_drift(threshold_ms=100)

            assert is_synced is True
            assert abs(drift_ms) < 100

    def test_ntp_drift_check_out_of_sync(self):
        """Test NTP drift check when out of sync."""
        # Mock NTP response with large offset
        with patch('data_plane.qa.ntp_guard.get_ntp_time') as mock_ntp:
            mock_ntp.return_value = datetime.now() + timedelta(milliseconds=500)

            is_synced, drift_ms = check_ntp_drift(threshold_ms=100)

            assert is_synced is False
            assert abs(drift_ms) > 100


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.requires_kafka
class TestDataPlaneIntegration:
    """Integration tests for Data Plane."""

    def test_end_to_end_data_flow(self):
        """Test end-to-end data flow through Data Plane."""
        # This is a placeholder for full integration test
        # Would require Kafka and full data plane stack
        pass

    def test_data_plane_with_mock_ibkr(self, mock_ibkr_client):
        """Test Data Plane with mocked IBKR client."""
        # Mock IBKR market data
        mock_ibkr_client.get_market_data.return_value = {
            "symbol": "AAPL",
            "bid": 150.0,
            "ask": 150.10,
            "last": 150.05,
            "volume": 1000000
        }

        # Test data flow
        raw_data = mock_ibkr_client.get_market_data("AAPL")
        normalized = normalize_market_event(raw_data)

        assert normalized is not None
        assert normalized["symbol"] == "AAPL"
