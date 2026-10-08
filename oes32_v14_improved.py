#!/usr/bin/env python3
"""
oes32_v14_improved.py
OES-32 toy simulation v14 (classical, SYNTHETIC)

METRIC_TAG=SYNTHETIC. This is a classical Python toy simulation. It uses no
qubits and implements no quantum error-correcting code. Metric names such as
"spooky correlation" and "entanglement entropy" are labels for hand-written
formulas below; they are not quantum measurements.

Known property: recovery success is drawn with probability
max(0.95, 1 - 0.7 * erasure_prob), so the success rate is ~95% by
construction whenever erasure_prob >= ~0.07. Values near 95% are
sampling outcomes of that hard-coded floor, not a measured error-correction rate.

The script models hand-written relationships between:
- Erasure Probability
- Coherence (Before / After Recovery)
- Spooky Correlation
- Entanglement Entropy
- System Collapses

Default run is 1,000,000 iterations (laptop-sized). Larger runs only reduce
sampling noise around the built-in formulas; they do not add evidence.
"""

import argparse
import logging
import sys
import random
from datetime import datetime
from typing import Dict, Any

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("oes32_v14")

def is_notebook() -> bool:
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except Exception:
        return False

# ====================== UPGRADED SPOOKY ARCHITECTURE ======================
def simulate_single_trial(erasure_prob: float) -> Dict[str, float]:
    """
    One SYNTHETIC trial of the OES-32 toy simulation.
    Metrics follow hand-written formulas (see module docstring).
    
    Args:
        erasure_prob: Simulated erasure probability (0.0-1.0)
    
    Returns:
        Dictionary containing trial metrics:
        - erasure_prob: Input erasure probability
        - coherence_before: heuristic score before the modelled recovery step (SYNTHETIC)
        - coherence_after: heuristic score after the modelled recovery step (SYNTHETIC)
        - recovery_success: 1 if the Bernoulli recovery draw succeeded, 0 otherwise
        - spooky_correlation: label for a hand-written formula of coherence_after;
          not a correlation or entanglement measurement (SYNTHETIC)
        - entanglement_entropy: label for a hand-written formula of coherence_after;
          not an entropy of any quantum state (SYNTHETIC)
        - system_collapse: 1 if coherence_after < 0.60, 0 otherwise (SYNTHETIC)
    """
    # 1. Base coherence before recovery
    base_coherence = 1.0 - (erasure_prob ** 0.95) * 1.05
    noise = random.gauss(0, 0.045)
    coherence_before = max(0.55, min(0.98, base_coherence + noise))

    # 2. Recovery success probability.
    #    NOTE: hard-coded floor of 0.95 -> success rate ~95% by construction (SYNTHETIC).
    recovery_success_prob = max(0.95, 1.0 - erasure_prob * 0.70)
    recovery_success = random.random() < recovery_success_prob

    # 3. Coherence after recovery
    if recovery_success:
        improvement = (0.98 - coherence_before) * random.uniform(0.85, 1.0)
        coherence_after = min(0.995, coherence_before + improvement)
    else:
        coherence_after = coherence_before * random.uniform(0.92, 0.98)

    # 4. Spooky correlation (stronger when recovery is good)
    spooky_correlation = 0.75 + (coherence_after - 0.55) * 0.45
    spooky_correlation = min(0.995, max(0.70, spooky_correlation + random.gauss(0, 0.02)))

    # 5. Entanglement entropy (lower = more coherent)
    entanglement_entropy = max(0.05, 1.2 - coherence_after * 1.1 + random.gauss(0, 0.08))

    # 6. System collapse flag
    system_collapse = coherence_after < 0.60

    return {
        "erasure_prob": erasure_prob,
        "coherence_before": round(coherence_before, 4),
        "coherence_after": round(coherence_after, 4),
        "recovery_success": int(recovery_success),
        "spooky_correlation": round(spooky_correlation, 4),
        "entanglement_entropy": round(entanglement_entropy, 4),
        "system_collapse": int(system_collapse)
    }

def run_benchmark(num_iterations: int = 1_000_000,
                  erasure_prob: float = 0.20,
                  verbose: bool = False) -> Dict[str, Any]:
    """
    Run the OES-32 toy simulation (SYNTHETIC) at the specified scale.
    
    Args:
        num_iterations: Number of Monte Carlo trials
        erasure_prob: Simulated erasure probability (0.0-1.0)
        verbose: Enable verbose logging
    
    Returns:
        Dictionary with aggregated benchmark results
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Starting OES-32 v14 toy simulation (SYNTHETIC): {num_iterations:,} iterations @ {erasure_prob*100:.0f}% erasure")

    results = []
    collapses = 0
    total_spooky = 0.0
    total_entropy = 0.0
    success_count = 0

    iterator = tqdm(range(num_iterations), desc="OES-32 v14") if HAS_TQDM else range(num_iterations)

    for _ in iterator:
        trial = simulate_single_trial(erasure_prob)
        results.append(trial)
        if trial["system_collapse"]:
            collapses += 1
        total_spooky += trial["spooky_correlation"]
        total_entropy += trial["entanglement_entropy"]
        if trial["recovery_success"]:
            success_count += 1

    avg_coherence_before = sum(r["coherence_before"] for r in results) / num_iterations
    avg_coherence_after = sum(r["coherence_after"] for r in results) / num_iterations
    avg_spooky = total_spooky / num_iterations
    avg_entropy = total_entropy / num_iterations
    success_rate = success_count / num_iterations
    collapse_rate = collapses / num_iterations

    return {
        "iterations": num_iterations,
        "erasure_prob": erasure_prob,
        "avg_coherence_before": round(avg_coherence_before, 4),
        "avg_coherence_after": round(avg_coherence_after, 4),
        "coherence_improvement": round(avg_coherence_after - avg_coherence_before, 4),
        "success_rate": round(success_rate, 4),
        "spooky_correlation": round(avg_spooky, 4),
        "entanglement_entropy": round(avg_entropy, 4),
        "collapse_rate": round(collapse_rate, 6),
        "timestamp": datetime.now().isoformat()
    }

def print_report(results: Dict[str, Any]) -> None:
    """Print the SYNTHETIC simulation report. Every metric is tagged SYNTHETIC."""
    print("\n" + "="*70)
    print(f"OES-32 v14 toy simulation report ({results['iterations']:,} iterations) [METRIC_TAG=SYNTHETIC]")
    print("="*70)
    print(f"Timestamp           : {results['timestamp']}")
    print(f"Iterations          : {results['iterations']:,}")
    print(f"Erasure Probability : {results['erasure_prob']*100:.0f}%")
    print(f"Seed                : {results.get('seed') if results.get('seed') is not None else 'none (non-deterministic)'}")
    print("-"*70)
    print(f"Coherence Before    : {results['avg_coherence_before']:.4f}")
    print(f"Coherence After     : {results['avg_coherence_after']:.4f}")
    print(f"Improvement         : +{results['coherence_improvement']:.4f} ({results['coherence_improvement']/results['avg_coherence_before']*100:.2f}%)")
    print(f"Success Rate        : {results['success_rate']*100:.2f}%  [SYNTHETIC: floor max(0.95, 1-0.7p) is hard-coded]")
    print(f"Spooky Correlation  : {results['spooky_correlation']:.4f}")
    print(f"Entanglement Entropy: {results['entanglement_entropy']:.4f}")
    print(f"System Collapse Rate: {results['collapse_rate']*100:.4f}%")
    print("-"*70)
    # Conditional status line (previously printed unconditionally).
    if results["collapse_rate"] == 0:
        print("Simulated collapses : none in this run [SYNTHETIC; not a stability claim]")
    else:
        print(f"Simulated collapses : {results['collapse_rate']*100:.4f}% of trials [SYNTHETIC]")
    print("All values above are outputs of hand-written formulas (METRIC_TAG=SYNTHETIC).")
    print("="*70 + "\n")

def main(num_iterations: int = 1_000_000,
         erasure_prob: float = 0.20,
         verbose: bool = False,
         seed: "int | None" = None) -> None:
    """Main entry point for the OES-32 toy simulation (SYNTHETIC).

    If ``seed`` is given, Python's ``random`` module is seeded so the printed
    metrics are reproducible (timestamp excepted).
    """
    if seed is not None:
        random.seed(seed)
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    logger.info("Starting OES-32 v14 toy simulation (classical, SYNTHETIC)")
    results = run_benchmark(
        num_iterations=num_iterations,
        erasure_prob=erasure_prob,
        verbose=verbose
    )
    results["seed"] = seed
    print_report(results)
    logger.info("Simulation run finished.")

# ====================== CLI ======================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OES-32 v14 toy simulation (classical, SYNTHETIC outputs)")
    parser.add_argument("--iterations", type=int, default=1_000_000,
                        help="Number of iterations (default: 1,000,000)")
    parser.add_argument("--erasure", type=float, default=0.20, help="Erasure probability (0.0-1.0)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed for Python's random module (reproducible SYNTHETIC output)")
    args, unknown = parser.parse_known_args()
    try:
        main(num_iterations=args.iterations, erasure_prob=args.erasure, verbose=args.verbose,
             seed=args.seed)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)

# ====================== COLAB USAGE ======================
"""
Google Colab:
!python oes32_v14_improved.py -v

# Quick test run
!python oes32_v14_improved.py --iterations 100000 --erasure 0.20 -v
"""
