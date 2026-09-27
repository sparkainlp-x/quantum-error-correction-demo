# OES-32 toy simulation (quantum-error-correction-demo)

Classical Python toy simulation of OES-32-style metrics. No qubits, no QEC code; every output is SYNTHETIC.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Smoke run](https://github.com/sparkainlp-x/quantum-error-correction-demo/actions/workflows/smoke.yml/badge.svg)](https://github.com/sparkainlp-x/quantum-error-correction-demo/actions/workflows/smoke.yml)
[![Status: research prototype](https://img.shields.io/badge/status-research%20prototype-orange.svg)](#what-it-is-not)
[![Outputs: SYNTHETIC](https://img.shields.io/badge/outputs-SYNTHETIC-lightgrey.svg)](#evidence-tags)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22985530.svg)](https://doi.org/10.5281/zenodo.22985530)

> **METRIC_TAG=SYNTHETIC.** Every number this script prints comes from hand-written formulas on generated inputs.

## What it is

- A single **classical Python script**, [`oes32_v14_improved.py`](oes32_v14_improved.py), that runs a Monte Carlo loop over hand-written formulas relating a simulated erasure probability to "coherence", "success rate", and a few other labelled quantities.
- A teaching/exploration toy for the OES-32 naming used across the Spark AI NLP repositories.

## What it is NOT

- **Not** a quantum computer implementation and **not** a quantum error-correcting code (no qubits, no stabilizers, no surface code, no decoder).
- **Not** a benchmark. Metric names such as "spooky correlation" and "entanglement entropy" are labels for formulas in the script, not quantum measurements.
- **Not** hardware, field, medical, or production software.
- **Not** bit-matched to the normative OES-32 residual (see [Relationship to ADR-001](#relationship-to-adr-001)).

The repository name predates these scope statements and is kept so existing links keep working.

## Quickstart

Requires Python 3.8+. `tqdm` (progress bar) is the only third-party import and is optional.

```bash
git clone https://github.com/sparkainlp-x/quantum-error-correction-demo.git
cd quantum-error-correction-demo
python3 -m pip install -r requirements.txt   # optional (tqdm)
python3 oes32_v14_improved.py --iterations 20000 --erasure 0.15 --seed 42
```

Other options: `--iterations N` (default 1,000,000), `--erasure P` (default 0.20), `--seed S` (reproducible output), `-v` (verbose logging).

### What the script prints

A report with run metadata and SYNTHETIC values for coherence before/after, success rate, "spooky correlation", "entanglement entropy", and collapse rate. The header and footer carry `METRIC_TAG=SYNTHETIC`, and the success-rate line carries its own SYNTHETIC note.

### About the success rate (for example, 94.92%)

**SYNTHETIC.** Recovery success is drawn with probability `max(0.95, 1 − 0.7·p_erasure)`, so the success rate is ≈95% by construction for `p_erasure ≥ ~0.07`. Figures such as 94.92% are sampling outcomes of that hard-coded 0.95 floor, not a measured error-correction rate, and are not comparable with any QEC benchmark.

## Tests

There is no unit-test suite. CI ([`smoke.yml`](.github/workflows/smoke.yml)) runs the script twice with `--seed 42` and checks that:

1. the report header, footer, and success-rate line are tagged SYNTHETIC;
2. the removed "investor" / unconditional "STABLE" wording has not come back;
3. the two seeded runs produce identical output (timestamp excluded).

To reproduce locally, run the Quickstart command twice and compare the outputs.

## Evidence tags

| Item | Tag |
|---|---|
| Every printed metric | **SYNTHETIC** (formula output on generated inputs) |
| Any hardware, qubit, or QEC performance interpretation | Not claimed |

Tag definitions: [sparkainlp-x/.github](https://github.com/sparkainlp-x/.github#evidence-tags).

## Relationship to ADR-001

The normative OES-32 residual definition is [oes32-residual@b77b612](https://github.com/sparkainlp-x/oes32-residual/tree/b77b61254f15778c6ae221843dceac7a8571158e) (ADR-001). This demo is **not** bit-matched to it and is not a Profile A sidecar.

- [`oes32-residual`](https://github.com/sparkainlp-x/oes32-residual): normative residual contract
- [`oes32_engine`](https://github.com/sparkainlp-x/oes32_engine): Profile A sidecar (Python)
- [`oes32-hls`](https://github.com/sparkainlp-x/oes32-hls): Profile A sidecar (C++ HLS prototype; synthesis UNRUN)
- OES-512 (16 × OES-32 blocks, weighted latch) is a **TARGET**; source not published ([`oes512-residual`](https://github.com/sparkainlp-x/oes512-residual))

## Citation

Archived on Zenodo: concept DOI [10.5281/zenodo.22985530](https://doi.org/10.5281/zenodo.22985530) (all versions; resolves to the latest). The v0.1.0 archive is [10.5281/zenodo.22985531](https://doi.org/10.5281/zenodo.22985531); its source tree is git tag [`v0.1.2`](https://github.com/sparkainlp-x/quantum-error-correction-demo/releases/tag/v0.1.2) (the same files, re-tagged on the rewritten history).

Citation metadata is in [CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button). This is a toy script: if you mention it, cite a tagged release (or the repository URL and commit SHA) and describe its outputs as SYNTHETIC.

Author: Jean-François Brisson, Spark AI NLP, <https://sparkainlpx.xyz>. Questions: open an issue in this repository.

## License

[MIT](LICENSE).
