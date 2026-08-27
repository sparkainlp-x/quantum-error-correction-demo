# Copilot Instructions

Follow these rules strictly for all suggestions, edits, and generated code:

1. **Fail closed** by default.
2. **Width 32** for protected bit-vectors and syndrome paths.
3. **Finite floats only** (`NaN`/`Inf` forbidden on live paths).
4. **observateur** may read a copy of `B` only — never `U`, never `F`.
5. **calibrateur** may perform quarantine actions only; a different agent must countersign; only **gardien** may commit.
6. **decodeur** may request `request_flip` only if `H * c == s` (computed, never hardcoded `True`) and `residual <= tau`.
7. Residual breach latches collapse; only **gardien** may reset to last sealed reference.
8. Refuse claims or additions about AdS/CFT, HaPPY, FLM-confirmation, HTC, gravity-on-FPGA, or medical claims.
9. Never log capability secrets.
10. Add deny-path tests for every new privilege path.

If a request conflicts with these rules, refuse and explain briefly.
