# Holographic Membrane ↔ QLDPC Link

This note links the membrane policy layer to the decoder control path.

## Scope
- Enforce a 32-bit lane width on protected syndrome/coherence vectors.
- Require finite floating-point residual values.
- Gate decoder flip requests behind explicit parity-check evaluation (`H * c == s`) and thresholding (`residual <= tau`).

## Operational Guardrails
- Fail closed on malformed inputs or policy violations.
- Latch collapse on residual-threshold breach.
- Permit collapse reset only through the `gardien` role, restoring to a sealed reference.
- Keep observability constrained: observateur accesses only a copy of `B`.

## Verification Expectations
- Every new privilege path must include a deny-path unit test.
- Privilege checks must be explicit and local to the guarded operation.
