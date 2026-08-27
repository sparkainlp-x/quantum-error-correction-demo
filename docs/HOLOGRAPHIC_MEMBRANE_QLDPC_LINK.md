# Holographic Membrane ↔ QLDPC Link

This document defines the software contract linking OES-32 membrane state handling,
`oes32-residual` 32-lane residual checks, and the `qldpc_decoder_cpp` decode path.

## Contract Boundaries
- Membrane is a 32-slot interface with paired `(U, B)` updates.
- Decoder admission is fail-closed and depends on computed syndrome validity (`Hc == s`) plus residual gate (`max_i |obs_i-ref_i| <= tau`).
- Residual breach latches collapse until gardien reset to the last sealed reference.

## ABI Preservation
```cpp
struct MembraneFrame { float bulk[32]; float boundary[32]; };
struct DecodeReport {
    bool syndrome_ok;
    bool logical_ok;
    uint32_t iterations;
    uint64_t latency_ns;
    float residual;
};
DecodeReport membrane_decode(
    const MembraneFrame& observed,
    const MembraneFrame& reference,
    float tau
);
```

## Citation Note
Related literature may be cited for context (e.g., HaPPY/Biswas 2026 and Denis HTC notes),
but this code does not claim gravity, AdS/CFT, or experimental FLM confirmation outputs.
