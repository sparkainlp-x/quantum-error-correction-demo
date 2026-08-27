"""
benchmark.py — Monte Carlo performance benchmark for OES-32 MembraneShield.

Measures wall-clock throughput (trials/second) for each stage of the Monte
Carlo pipeline:

  1. perturbation generation  — _random_perturbation / _symmetric_perturbation
  2. flip admission            — request_flip (full gate pipeline)
  3. full run_cell             — all overhead included

Each benchmark is run for a configurable warm-up period followed by a timed
measurement window.  Results are printed as a formatted table and optionally
written to CSV.

Usage
-----
    python3 benchmark.py [options]

    --duration S      timed measurement window per stage, seconds  [default: 2.0]
    --warmup S        warm-up period per stage, seconds            [default: 0.5]
    --sectors S …     sector names ANY EVEN ODD FOLD8 to include   [default: ALL]
    --tau TAU         shield tolerance used for flip benchmarks     [default: 0.10]
    --amplitude A     perturbation amplitude for flip benchmarks    [default: 0.04]
    --seed SEED       random seed                                   [default: 42]
    --csv PATH        write results to CSV file
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from typing import List, Optional, Sequence

from membrane_shield import (
    MembraneShield, Role, Sector, ShieldDenied, WIDTH, zeros,
)
from monte_carlo import (
    _calibrate,
    _random_perturbation,
    _symmetric_perturbation,
)


# ---------------------------------------------------------------------------
# timing helpers
# ---------------------------------------------------------------------------

def _now() -> float:
    return time.perf_counter()


def _run_timed(fn, duration_s: float, warmup_s: float) -> tuple[int, float]:
    """
    Run *fn()* in a tight loop.

    Returns (count, elapsed_s) for the timed window only (warmup excluded).
    *fn* must be a zero-argument callable.
    """
    # warm-up
    deadline = _now() + warmup_s
    while _now() < deadline:
        fn()

    # timed window
    count = 0
    start = _now()
    deadline = start + duration_s
    while _now() < deadline:
        fn()
        count += 1
    elapsed = _now() - start
    return count, elapsed


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

class BenchResult:
    def __init__(self, name: str, sector: str, count: int, elapsed: float):
        self.name = name
        self.sector = sector
        self.count = count
        self.elapsed = elapsed

    @property
    def throughput(self) -> float:
        return self.count / self.elapsed if self.elapsed > 0 else 0.0

    def as_dict(self) -> dict:
        return {
            'benchmark': self.name,
            'sector': self.sector,
            'count': self.count,
            'elapsed_s': f'{self.elapsed:.3f}',
            'throughput_per_s': f'{self.throughput:,.0f}',
        }


# ---------------------------------------------------------------------------
# individual benchmarks
# ---------------------------------------------------------------------------

def bench_perturbation(
    sector: Sector,
    amplitude: float,
    duration_s: float,
    warmup_s: float,
    rng: random.Random,
) -> BenchResult:
    """Benchmark _symmetric_perturbation for the given sector."""
    def fn():
        _symmetric_perturbation(rng, amplitude, sector)

    count, elapsed = _run_timed(fn, duration_s, warmup_s)
    return BenchResult(
        name='perturbation_gen',
        sector=sector.value,
        count=count,
        elapsed=elapsed,
    )


def bench_flip(
    sector: Sector,
    tau: float,
    amplitude: float,
    duration_s: float,
    warmup_s: float,
    rng: random.Random,
    eps: float = 1e-9,
) -> BenchResult:
    """
    Benchmark request_flip end-to-end.

    Uses perturbations that are symmetric and well within tau so that the
    full pipeline runs without collapse (all gates pass → pure throughput).
    Shield is reset after collapse if it happens to occur.
    """
    sh, g, dec = _calibrate(tau, sector, eps)

    def fn():
        nonlocal sh, g, dec
        if sh.state.collapse:
            sh.reset_after_latch(g)
        p = _symmetric_perturbation(rng, amplitude, sector)
        new_b = [b + d for b, d in zip(sh.state.live.boundary, p)]
        try:
            sh.request_flip(dec, new_b, syndrome_ok=True)
        except ShieldDenied:
            pass  # count even denied attempts to measure gate throughput

    count, elapsed = _run_timed(fn, duration_s, warmup_s)
    return BenchResult(
        name='request_flip',
        sector=sector.value,
        count=count,
        elapsed=elapsed,
    )


def bench_full_run_cell(
    sector: Sector,
    tau: float,
    amplitude: float,
    trials_per_call: int,
    duration_s: float,
    warmup_s: float,
    rng: random.Random,
    eps: float = 1e-9,
) -> BenchResult:
    """
    Benchmark run_cell (full MC cell, including calibration setup and
    accounting overhead).  Throughput is reported in trials/s.
    """
    from monte_carlo import run_cell

    def fn():
        run_cell(amplitude, sector, tau, eps, trials_per_call, rng)

    count_calls, elapsed = _run_timed(fn, duration_s, warmup_s)
    total_trials = count_calls * trials_per_call
    return BenchResult(
        name='run_cell',
        sector=sector.value,
        count=total_trials,
        elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------

def run_benchmark(
    sectors: Sequence[Sector],
    tau: float,
    amplitude: float,
    duration_s: float,
    warmup_s: float,
    seed: int,
    quiet: bool = False,
) -> List[BenchResult]:
    results: List[BenchResult] = []
    rng = random.Random(seed)

    for sector in sectors:
        for name, fn in [
            ('perturbation_gen', lambda s=sector: bench_perturbation(s, amplitude, duration_s, warmup_s, random.Random(seed))),
            ('request_flip',     lambda s=sector: bench_flip(s, tau, amplitude, duration_s, warmup_s, random.Random(seed))),
            ('run_cell',         lambda s=sector: bench_full_run_cell(s, tau, amplitude, 200, duration_s, warmup_s, random.Random(seed))),
        ]:
            if not quiet:
                print(f'  {name:20s}  sector={sector.value:6s}  …', end=' ', flush=True)
            r = fn()
            results.append(r)
            if not quiet:
                print(f'{r.throughput:>12,.0f} /s   ({r.count:,} in {r.elapsed:.2f}s)')

    return results


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

_HEADER = ['benchmark', 'sector', 'count', 'elapsed_s', 'throughput_per_s']


def print_table(results: List[BenchResult]) -> None:
    col_w = [22, 8, 14, 12, 20]
    header = ''.join(h.rjust(w) for h, w in zip(_HEADER, col_w))
    sep = '-' * len(header)
    print(sep)
    print('OES-32 MEMBRANE SHIELD — Monte Carlo Benchmark')
    print(sep)
    print(header)
    print(sep)
    for r in results:
        row = r.as_dict()
        print(''.join(str(row[h]).rjust(w) for h, w in zip(_HEADER, col_w)))
    print(sep)


def write_csv(results: List[BenchResult], path: str) -> None:
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for r in results:
            writer.writerow(r.as_dict())
    print(f'Results written to {path}')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description='OES-32 MembraneShield Monte Carlo benchmark')
    p.add_argument('--duration', type=float, default=2.0,
                   help='timed measurement window per stage in seconds [default: 2.0]')
    p.add_argument('--warmup', type=float, default=0.5,
                   help='warm-up period per stage in seconds [default: 0.5]')
    p.add_argument('--sectors', nargs='+',
                   choices=['ANY', 'EVEN', 'ODD', 'FOLD8'],
                   default=['ANY', 'EVEN', 'ODD', 'FOLD8'],
                   help='sector modes to benchmark')
    p.add_argument('--tau', type=float, default=0.10,
                   help='shield residual tolerance [default: 0.10]')
    p.add_argument('--amplitude', type=float, default=0.04,
                   help='perturbation amplitude for flip benchmarks [default: 0.04]')
    p.add_argument('--seed', type=int, default=42,
                   help='random seed [default: 42]')
    p.add_argument('--csv', type=str, default=None,
                   help='write results to this CSV file')
    p.add_argument('--quiet', action='store_true',
                   help='suppress per-stage progress')
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    sectors = [Sector(s) for s in args.sectors]

    print(f'MembraneShield Monte Carlo Benchmark')
    print(f'  tau={args.tau}  amplitude={args.amplitude}  '
          f'duration={args.duration}s  warmup={args.warmup}s  seed={args.seed}')
    print(f'  Sectors: {[s.value for s in sectors]}')
    print()

    results = run_benchmark(
        sectors=sectors,
        tau=args.tau,
        amplitude=args.amplitude,
        duration_s=args.duration,
        warmup_s=args.warmup,
        seed=args.seed,
        quiet=args.quiet,
    )

    print()
    print_table(results)

    if args.csv:
        write_csv(results, args.csv)


if __name__ == '__main__':
    main()
