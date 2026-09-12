# OES-32 simulation demo

## What this repository is / is not
- This repository contains a **classical Python simulation script**: `oes32_v14_improved.py`.
- It is **not** a quantum computer implementation and **not** a standard QECC implementation (no qubits, no stabilizers, no surface code).
- It emits internal simulation metrics on a synthetic loop; these outputs are not claims of peer-reviewed physics.
- It is a demo-level codebase focused on reproducible script execution and metric reporting.
- OES-32 here is an identifier for a 32-component real-vector contract with residual/latch/symmetry/FOLD8 structure.

## Relation to `oes32-residual`, `oes32_engine`, `oes32-hls`
This demo script aligns conceptually with the public OES-32 specifications:
- `oes32-residual`: https://github.com/sparkainlp-x/oes32-residual
- `oes32_engine`: https://github.com/sparkainlp-x/oes32_engine
- `oes32-hls`: https://github.com/sparkainlp-x/oes32-hls

OES-512 is closed source: 512 = 16 × OES-32 blocks; source not published (`oes512-residual`).

## How to run
### Requirements
- Python 3.8+
- `tqdm` (optional, progress bar)
- JAX (optional, acceleration)

### Commands
```bash
git clone https://github.com/sparkainlp-x/quantum-error-correction-demo.git
cd quantum-error-correction-demo
pip install -r requirements.txt  # optional deps

python oes32_v14_improved.py --iterations 1000000 --erasure 0.20
python oes32_v14_improved.py --iterations 100000000 --erasure 0.15 -v
```

## What the script prints
The script prints run metadata and metrics such as iterations, erasure probability, coherence before/after, success rate, spooky correlation, entanglement entropy, and collapse rate.

If values such as `94.92%` appear, treat them as **metrics emitted by this simulation on its own synthetic loop**. They are **not** presented as a comparison against a standard QEC benchmark.

## License
This repository is released under the **MIT License**. See [LICENSE](LICENSE).

## Author
Jean-François Brisson / Spark AI NLP / https://sparkainlpx.xyz

## Contact
GitHub organization: `sparkainlp-x`
