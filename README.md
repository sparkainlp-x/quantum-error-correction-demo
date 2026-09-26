# OES-32 toy simulation (classical Python, SYNTHETIC outputs)

> **METRIC_TAG=SYNTHETIC.** Every number this script prints comes from hand-written formulas on generated inputs. It is a research prototype, not a quantum computer implementation, not a quantum error-correcting code, and not a hardware, field, or medical product.

## What this repository is / is not
- This repository contains a **classical Python simulation script**: `oes32_v14_improved.py`.
- It is **not** a quantum computer implementation and **not** a standard QECC implementation (no qubits, no stabilizers, no surface code).
- Metric names such as "spooky correlation" and "entanglement entropy" are labels for formulas in the script. They are not quantum measurements.
- OES-32 here is an identifier for a 32-component real-vector contract with residual/latch/symmetry/FOLD8 structure. The normative residual definition is [oes32-residual@b77b612](https://github.com/sparkainlp-x/oes32-residual/tree/b77b61254f15778c6ae221843dceac7a8571158e) (ADR-001); this demo is not bit-matched to it.

## Relation to `oes32-residual`, `oes32_engine`, `oes32-hls`
- `oes32-residual` (normative residual contract): https://github.com/sparkainlp-x/oes32-residual
- `oes32_engine` (Profile A sidecar, Python): https://github.com/sparkainlp-x/oes32_engine
- `oes32-hls` (Profile A sidecar, C++ HLS prototype; synthesis UNRUN): https://github.com/sparkainlp-x/oes32-hls

OES-512 (512 = 16 × OES-32 blocks) is a **TARGET**; its source is not published (`oes512-residual`).

## How to run
### Requirements
- Python 3.8+
- `tqdm` (optional; progress bar). It is the only third-party import. The script runs without it.

### Commands
```bash
git clone https://github.com/sparkainlp-x/quantum-error-correction-demo.git
cd quantum-error-correction-demo
pip install -r requirements.txt  # optional (tqdm)

python oes32_v14_improved.py                              # 1,000,000 iterations (default)
python oes32_v14_improved.py --iterations 100000 --erasure 0.15 -v
```

## What the script prints
Run metadata plus these SYNTHETIC metrics: coherence before/after, success rate, "spooky correlation", "entanglement entropy", and collapse rate. Each line is tagged SYNTHETIC.

### About the success rate (for example, 94.92%)
**SYNTHETIC.** Recovery success is drawn with probability `max(0.95, 1 − 0.7·p_erasure)`, so the success rate is ≈95% by construction for `p_erasure ≥ ~0.07`. Figures such as 94.92% are sampling outcomes of that hard-coded 0.95 floor, not a measured error-correction rate, and are not comparable with any QEC benchmark.

## License
This repository is released under the **MIT License**. See [LICENSE](LICENSE).

## Author
Jean-François Brisson, Spark AI NLP, https://sparkainlpx.xyz

## Contact
Open an issue in this repository.
