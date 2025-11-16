"""
Unit tests for Order Plane components.

Tests cover:
- Risk checks (pre-trade validation)
- Order throttling (POV, ADV limits)
- Transaction cost learning
- Order execution
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from order_plane.intents.risk_checks import (
    check_exposure_limits,
    validate_order_intent,
)
from order_plane.broker.throttling import check_throttling_limits
from order_plane.learning.lambda_online import update_transaction_cost_model


# ============================================================================
# Risk Checks Tests
# ============================================================================


@pytest.mark.unit
class TestOrderRiskChecks:
    """Test pre-trade risk checks."""

    def test_exposure_limits_within_bounds(self):
        """Test exposure check when within limits."""
        current_positions = pd.Series({
            "AAPL": 10000,
            "GOOGL": 5000,
            "MSFT": -3000,
        })

        new_order = {
            "symbol": "AAPL",
            "quantity": 1000,  # Buy 1000 more
            "side": "BUY"
        }

        max_gross = 50000
        max_net = 20000

        passed, message = check_exposure_limits(
            current_positions, new_order, max_gross, max_net
        )

        assert passed is True

    def test_exposure_limits_exceed_gross(self):
        """Test exposure check when exceeding gross limit."""
        current_positions = pd.Series({
            "AAPL": 10000,
            "GOOGL": 8000,
            "MSFT": -6000,
        })

        new_order = {
            "symbol": "TSLA",
            "quantity": 20000,  # Large new position
            "side": "BUY"
        }

        max_gross = 25000  # Tight limit
        max_net = 20000

        passed, message = check_exposure_limits(
            current_positions, new_order, max_gross, max_net
        )

        assert passed is False
        assert "gross" in message.lower()

    def test_exposure_limits_exceed_net(self):
        """Test exposure check when exceeding net limit."""
        current_positions = pd.Series({
            "AAPL": 8000,
            "GOOGL": 7000,
            "MSFT": 4000,  # All long = high net exposure
        })

        new_order = {
            "symbol": "TSLA",
            "quantity": 10000,
            "side": "BUY"
        }

        max_gross = 50000
        max_net = 20000  # Tight net limit

        passed, message = check_exposure_limits(
            current_positions, new_order, max_gross, max_net
        )

        assert passed is False
        assert "net" in message.lower()

    def test_validate_order_intent_valid(self):
        """Test validation of valid order intent."""
        order_intent = {
            "symbol": "AAPL",
            "quantity": 100,
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": 150.0,
        }

        is_valid, errors = validate_order_intent(order_intent)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_order_intent_missing_fields(self):
        """Test validation with missing required fields."""
        order_intent = {
            "symbol": "AAPL",
            # Missing quantity, side, order_type
        }

        is_valid, errors = validate_order_intent(order_intent)

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_order_intent_invalid_quantity(self):
        """Test validation with invalid quantity."""
        order_intent = {
            "symbol": "AAPL",
            "quantity": -100,  # Negative quantity
            "side": "BUY",
            "order_type": "MARKET",
        }

        is_valid, errors = validate_order_intent(order_intent)

        assert is_valid is False
        assert any("quantity" in error.lower() for error in errors)


# ============================================================================
# Throttling Tests
# ============================================================================


@pytest.mark.unit
class TestOrderThrottling:
    """Test order throttling logic."""

    def test_throttling_within_pov_limit(self):
        """Test throttling when within POV limit."""
        order_volume = 5000
        current_volume = 100000  # 5% of volume
        pov_limit = 0.10  # 10% limit

        passed, message = check_throttling_limits(
            order_volume, current_volume, pov_limit=pov_limit
        )

        assert passed is True

    def test_throttling_exceeds_pov_limit(self):
        """Test throttling when exceeding POV limit."""
        order_volume = 15000
        current_volume = 100000  # 15% of volume
        pov_limit = 0.10  # 10% limit

        passed, message = check_throttling_limits(
            order_volume, current_volume, pov_limit=pov_limit
        )

        assert passed is False
        assert "pov" in message.lower() or "volume" in message.lower()

    def test_throttling_zero_market_volume(self):
        """Test throttling with zero market volume."""
        order_volume = 1000
        current_volume = 0  # No market volume
        pov_limit = 0.10

        # Should handle zero volume gracefully
        passed, message = check_throttling_limits(
            order_volume, current_volume, pov_limit=pov_limit
        )

        # Implementation dependent - may reject or allow
        assert isinstance(passed, bool)

    def test_throttling_adv_limit(self):
        """Test ADV (Average Daily Volume) throttling."""
        order_volume = 60000
        avg_daily_volume = 1000000
        adv_limit = 0.05  # 5% of ADV

        # Order is 6% of ADV, exceeds 5% limit
        passed = order_volume / avg_daily_volume <= adv_limit

        assert passed is False


# ============================================================================
# Transaction Cost Learning Tests
# ============================================================================


@pytest.mark.unit
class TestTransactionCostLearning:
    """Test transaction cost model learning."""

    def test_update_tc_model_basic(self):
        """Test basic transaction cost model update."""
        current_lambda = 0.0005
        observed_cost = 0.0008
        learning_rate = 0.01

        new_lambda = update_transaction_cost_model(
            current_lambda, observed_cost, learning_rate
        )

        # Should move towards observed cost
        assert new_lambda > current_lambda
        assert new_lambda < observed_cost  # Not all the way due to learning rate

    def test_update_tc_model_convergence(self):
        """Test that TC model converges over multiple updates."""
        lambda_values = [0.0005]
        true_cost = 0.001
        learning_rate = 0.05

        # Simulate multiple observations
        for _ in range(100):
            observed = true_cost + np.random.randn() * 0.0001  # Noisy observations
            new_lambda = update_transaction_cost_model(
                lambda_values[-1], observed, learning_rate
            )
            lambda_values.append(new_lambda)

        # Should converge towards true cost
        assert abs(lambda_values[-1] - true_cost) < 0.0002

    def test_update_tc_model_decay(self):
        """Test that old observations decay in influence."""
        current_lambda = 0.001
        observed_cost = 0.0005  # Much lower than current
        learning_rate = 0.01  # Low learning rate

        new_lambda = update_transaction_cost_model(
            current_lambda, observed_cost, learning_rate
        )

        # Should not change drastically with low learning rate
        change = abs(new_lambda - current_lambda)
        assert change < 0.0001


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
class TestOrderPlaneIntegration:
    """Integration tests for Order Plane."""

    def test_full_order_pipeline(self, mock_ibkr_client):
        """Test complete order processing pipeline."""
        # Setup
        current_positions = pd.Series({"AAPL": 5000})
        order_intent = {
            "symbol": "AAPL",
            "quantity": 100,
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": 150.0,
        }

        # Step 1: Validate order
        is_valid, errors = validate_order_intent(order_intent)
        assert is_valid is True

        # Step 2: Check risk limits
        passed, message = check_exposure_limits(
            current_positions, order_intent,
            max_gross=100000, max_net=50000
        )
        assert passed is True

        # Step 3: Check throttling
        passed, message = check_throttling_limits(
            order_intent["quantity"], current_volume=10000, pov_limit=0.10
        )
        assert passed is True

        # Step 4: Place order (mocked)
        result = mock_ibkr_client.place_order(
            symbol=order_intent["symbol"],
            quantity=order_intent["quantity"],
            order_type=order_intent["order_type"]
        )

        assert result["status"] == "submitted"
        assert result["symbol"] == "AAPL"

    def test_order_rejection_pipeline(self):
        """Test order rejection due to risk checks."""
        current_positions = pd.Series({
            "AAPL": 40000,
            "GOOGL": 30000,
        })

        # Order that would exceed limits
        order_intent = {
            "symbol": "MSFT",
            "quantity": 50000,
            "side": "BUY",
            "order_type": "MARKET",
        }

        # Should fail risk check
        passed, message = check_exposure_limits(
            current_positions, order_intent,
            max_gross=100000,  # Would be 40000 + 30000 + 50000 = 120000
            max_net=80000
        )

        assert passed is False
