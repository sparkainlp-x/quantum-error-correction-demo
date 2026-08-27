# Membrane Shield Policy

The membrane shield is a policy enforcement boundary for privileged decoder actions.

## Core Constraints
- Default deny (fail closed).
- Width 32 for protected bit-vectors.
- Finite floats only.
- observateur reads only a copy of `B`.
- calibrateur is quarantine-only, with distinct countersigner requirement.
- Only gardien can finalize commit-class actions.
- `request_flip` requires computed `H * c == s` and `residual <= tau`.
- Residual breach latches collapse until gardien reset to sealed reference.

## Safety Rules
- No capability-secret logging.
- Add deny-path tests for each privilege-bearing operation.
