---
applyTo: "tests/**/*.py"
---

# Python test instructions

## General rules

- Write pytest tests only.
- Import the function under test from its package path.
- Use Arrange / Act / Assert structure.
- Prefer deterministic tests.
- Keep each test focused on one behavior.
- Use `np.isclose` or `np.allclose` for floating-point comparisons.
- Avoid testing implementation details unless necessary for correctness.

## OES-32 test coverage

For the OES-32 wave function, write tests that verify:
- The output surface array has length N.
- The probabilities array has length N.
- Surface and probability values are finite.
- Probability values are nonnegative.
- Probabilities sum to 1 within a small tolerance.
- A near-zero intensity case returns a uniform distribution.
- Changing `f_left` or `f_right` changes the output field.
- Invalid N values raise `ValueError`.

## Numerical testing guidelines

- Use a fixed seed when randomness is involved.
- Prefer deterministic inputs whenever possible.
- Use `np.allclose` for uniform distributions and near-zero cases.
- Use `np.isclose` for probability normalization checks.
- Check both shape and content when the output is array-based.
- If a test depends on exact input values, make those values explicit in the test body.

## Error handling

- Test invalid input early.
- Confirm that bad shapes, invalid N, or impossible parameter values raise clear exceptions.
- Do not suppress exceptions in tests.
- Prefer explicit `with pytest.raises(...)` blocks.

## Readability

- Keep test names descriptive and specific.
- Avoid large fixtures unless they reduce duplication.
- Do not add extra helper logic unless it improves clarity.
- Keep the file small and easy to scan.

## OES-32-specific style

- Treat the function as a classical wave model with a quantum-inspired normalization.
- Do not test for quantum behavior.
- Do not assume physical claims beyond normalization and interference behavior.
