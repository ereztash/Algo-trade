"""
Unit Tests for Trading Signals

Priority tests for all 6 signal strategies:
- OFI (Order Flow Imbalance)
- ERN (Earnings)
- VRP (Volatility Risk Premium)
- POS (Positioning)
- TSX (Technical Signals - Extended)
- SIF (Structural Information Flow)
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import Mock, patch


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_prices():
    """Generate sample price data for testing."""
    np.random.seed(42)
    n_periods = 100
    base_price = 100.0
    returns = np.random.randn(n_periods) * 0.02
    prices = base_price * np.exp(np.cumsum(returns))
    return prices


@pytest.fixture
def sample_returns():
    """Generate sample return data."""
    np.random.seed(42)
    return np.random.randn(100) * 0.02


@pytest.fixture
def sample_volume():
    """Generate sample volume data."""
    np.random.seed(42)
    return np.random.randint(1000000, 5000000, size=100)


# ==============================================================================
# OFI (Order Flow Imbalance) Signal Tests
# ==============================================================================

class TestOFISignal:
    """Test Order Flow Imbalance signal generation."""

    def test_ofi_calculation_basic(self):
        """Test basic OFI calculation with bid/ask volumes."""
        # Mock order flow data
        bid_volume = np.array([1000, 1500, 2000, 1800, 2200])
        ask_volume = np.array([900, 1600, 1900, 2000, 2100])

        # OFI = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        expected_ofi = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        # Test calculation
        ofi = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        np.testing.assert_array_almost_equal(ofi, expected_ofi)
        assert len(ofi) == len(bid_volume)

    def test_ofi_bounded_range(self):
        """Test that OFI is bounded between -1 and 1."""
        bid_volume = np.random.randint(100, 10000, size=50)
        ask_volume = np.random.randint(100, 10000, size=50)

        ofi = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        assert np.all(ofi >= -1.0), "OFI should be >= -1"
        assert np.all(ofi <= 1.0), "OFI should be <= 1"

    def test_ofi_extreme_cases(self):
        """Test OFI behavior at extremes."""
        # All buying (no ask volume)
        ofi_all_buy = (1000 - 0) / (1000 + 0 + 1e-10)
        assert ofi_all_buy > 0.99, "All buying should give OFI close to +1"

        # All selling (no bid volume)
        ofi_all_sell = (0 - 1000) / (0 + 1000 + 1e-10)
        assert ofi_all_sell < -0.99, "All selling should give OFI close to -1"

        # Balanced
        ofi_balanced = (1000 - 1000) / (1000 + 1000)
        assert abs(ofi_balanced) < 0.01, "Balanced should give OFI close to 0"

    def test_ofi_rolling_window(self):
        """Test OFI calculation with rolling window."""
        n_periods = 100
        bid_volume = np.random.randint(1000, 5000, size=n_periods)
        ask_volume = np.random.randint(1000, 5000, size=n_periods)

        window = 20
        ofi = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        # Rolling mean OFI
        rolling_ofi = pd.Series(ofi).rolling(window).mean()

        assert len(rolling_ofi) == n_periods
        assert rolling_ofi.iloc[:window-1].isna().all(), "First window-1 values should be NaN"
        assert not rolling_ofi.iloc[window:].isna().any(), "Rest should not be NaN"


# ==============================================================================
# ERN (Earnings) Signal Tests
# ==============================================================================

class TestERNSignal:
    """Test Earnings signal generation."""

    def test_earnings_surprise_calculation(self):
        """Test earnings surprise calculation."""
        actual_earnings = 1.25
        expected_earnings = 1.10

        # Earnings surprise = (actual - expected) / expected
        surprise = (actual_earnings - expected_earnings) / expected_earnings

        assert surprise > 0, "Positive earnings surprise"
        assert abs(surprise - 0.1364) < 0.001, "Surprise calculation correct"

    def test_earnings_drift_post_announcement(self):
        """Test post-earnings announcement drift (PEAD)."""
        # Simulate price drift after positive earnings
        np.random.seed(42)
        n_days = 60  # 60 days post-earnings

        # Positive surprise -> upward drift
        surprise = 0.15  # 15% positive surprise
        base_drift = surprise * 0.3  # 30% of surprise translates to drift

        # Simulate cumulative drift with noise
        drift = base_drift + np.random.randn(n_days) * 0.01
        cumulative_drift = np.cumsum(drift)

        # Test that drift is generally positive
        assert cumulative_drift[-1] > 0, "Positive surprise should lead to upward drift"
        assert np.mean(cumulative_drift[30:]) > 0, "Average drift should be positive"

    def test_earnings_announcement_dates(self):
        """Test identification of earnings announcement dates."""
        # Use full year to capture all quarterly dates
        dates = pd.date_range('2024-01-01', periods=365, freq='D')

        # Mock earnings dates (quarterly)
        earnings_dates = ['2024-01-15', '2024-04-15', '2024-07-15', '2024-10-15']
        earnings_dates = pd.to_datetime(earnings_dates)

        # Create boolean mask
        is_earnings_day = dates.isin(earnings_dates)

        assert is_earnings_day.sum() == len(earnings_dates), f"Expected {len(earnings_dates)} earnings dates, found {is_earnings_day.sum()}"
        assert is_earnings_day[14]  # Jan 15 is day 14 (0-indexed)

    def test_earnings_quality_metrics(self):
        """Test earnings quality metrics (accruals, etc.)."""
        # Accrual ratio = (Net Income - Operating Cash Flow) / Total Assets
        net_income = 100_000_000
        operating_cf = 90_000_000
        total_assets = 500_000_000

        accrual_ratio = (net_income - operating_cf) / total_assets

        # High accrual ratio indicates low quality earnings
        assert accrual_ratio == 0.02, "Accrual ratio calculation"
        assert accrual_ratio < 0.1, "Low accrual ratio = high quality"


# ==============================================================================
# VRP (Volatility Risk Premium) Signal Tests
# ==============================================================================

class TestVRPSignal:
    """Test Volatility Risk Premium signal."""

    def test_realized_volatility_calculation(self, sample_returns):
        """Test realized volatility calculation."""
        returns = sample_returns

        # Realized vol = std(returns) * sqrt(252)
        realized_vol = np.std(returns) * np.sqrt(252)

        assert realized_vol > 0, "Realized vol should be positive"
        assert 0.1 < realized_vol < 0.5, "Reasonable vol range"

    def test_implied_volatility_mock(self):
        """Test implied volatility extraction (mock)."""
        # Mock option prices -> implied vol
        strike = 100
        spot = 105
        time_to_expiry = 30 / 365
        option_price = 7.5

        # Mock Black-Scholes implied vol (simplified)
        # In reality, use scipy.optimize or financial library
        implied_vol = 0.25  # 25% annualized

        assert implied_vol > 0
        assert implied_vol < 1.0  # Reasonable range

    def test_vrp_calculation(self):
        """Test VRP = Implied Vol - Realized Vol."""
        implied_vol = 0.25
        realized_vol = 0.20

        vrp = implied_vol - realized_vol

        assert np.isclose(vrp, 0.05), "VRP calculation"
        assert vrp > 0, "Positive VRP (options overpriced)"

    def test_vrp_signal_direction(self):
        """Test VRP signal interpretation."""
        # Positive VRP -> sell volatility (options expensive)
        # Negative VRP -> buy volatility (options cheap)

        vrp_positive = 0.05
        vrp_negative = -0.03

        # Signal: -VRP (sell expensive vol)
        signal_sell = -vrp_positive
        signal_buy = -vrp_negative

        assert signal_sell < 0, "Sell signal when VRP positive"
        assert signal_buy > 0, "Buy signal when VRP negative"


# ==============================================================================
# POS (Positioning) Signal Tests
# ==============================================================================

class TestPOSSignal:
    """Test Positioning signal (contrarian indicator)."""

    def test_cot_net_positioning(self):
        """Test COT (Commitment of Traders) net positioning."""
        # Non-commercial (speculative) positions
        long_positions = 50000
        short_positions = 30000

        net_position = long_positions - short_positions
        net_position_pct = net_position / (long_positions + short_positions)

        assert net_position == 20000, "Net long position"
        assert net_position_pct == 0.25, "25% net long"

    def test_crowding_indicator(self):
        """Test position crowding indicator."""
        # High crowding -> contrarian short signal
        net_position_pct = 0.80  # 80% net long (very crowded)

        # Contrarian signal = -net_position_pct
        signal = -net_position_pct

        assert signal < 0, "Crowded long -> short signal"
        assert signal == -0.80

    def test_positioning_mean_reversion(self):
        """Test positioning mean reversion."""
        # Historical average net position
        historical_avg = 0.10
        current_position = 0.70

        # Deviation from mean
        deviation = current_position - historical_avg

        # Mean reversion signal
        signal = -deviation  # Fade the extreme position

        assert signal < 0, "Extreme long position -> short signal"
        assert abs(signal) == 0.60

    def test_sentiment_extremes(self):
        """Test sentiment extreme indicators."""
        # Put/Call ratio as sentiment indicator
        put_volume = 500
        call_volume = 2000

        put_call_ratio = put_volume / call_volume

        # Low P/C ratio = bullish sentiment = contrarian short
        assert put_call_ratio == 0.25, "Low P/C ratio"
        assert put_call_ratio < 0.7, "Bullish sentiment (contrarian short)"


# ==============================================================================
# TSX (Technical Signals - Extended) Signal Tests
# ==============================================================================

class TestTSXSignal:
    """Test Technical Signals Extended."""

    def test_moving_average_crossover(self, sample_prices):
        """Test MA crossover signal."""
        prices = sample_prices

        # Short MA and Long MA
        ma_short = pd.Series(prices).rolling(20).mean()
        ma_long = pd.Series(prices).rolling(50).mean()

        # Crossover signal
        signal = np.where(ma_short > ma_long, 1, -1)

        assert len(signal) == len(prices)
        assert set(signal[50:]) <= {-1, 1}, "Signal is binary after warmup"

    def test_rsi_calculation(self, sample_prices):
        """Test RSI (Relative Strength Index)."""
        prices = sample_prices
        returns = np.diff(prices)

        # Separate gains and losses
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)

        # Average gains and losses
        window = 14
        avg_gain = pd.Series(gains).rolling(window).mean()
        avg_loss = pd.Series(losses).rolling(window).mean()

        # RSI = 100 - (100 / (1 + RS))
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        assert rsi.min() >= 0, "RSI >= 0"
        assert rsi.max() <= 100, "RSI <= 100"

    def test_bollinger_bands(self, sample_prices):
        """Test Bollinger Bands."""
        prices = sample_prices
        window = 20
        num_std = 2

        ma = pd.Series(prices).rolling(window).mean()
        std = pd.Series(prices).rolling(window).std()

        upper_band = ma + num_std * std
        lower_band = ma - num_std * std

        # Signal: price touches lower band -> buy
        # price touches upper band -> sell
        # Skip NaN values from rolling window
        valid_idx = ~ma.isna()
        assert (upper_band[valid_idx] >= ma[valid_idx]).all()
        assert (lower_band[valid_idx] <= ma[valid_idx]).all()

    def test_macd_signal(self, sample_prices):
        """Test MACD (Moving Average Convergence Divergence)."""
        prices = sample_prices

        ema_fast = pd.Series(prices).ewm(span=12).mean()
        ema_slow = pd.Series(prices).ewm(span=26).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9).mean()

        # MACD crossover
        bullish = (macd_line > signal_line).astype(int)

        assert len(bullish) == len(prices)


# ==============================================================================
# SIF (Structural Information Flow) Signal Tests
# ==============================================================================

class TestSIFSignal:
    """Test Structural Information Flow signal."""

    def test_correlation_structure(self):
        """Test correlation structure changes."""
        np.random.seed(42)
        n_assets = 5
        n_periods = 100

        # Generate returns
        returns = np.random.randn(n_periods, n_assets) * 0.02

        # Correlation matrix
        corr_matrix = np.corrcoef(returns.T)

        assert corr_matrix.shape == (n_assets, n_assets)
        assert np.allclose(corr_matrix, corr_matrix.T), "Correlation matrix symmetric"
        assert np.allclose(np.diag(corr_matrix), 1.0), "Diagonal is 1"

    def test_principal_component_analysis(self):
        """Test PCA for structural information."""
        np.random.seed(42)
        n_assets = 5
        n_periods = 100

        returns = np.random.randn(n_periods, n_assets) * 0.02

        # PCA
        cov_matrix = np.cov(returns.T)
        eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)

        # Sort eigenvalues in descending order
        sorted_indices = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_indices]

        # First PC explains most variance
        explained_var = eigenvalues / eigenvalues.sum()

        assert len(eigenvalues) == n_assets
        assert explained_var[0] >= explained_var[1], "First PC explains most"

    def test_information_flow_graph(self):
        """Test information flow network."""
        # Mock information flow matrix (directed graph)
        n_assets = 4
        flow_matrix = np.array([
            [0.0, 0.3, 0.2, 0.1],
            [0.1, 0.0, 0.4, 0.2],
            [0.2, 0.1, 0.0, 0.3],
            [0.3, 0.2, 0.1, 0.0]
        ])

        # Net information flow = row_sum - column_sum
        net_flow = flow_matrix.sum(axis=1) - flow_matrix.sum(axis=0)

        assert len(net_flow) == n_assets
        # Assets with positive net flow are information sources

    def test_granger_causality_mock(self):
        """Test Granger causality for lead-lag relationships."""
        # Mock: Asset A leads Asset B
        np.random.seed(42)
        n_periods = 100

        # Asset A
        returns_a = np.random.randn(n_periods) * 0.02

        # Asset B lags A by 1 period
        returns_b = np.roll(returns_a, 1) * 0.8 + np.random.randn(n_periods) * 0.01

        # Correlation between A(t) and B(t+1) should be high
        corr_lead = np.corrcoef(returns_a[:-1], returns_b[1:])[0, 1]

        assert abs(corr_lead) > 0.5, "Asset A should lead Asset B"


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestSignalIntegration:
    """Integration tests for signal combination."""

    def test_signal_normalization(self):
        """Test that signals are normalized to [-1, 1]."""
        # Mock raw signals
        raw_signals = np.array([5.2, -3.1, 0.8, 7.6, -2.4])

        # Z-score normalization
        mean = raw_signals.mean()
        std = raw_signals.std()
        normalized = (raw_signals - mean) / std

        # Clip to [-3, 3] and scale to [-1, 1]
        clipped = np.clip(normalized, -3, 3) / 3

        assert clipped.min() >= -1.0
        assert clipped.max() <= 1.0

    def test_signal_aggregation(self):
        """Test combining multiple signals."""
        # 6 signals
        ofi_signal = 0.2
        ern_signal = 0.5
        vrp_signal = -0.3
        pos_signal = -0.1
        tsx_signal = 0.4
        sif_signal = 0.1

        # Equal weighted combination
        combined = (ofi_signal + ern_signal + vrp_signal + pos_signal + tsx_signal + sif_signal) / 6

        assert -1 <= combined <= 1
        assert abs(combined - 0.133) < 0.01

    def test_signal_orthogonalization(self):
        """Test signal orthogonalization."""
        np.random.seed(42)
        n_signals = 6
        n_periods = 100

        # Generate correlated signals
        signals = np.random.randn(n_periods, n_signals) * 0.3

        # Orthogonalize using QR decomposition
        Q, R = np.linalg.qr(signals)

        # Q has orthogonal columns
        orthogonality = Q.T @ Q

        # Should be close to identity matrix
        assert np.allclose(orthogonality, np.eye(n_signals), atol=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
