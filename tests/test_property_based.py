"""
Property-Based Tests using Hypothesis

These tests verify mathematical properties and invariants that should
hold for all valid inputs, not just specific test cases.

Tests cover:
- Mathematical properties (linearity, symmetry, invariance)
- Numerical stability
- Constraint satisfaction
- Idempotence and consistency
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, settings, strategies as st, assume
from hypothesis.extra.pandas import column, data_frames, range_indexes

from algo_trade.core.signals.base_signals import zscore_dynamic
from algo_trade.core.signals.composite_signals import combine_signals, orthogonalize_signals
from algo_trade.core.risk.covariance import _ewma_cov, _lw_cov, _fix_psd
from algo_trade.core.optimization.qp_solver import solve_qp


# ============================================================================
# Hypothesis Strategies (Data Generators)
# ============================================================================

@st.composite
def returns_dataframe(draw, min_rows=30, max_rows=100, min_cols=2, max_cols=5):
    """Generate valid returns DataFrame."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    n_cols = draw(st.integers(min_value=min_cols, max_value=max_cols))

    # Generate returns between -10% and +10% daily
    data = draw(st.lists(
        st.lists(
            st.floats(min_value=-0.10, max_value=0.10, allow_nan=False, allow_infinity=False),
            min_size=n_cols,
            max_size=n_cols
        ),
        min_size=n_rows,
        max_size=n_rows
    ))

    dates = pd.date_range('2024-01-01', periods=n_rows, freq='D')
    columns = [f'ASSET_{i}' for i in range(n_cols)]

    return pd.DataFrame(data, index=dates, columns=columns)


@st.composite
def positive_definite_matrix(draw, size):
    """Generate positive definite correlation matrix."""
    # Generate random correlation matrix via Cholesky
    A = draw(st.lists(
        st.lists(st.floats(min_value=-1, max_value=1), min_size=size, max_size=size),
        min_size=size,
        max_size=size
    ))

    A = np.array(A)
    # Make symmetric
    A = (A + A.T) / 2
    # Add identity to ensure PD
    A = A + np.eye(size) * 2.0

    # Convert to DataFrame
    idx = [f'A{i}' for i in range(size)]
    return pd.DataFrame(A, index=idx, columns=idx)


# ============================================================================
# Property Tests for Z-Score
# ============================================================================

@pytest.mark.property
class TestZScoreProperties:
    """Property-based tests for z-score normalization."""

    @given(df=returns_dataframe(min_rows=50, max_rows=100))
    @settings(deadline=None, max_examples=20)
    def test_zscore_output_shape(self, df):
        """Property: z-score output has same shape as input."""
        result = zscore_dynamic(df, win_vol=10, win_mean=10)

        assert result.shape == df.shape
        assert list(result.columns) == list(df.columns)
        assert list(result.index) == list(df.index)

    @given(df=returns_dataframe(min_rows=50), scale=st.floats(min_value=0.1, max_value=10.0))
    @settings(deadline=None, max_examples=15)
    def test_zscore_scale_invariance(self, df, scale):
        """Property: z-score is scale-invariant (scaling input doesn't change z-score much)."""
        assume(not df.isnull().all().all())

        z1 = zscore_dynamic(df, win_vol=10, win_mean=10)
        z2 = zscore_dynamic(df * scale, win_vol=10, win_mean=10)

        # Z-scores should be similar (not exactly equal due to rolling windows)
        # After warm-up period
        stable = z1.iloc[20:]
        stable2 = z2.iloc[20:]

        if not stable.empty and not stable2.empty:
            # Check correlation (should be very high)
            for col in df.columns:
                corr = stable[col].corr(stable2[col])
                if not np.isnan(corr):
                    assert corr > 0.90, f"Z-score should be scale-invariant for {col}"


# ============================================================================
# Property Tests for Signal Combination
# ============================================================================

@pytest.mark.property
class TestCombineSignalsProperties:
    """Property-based tests for signal combination."""

    @given(
        n_signals=st.integers(min_value=2, max_value=5),
        n_rows=st.integers(min_value=30, max_value=100),
        n_cols=st.integers(min_value=2, max_value=5)
    )
    @settings(deadline=None, max_examples=15)
    def test_combine_linearity(self, n_signals, n_rows, n_cols):
        """Property: Signal combination is linear."""
        dates = pd.date_range('2024-01-01', periods=n_rows, freq='D')
        columns = [f'A{i}' for i in range(n_cols)]

        # Generate signals
        np.random.seed(42)
        signals = {}
        for i in range(n_signals):
            signals[f'S{i}'] = pd.DataFrame(
                np.random.randn(n_rows, n_cols),
                index=dates,
                columns=columns
            )

        # Generate weights (sum to 1)
        weights_raw = np.random.rand(n_signals)
        weights_dict = {f'S{i}': weights_raw[i] / weights_raw.sum() for i in range(n_signals)}

        # Combine
        combined = combine_signals(signals, weights_dict)

        # Manual calculation
        expected = sum(weights_dict[k] * signals[k] for k in signals.keys())

        pd.testing.assert_frame_equal(combined, expected, rtol=1e-10)

    @given(n_cols=st.integers(min_value=2, max_value=5))
    @settings(deadline=None, max_examples=10)
    def test_combine_zero_weights_gives_zero(self, n_cols):
        """Property: Zero weights should give zero output."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        columns = [f'A{i}' for i in range(n_cols)]

        signals = {
            'S1': pd.DataFrame(np.random.randn(50, n_cols), index=dates, columns=columns),
            'S2': pd.DataFrame(np.random.randn(50, n_cols), index=dates, columns=columns),
        }

        weights = {'S1': 0.0, 'S2': 0.0}

        combined = combine_signals(signals, weights)

        # Should be all zeros
        assert (combined == 0).all().all()


# ============================================================================
# Property Tests for Covariance
# ============================================================================

@pytest.mark.property
class TestCovarianceProperties:
    """Property-based tests for covariance matrices."""

    @given(df=returns_dataframe(min_rows=50, min_cols=2, max_cols=4))
    @settings(deadline=None, max_examples=15)
    def test_ewma_cov_symmetry(self, df):
        """Property: EWMA covariance matrix is symmetric."""
        cov = _ewma_cov(df, halflife=10)

        if not cov.empty:
            np.testing.assert_array_almost_equal(
                cov.values,
                cov.values.T,
                decimal=10,
                err_msg="Covariance matrix must be symmetric"
            )

    @given(df=returns_dataframe(min_rows=50, min_cols=2, max_cols=4))
    @settings(deadline=None, max_examples=15)
    def test_lw_cov_positive_definite(self, df):
        """Property: Ledoit-Wolf covariance is positive semi-definite."""
        cov = _lw_cov(df)

        if not cov.empty:
            eigenvalues = np.linalg.eigvalsh(cov.values)
            assert np.all(eigenvalues > -1e-8), "Covariance must be PSD"

    @given(
        df=returns_dataframe(min_rows=50, min_cols=3, max_cols=3),
        scale=st.floats(min_value=0.5, max_value=3.0)
    )
    @settings(deadline=None, max_examples=10)
    def test_cov_scaling_property(self, df, scale):
        """Property: Cov(k*X) = k^2 * Cov(X)."""
        cov1 = _ewma_cov(df, halflife=20)
        cov2 = _ewma_cov(df * scale, halflife=20)

        if not cov1.empty and not cov2.empty:
            # cov2 should be approximately scale^2 * cov1
            ratio = cov2.values / (cov1.values + 1e-12)

            # Check ratio is close to scale^2
            expected_ratio = scale ** 2

            # Allow some tolerance
            assert np.abs(ratio - expected_ratio).mean() < 0.5, \
                f"Scaling property violated: expected {expected_ratio:.2f}, got {ratio.mean():.2f}"

    @given(mat=positive_definite_matrix(size=3))
    @settings(deadline=None, max_examples=15)
    def test_fix_psd_idempotent(self, mat):
        """Property: Fixing PSD matrix twice gives same result."""
        fixed1 = _fix_psd(mat)
        fixed2 = _fix_psd(fixed1)

        if not fixed1.empty:
            pd.testing.assert_frame_equal(fixed1, fixed2, rtol=1e-6)


# ============================================================================
# Property Tests for QP Solver
# ============================================================================

@pytest.mark.property
class TestQPSolverProperties:
    """Property-based tests for QP solver."""

    @given(
        n_assets=st.integers(min_value=2, max_value=5),
        gross_lim=st.floats(min_value=0.5, max_value=2.0),
        net_lim=st.floats(min_value=0.3, max_value=1.0)
    )
    @settings(deadline=None, max_examples=15)
    def test_qp_constraint_satisfaction(self, n_assets, gross_lim, net_lim):
        """Property: QP solution always satisfies constraints."""
        assets = [f'A{i}' for i in range(n_assets)]

        # Generate random problem
        np.random.seed(42)
        mu_hat = pd.Series(np.random.uniform(0.05, 0.15, n_assets), index=assets)

        # Generate PSD covariance
        L = np.random.randn(n_assets, n_assets) * 0.05
        C_matrix = L @ L.T + np.eye(n_assets) * 0.02
        C = pd.DataFrame(C_matrix, index=assets, columns=assets)

        w_prev = pd.Series(np.random.uniform(-0.2, 0.2, n_assets), index=assets)

        params = {
            "TURNOVER_PEN": 0.002,
            "RIDGE_PEN": 1e-4,
            "BOX_LIM": 0.30,
            "VOL_TARGET": 0.15,
        }

        result = solve_qp(mu_hat, C, w_prev, gross_lim, net_lim, params)

        # Check constraints
        gross = result.abs().sum()
        net = result.sum()

        assert gross <= gross_lim + 1e-5, f"Gross constraint violated: {gross:.4f} > {gross_lim}"
        assert -net_lim - 1e-5 <= net <= net_lim + 1e-5, f"Net constraint violated: {net:.4f}"
        assert result.max() <= 0.30 + 1e-5, "Box upper constraint violated"
        assert result.min() >= -0.30 - 1e-5, "Box lower constraint violated"

    @given(n_assets=st.integers(min_value=2, max_value=4))
    @settings(deadline=None, max_examples=10)
    def test_qp_optimal_for_unconstrained_quadratic(self, n_assets):
        """Property: QP finds optimal solution for simple quadratic problem."""
        assets = [f'A{i}' for i in range(n_assets)]

        # Simple problem: minimize variance only (no return)
        mu_hat = pd.Series(0.0, index=assets)

        # Diagonal covariance (independent assets)
        C = pd.DataFrame(np.eye(n_assets) * 0.04, index=assets, columns=assets)

        w_prev = pd.Series(0.0, index=assets)

        params = {
            "TURNOVER_PEN": 0.0,  # No turnover penalty
            "RIDGE_PEN": 0.0,     # No ridge penalty
            "BOX_LIM": 1.0,
            "VOL_TARGET": 1.0,    # No vol targeting
        }

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=1.0, params=params)

        # With no returns and independent assets, optimal is near-zero (minimize variance)
        assert result.abs().sum() < 0.5, "Should minimize to near-zero weights"

    @given(n_assets=st.integers(min_value=2, max_value=4))
    @settings(deadline=None, max_examples=10)
    def test_qp_deterministic(self, n_assets):
        """Property: Same input produces same output (determinism)."""
        assets = [f'A{i}' for i in range(n_assets)]

        np.random.seed(42)
        mu_hat = pd.Series(np.random.uniform(0.05, 0.15, n_assets), index=assets)

        L = np.random.randn(n_assets, n_assets) * 0.05
        C_matrix = L @ L.T + np.eye(n_assets) * 0.02
        C = pd.DataFrame(C_matrix, index=assets, columns=assets)

        w_prev = pd.Series(np.random.uniform(-0.1, 0.1, n_assets), index=assets)

        params = {
            "TURNOVER_PEN": 0.002,
            "RIDGE_PEN": 1e-4,
            "BOX_LIM": 0.25,
            "VOL_TARGET": 0.12,
        }

        # Solve twice
        result1 = solve_qp(mu_hat, C, w_prev, 1.0, 0.8, params)
        result2 = solve_qp(mu_hat, C, w_prev, 1.0, 0.8, params)

        pd.testing.assert_series_equal(result1, result2, rtol=1e-6)


# ============================================================================
# Property Tests for Orthogonalization
# ============================================================================

@pytest.mark.property
class TestOrthogonalizationProperties:
    """Property-based tests for signal orthogonalization."""

    @given(n_signals=st.integers(min_value=2, max_value=4))
    @settings(deadline=None, max_examples=10)
    def test_orthogonalization_preserves_signal_count(self, n_signals):
        """Property: Orthogonalization preserves number of signals."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        assets = ['A', 'B', 'C']

        np.random.seed(42)
        signals = {}
        for i in range(n_signals):
            signals[f'S{i}'] = pd.DataFrame(
                np.random.randn(100, 3),
                index=dates,
                columns=assets
            )

        ortho = orthogonalize_signals(signals)

        assert len(ortho) == len(signals)
        assert set(ortho.keys()) == set(signals.keys())

    @given(n_rows=st.integers(min_value=50, max_value=100))
    @settings(deadline=None, max_examples=10)
    def test_orthogonalization_output_shape(self, n_rows):
        """Property: Orthogonalization preserves DataFrame shapes."""
        dates = pd.date_range('2024-01-01', periods=n_rows, freq='D')
        assets = ['A', 'B']

        signals = {
            'S1': pd.DataFrame(np.random.randn(n_rows, 2), index=dates, columns=assets),
            'S2': pd.DataFrame(np.random.randn(n_rows, 2), index=dates, columns=assets),
        }

        ortho = orthogonalize_signals(signals)

        for key in signals.keys():
            assert ortho[key].shape == signals[key].shape


# ============================================================================
# Metamorphic Properties
# ============================================================================

@pytest.mark.property
class TestMetamorphicProperties:
    """Metamorphic testing: relationships between outputs for related inputs."""

    @given(
        df=returns_dataframe(min_rows=50, min_cols=3, max_cols=3),
        noise_scale=st.floats(min_value=0.001, max_value=0.01)
    )
    @settings(deadline=None, max_examples=10)
    def test_small_input_perturbation_small_output_change(self, df, noise_scale):
        """Metamorphic: Small input change → Small output change (continuity)."""
        np.random.seed(42)

        # Original covariance
        cov1 = _ewma_cov(df, halflife=30)

        # Perturbed input
        noise = np.random.randn(*df.shape) * noise_scale
        df_perturbed = df + noise

        # Perturbed covariance
        cov2 = _ewma_cov(df_perturbed, halflife=30)

        if not cov1.empty and not cov2.empty:
            # Difference should be small
            diff = np.abs(cov1.values - cov2.values).mean()

            # Difference should scale with noise
            assert diff < 0.01, f"Small perturbation caused large change: {diff:.6f}"

    @given(n_assets=st.integers(min_value=2, max_value=4))
    @settings(deadline=None, max_examples=10)
    def test_qp_increasing_constraint_reduces_feasible_region(self, n_assets):
        """Metamorphic: Tightening constraints → Different/more conservative solution."""
        assets = [f'A{i}' for i in range(n_assets)]

        np.random.seed(42)
        mu_hat = pd.Series(np.random.uniform(0.08, 0.15, n_assets), index=assets)

        L = np.random.randn(n_assets, n_assets) * 0.05
        C_matrix = L @ L.T + np.eye(n_assets) * 0.02
        C = pd.DataFrame(C_matrix, index=assets, columns=assets)

        w_prev = pd.Series(0.2, index=assets)

        params = {
            "TURNOVER_PEN": 0.002,
            "RIDGE_PEN": 1e-4,
            "BOX_LIM": 0.25,
            "VOL_TARGET": 0.15,
        }

        # Loose constraints
        result_loose = solve_qp(mu_hat, C, w_prev, gross_lim=1.5, net_lim=1.0, params=params)

        # Tight constraints
        result_tight = solve_qp(mu_hat, C, w_prev, gross_lim=0.8, net_lim=0.5, params=params)

        # Tighter constraints should result in less aggressive position
        gross_loose = result_loose.abs().sum()
        gross_tight = result_tight.abs().sum()

        assert gross_tight <= gross_loose + 1e-5, \
            "Tighter constraints should not increase gross exposure"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'property'])
