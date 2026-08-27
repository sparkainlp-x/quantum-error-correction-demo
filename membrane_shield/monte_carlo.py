"""
monte_carlo.py — Monte Carlo simulation for the OES-32 MembraneShield.

Simulates random boundary perturbations through a calibrated MembraneShield
and collects statistics on flip admission, residual breaches (collapse), and
symmetry rejections across a sweep of error amplitudes and sector modes.

Usage
-----
    python3 monte_carlo.py [options]

    --trials N          trials per (amplitude, sector) cell  [default: 1000]
    --amplitudes A B …  space-separated max-perturbation values to sweep
                        [default: 0.01 0.03 0.05 0.08 0.12 0.20]
    --sectors S …       sector names ANY EVEN ODD FOLD8 to include
                        [default: ALL]
    --tau TAU           shield tolerance threshold            [default: 0.10]
    --eps EPS           symmetry tolerance (eps)             [default: 1e-9]
    --seed SEED         random seed for reproducibility      [default: 42]
    --csv PATH          write results to CSV file
    --quiet             suppress per-cell progress output

Output columns
--------------
    amplitude   max component magnitude of the random perturbation
    sector      Sector mode used for this cell
    trials      number of trials run
    admitted    flips accepted by the shield
    collapsed   residual breaches (collapse latched)
    sym_denied  flips denied due to symmetry check failure
    syn_denied  flips denied due to syndrome=False injection (control arm)
    admit_rate  admitted / trials
    collapse_rate   collapsed / trials
    avg_residual    mean max-residual across all admitted flips
    max_residual    maximum max-residual seen across all admitted flips
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from membrane_shield import (
    Face, MembraneShield, Role, Sector, ShieldDenied, WIDTH, mu, zeros,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _random_perturbation(rng: random.Random, amplitude: float) -> list:
    """Return a WIDTH-vector with each component drawn uniformly in [-amplitude, amplitude]."""
    return [rng.uniform(-amplitude, amplitude) for _ in range(WIDTH)]


def _symmetric_perturbation(rng: random.Random, amplitude: float, sector: Sector) -> list:
    """Return a perturbation that satisfies the declared sector symmetry."""
    base = _random_perturbation(rng, amplitude)
    if sector is Sector.ANY:
        return base
    if sector is Sector.EVEN:
        # Enforce d[i] == d[mu(i)]
        v = list(base)
        for i in range(WIDTH // 2):
            avg = (v[i] + v[mu(i)]) / 2.0
            v[i] = avg
            v[mu(i)] = avg
        return v
    if sector is Sector.ODD:
        # Enforce d[i] == -d[mu(i)]
        v = list(base)
        for i in range(WIDTH // 2):
            half = v[i] / 2.0
            v[i] = half
            v[mu(i)] = -half
        return v
    if sector is Sector.FOLD8:
        # Enforce d[a] == d[b] for each consecutive ring pair
        v = list(base)
        for k in range(4):
            ring = [(k + 4 * t) % WIDTH for t in range(8)]
            avg = sum(v[j] for j in ring) / 8.0
            for j in ring:
                v[j] = avg
        return v
    return base


def _calibrate(tau: float, sector: Sector, eps: float) -> tuple:
    """Return (shield, gardien_cap, decoder_cap) with a committed zero-reference calibration."""
    sh = MembraneShield()
    g = sh.issue(Role.GARDIEN, 'mc_gardien')
    c = sh.issue(Role.CALIBRATEUR, 'mc_calibrateur')
    ref = zeros()
    pid = sh.propose_calibration(g, ref, ref, tau)
    sh.countersign_calibration(c, pid)
    sh.commit_calibration(g, pid)
    sh.set_sector(g, sector, eps)
    dec = sh.issue(Role.DECODEUR, 'mc_decoder')
    return sh, g, dec


# ---------------------------------------------------------------------------
# per-cell result
# ---------------------------------------------------------------------------

@dataclass
class CellResult:
    amplitude: float
    sector: str
    trials: int
    admitted: int = 0
    collapsed: int = 0
    sym_denied: int = 0
    syn_denied: int = 0
    residuals: List[float] = field(default_factory=list)

    @property
    def admit_rate(self) -> float:
        return self.admitted / self.trials if self.trials else 0.0

    @property
    def collapse_rate(self) -> float:
        return self.collapsed / self.trials if self.trials else 0.0

    @property
    def avg_residual(self) -> Optional[float]:
        return sum(self.residuals) / len(self.residuals) if self.residuals else None

    @property
    def max_residual(self) -> Optional[float]:
        return max(self.residuals) if self.residuals else None

    def as_dict(self) -> dict:
        return {
            'amplitude': f'{self.amplitude:.6g}',
            'sector': self.sector,
            'trials': self.trials,
            'admitted': self.admitted,
            'collapsed': self.collapsed,
            'sym_denied': self.sym_denied,
            'syn_denied': self.syn_denied,
            'admit_rate': f'{self.admit_rate:.4f}',
            'collapse_rate': f'{self.collapse_rate:.6f}',
            'avg_residual': f'{self.avg_residual:.6g}' if self.avg_residual is not None else 'n/a',
            'max_residual': f'{self.max_residual:.6g}' if self.max_residual is not None else 'n/a',
        }


# ---------------------------------------------------------------------------
# single-cell simulation
# ---------------------------------------------------------------------------

def run_cell(
    amplitude: float,
    sector: Sector,
    tau: float,
    eps: float,
    trials: int,
    rng: random.Random,
    syndrome_fault_rate: float = 0.05,
) -> CellResult:
    """
    Run *trials* random flip attempts against a freshly calibrated shield.

    A small fraction (syndrome_fault_rate) of trials inject syndrome_ok=False
    to act as a control arm and confirm the shield correctly rejects them.

    The perturbation drawn for each trial is sector-symmetric so that the
    only rejection reason is a residual breach (collapse) or, when the sector
    is non-ANY and random rounding breaks the exact constraint, a symmetry
    failure.  This gives a clean picture of the residual gate.
    """
    result = CellResult(amplitude=amplitude, sector=sector.value, trials=trials)

    # Track live state across trials — reset after collapse
    sh, g, dec = _calibrate(tau, sector, eps)

    for _ in range(trials):
        # Occasionally inject a bad-syndrome trial as a control
        if rng.random() < syndrome_fault_rate:
            try:
                sh.request_flip(dec, zeros(), syndrome_ok=False)
            except ShieldDenied:
                result.syn_denied += 1
            # Collapse cannot happen from syndrome rejection; no reset needed
            continue

        # If shield is in collapsed state from a previous trial, reset it
        if sh.state.collapse:
            sh.reset_after_latch(g)

        perturbation = _symmetric_perturbation(rng, amplitude, sector)
        new_boundary = [b + p for b, p in zip(sh.state.live.boundary, perturbation)]

        try:
            sh.request_flip(dec, new_boundary, syndrome_ok=True)
            # Compute residual for bookkeeping (against reference, not live)
            res = max(
                abs(nb - rb)
                for nb, rb in zip(new_boundary, sh.state.reference.boundary)
            )
            result.admitted += 1
            result.residuals.append(res)
        except ShieldDenied as exc:
            msg = str(exc)
            if 'collapse' in msg or 'residual breach' in msg:
                result.collapsed += 1
            elif 'symmetry' in msg:
                result.sym_denied += 1
            # locked / other errors are counted implicitly

    return result


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------

def run_sweep(
    amplitudes: Sequence[float],
    sectors: Sequence[Sector],
    tau: float,
    eps: float,
    trials: int,
    seed: int,
    quiet: bool = False,
) -> List[CellResult]:
    results: List[CellResult] = []
    rng = random.Random(seed)

    for sector in sectors:
        for amplitude in amplitudes:
            if not quiet:
                print(f'  sector={sector.value:6s}  amplitude={amplitude:.4f}  …', end=' ', flush=True)
            cell = run_cell(amplitude, sector, tau, eps, trials, rng)
            results.append(cell)
            if not quiet:
                print(
                    f'admit={cell.admit_rate:.3f}  collapse={cell.collapse_rate:.4f}'
                    f'  sym_denied={cell.sym_denied}'
                )
    return results


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

_HEADER = ['amplitude', 'sector', 'trials', 'admitted', 'collapsed',
           'sym_denied', 'syn_denied', 'admit_rate', 'collapse_rate',
           'avg_residual', 'max_residual']


def print_table(results: List[CellResult]) -> None:
    col_w = [14, 8, 8, 10, 10, 10, 10, 12, 14, 14, 14]
    header = ''.join(h.rjust(w) for h, w in zip(_HEADER, col_w))
    sep = '-' * len(header)
    print(sep)
    print('OES-32 MEMBRANE SHIELD — Monte Carlo Sweep Results')
    print(sep)
    print(header)
    print(sep)
    for r in results:
        row = r.as_dict()
        print(''.join(str(row[h]).rjust(w) for h, w in zip(_HEADER, col_w)))
    print(sep)


def write_csv(results: List[CellResult], path: str) -> None:
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
    p = argparse.ArgumentParser(description='OES-32 MembraneShield Monte Carlo sweep')
    p.add_argument('--trials', type=int, default=1000,
                   help='trials per (amplitude, sector) cell [default: 1000]')
    p.add_argument('--amplitudes', type=float, nargs='+',
                   default=[0.01, 0.03, 0.05, 0.08, 0.12, 0.20],
                   help='perturbation amplitudes to sweep')
    p.add_argument('--sectors', nargs='+',
                   choices=['ANY', 'EVEN', 'ODD', 'FOLD8'],
                   default=['ANY', 'EVEN', 'ODD', 'FOLD8'],
                   help='sector modes to include')
    p.add_argument('--tau', type=float, default=0.10,
                   help='shield residual tolerance [default: 0.10]')
    p.add_argument('--eps', type=float, default=1e-9,
                   help='symmetry tolerance [default: 1e-9]')
    p.add_argument('--seed', type=int, default=42,
                   help='random seed [default: 42]')
    p.add_argument('--csv', type=str, default=None,
                   help='write results to this CSV file')
    p.add_argument('--quiet', action='store_true',
                   help='suppress per-cell progress')
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    sectors = [Sector(s) for s in args.sectors]

    print(f'MembraneShield Monte Carlo  |  tau={args.tau}  eps={args.eps}'
          f'  trials/cell={args.trials}  seed={args.seed}')
    print(f'Amplitudes : {args.amplitudes}')
    print(f'Sectors    : {[s.value for s in sectors]}')
    print()

    results = run_sweep(
        amplitudes=args.amplitudes,
        sectors=sectors,
        tau=args.tau,
        eps=args.eps,
        trials=args.trials,
        seed=args.seed,
        quiet=args.quiet,
    )

    print()
    print_table(results)

    if args.csv:
        write_csv(results, args.csv)


if __name__ == '__main__':
    main()
