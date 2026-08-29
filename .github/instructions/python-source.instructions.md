---
applyTo: "src/**/*.py"
---

# Python source instructions

## Module structure

- Keep simulation physics in `src/oes32/waves.py`.
- Keep animation and rendering in `src/oes32/animation.py`.
- Keep the package entry point in `src/oes32/__init__.py`.
- Do not mix simulation logic and animation logic in the same file.

## Simulation functions

- All simulation functions must be pure (no side effects, no I/O).
- Parameters must have explicit types and defaults.
- Validate `N` as `isinstance(N, int) and N > 1`; raise `ValueError` otherwise.
- Handle near-zero total intensity by returning a uniform distribution `np.ones(N) / N`.
- Accept `noise_values` as an optional pre-computed array so callers control
  temporal correlation; never generate random noise inside the physics function.

## NumPy usage

- Use vectorized operations over whole arrays. Avoid Python-level loops on arrays.
- Use `np.sum`, `np.sin`, `np.arange`, `np.pi` — not math module equivalents.
- Use `np.ndarray | None` for optional array parameters.

## Animation

- Use `matplotlib.animation.FuncAnimation`.
- Generate noise with an AR(1) process (`AR1NoiseGenerator` pattern) so frames
  are temporally correlated and the animation is smooth.
- Default backend: `matplotlib.use("Agg")` (non-interactive). Document how to
  switch to `TkAgg` for interactive display.
- Update existing artists in `_update`; do not recreate figure elements per frame.
- Return updated artists from `_update` for `blit=True` compatibility.

## Docstrings

- Use NumPy docstring style: Parameters / Returns / Raises sections.
- Document units where applicable (Hz for frequencies, seconds for time).
- State clearly that this is a classical wave model in module-level docstrings.

## Scientific accuracy

- Do not add language suggesting quantum behavior, healing, or consciousness.
- Squaring amplitude gives classical intensity — document it as such.
