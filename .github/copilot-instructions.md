# OES-32 — Repository-wide Copilot Instructions

## Scientific framing

OES-32 is a **classical wave simulator** with a quantum-inspired probability mapping.

- The system models interference from two wave sources on a circular membrane.
- Surface amplitude is squared to produce a normalized intensity distribution
  analogous to a classical energy density.
- **Never claim** quantum entanglement, consciousness effects, or healing properties.
- **Never claim** this is a quantum system. It is a classical wave model.
- Acceptable framing: "quantum-inspired normalization", "intensity-like distribution",
  "classical wave interference".

## Project structure

```
src/oes32/       — simulation and animation logic (Python packages)
tests/           — pytest tests for all modules
membrane_shield/ — OES-32 Membrane Shield access-control module (stdlib only)
```

## Coding standards

- Python 3.12+. Use `from __future__ import annotations` in all source files.
- Type-annotate all public functions and methods.
- Use NumPy for all numerical operations. Do not use plain Python loops over arrays.
- Use Matplotlib for visualization. Default to the `Agg` backend for non-interactive use.
- Use pytest for all tests.
- Keep noise **temporally smooth** for animation: use AR(1) or similar correlated
  processes. Do not generate independent random noise every frame.
- Separate simulation logic, animation logic, and tests into different files.
- Validate `N > 1` and handle near-zero total intensity safely (uniform fallback).
- Do not use external packages beyond: `numpy`, `matplotlib`, `pytest`, `tqdm`.

## Error handling

- Raise `ValueError` with a descriptive message for invalid parameters.
- Never silently swallow exceptions.
- Near-zero intensity must return a uniform distribution, never NaN or Inf.

## Style

- PEP 8. Line length ≤ 100 characters.
- NumPy docstring style for all public functions.
- No magic numbers: assign named constants or document inline.
