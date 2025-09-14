import numpy as np
import pandas as pd
from typing import List, Tuple
from itertools import combinations
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def purged_k_fold(df: pd.DataFrame, n_splits: int = 5, embargo_len: int = 10) -> List[Tuple[pd.Index, pd.Index]]:
    """
    Purged K-Fold Cross-Validation for time series data.
    This method addresses data leakage by removing a time-dependent embargo
    between training and validation sets.

    Args:
        df: The DataFrame to split.
        n_splits: The number of splits.
        embargo_len: The number of days to exclude between training and validation.
    
    Returns:
        A list of tuples, each containing the indices for the training and validation sets.
    """
    if df.empty or n_splits <= 1:
        logging.warning("DataFrame is empty or n_splits is too small. Returning empty split list.")
        return []

    idx = np.arange(df.shape[0])
    fold_sizes = np.full(n_splits, len(idx) // n_splits, dtype=int)
    fold_sizes[:len(idx) % n_splits] += 1
    bounds = np.cumsum(fold_sizes)
    starts = np.concatenate(([0], bounds[:-1]))
    
    splits = []
    for i in range(n_splits):
        val_start = starts[i]
        val_end = bounds[i]
        val_idx = idx[val_start:val_end]
        
        train_mask = np.ones_like(idx, dtype=bool)
        
        # Apply the purge and embargo logic
        purge_end = min(len(idx), val_start + embargo_len)
        embargo_start = max(0, val_end - embargo_len)
        
        # Exclude both the purge and embargo periods
        train_mask[val_start:purge_end] = False
        train_mask[embargo_start:val_end] = False
        train_mask[val_start:val_end] = False
        
        tr_idx = idx[train_mask]
        splits.append((pd.Index(tr_idx), pd.Index(val_idx)))
        
    return splits

def true_cscv_pbo(scores: np.ndarray, M: int = 16) -> float:
    """
    Cross-Sectional Combinatorially Sliced Cross-Validation (CSCV)
    This method measures the probability of backtest overfitting (PBO).
    It works by finding the best strategy on subsets of the data and checking
    if it performs better on a held-out set. A high score (close to 1)
    indicates a high probability of overfitting.

    Args:
        scores: An array of performance scores from the cross-validation folds.
        M: The number of blocks to split the data into for combinatorial testing.
    
    Returns:
        The PBO score.
    """
    n = len(scores)
    if n < M or M <= 1:
        logging.error(f"Data length ({n}) is less than the number of blocks ({M}) or M is too small. Returning 0.5.")
        return 0.5
        
    blocks = np.array_split(np.arange(n), M)
    neg = 0
    total = 0
    
    # Ensure there are enough blocks to split into training and validation
    if M < 2:
        logging.error("Number of blocks M must be at least 2 for CSCV. Returning 0.5.")
        return 0.5
        
    # Iterate through all combinations of training blocks
    for train_blocks_indices in combinations(range(M), M // 2):
        val_blocks_indices = [i for i in range(M) if i not in train_blocks_indices]
        
        train_idx = np.concatenate([blocks[i] for i in train_blocks_indices])
        val_idx = np.concatenate([blocks[i] for i in val_blocks_indices])

        if len(train_idx) == 0 or len(val_idx) == 0:
            continue

        train_scores = scores[train_idx]
        val_scores = scores[val_idx]
        
        # Find the best score in the training set
        best_train_idx = np.argmax(train_scores)
        best_train_score = train_scores[best_train_idx]
        
        # Check the performance of the best strategy on the validation set
        avg_val_score = val_scores.mean()

        if avg_val_score < best_train_score:
            neg += 1
        total += 1
        
    return neg / total if total > 0 else 0.5
