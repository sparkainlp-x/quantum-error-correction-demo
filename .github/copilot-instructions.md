# GitHub Copilot instructions — Spark AI NLP holographic membrane stack

These instructions apply to this repository and to sibling Spark repos when this file is present:
`quantum-error-correction-demo`, `oes32-residual`, `qldpc_decoder_cpp`, `Cosmos-Holographic-Membrane-Simulation`.

You are writing production-grade code and docs for Spark AI NLP (sparkainlp-x). Follow this file over generic QEC tutorials.

## Mission

Build a **fail-closed** link between:

1. OES-32 holographic QECC simulation (membrane flip, coherence / spooky / entropy)
2. `oes32-residual` 32-vector residual contract
3. `qldpc_decoder_cpp` host + RFSoC ZCU111 syndrome decoder

The holographic **membrane** is a 32-slot two-faced register `(U bulk, B boundary)`. It is an interface, not spacetime.

## Hard rules — never violate

- Width is **32**. Reject any other length with a hard error.
- All floats must be finite. Reject NaN and Inf.
- Fail **closed**. Unauthorized, malformed, or residual-breaching acts raise an error. Do not “best effort” write the live membrane.
- Do not claim this implements AdS/CFT, HaPPY, FLM experimental confirmation, Denis HTC, quantum gravity on FPGA, or a medical/HoloHeal treatment device.
- Adjacent papers (HaPPY/Biswas 2026, Denis HCU, Ryu–Takayanagi, FLM) are **citations only**, not outputs of this code.
- Do not weaken the shield to make a demo pass.
- Do not log capability secrets, HMAC keys, or raw master keys.
- Observateur must never receive a live alias to `U` or `B`. Copies only.
- Observateur must never call the flip operator F.
- A single calibration agent must never both propose and commit a reference.
- Flip is admitted only if `syndrome_ok` (`H c == s`) **and** aggregate residual `max_i |obs_i - ref_i| ≤ τ`.
- Residual breach **latches** collapse. Further flips are denied until gardien reset to the last sealed reference.
- Do not pass `syndrome_ok=True` as a constant in production paths. Compute `H c == s`.
- HIL FER stub in `qldpc_decoder_cpp` must be replaced with real `H * correction == syndrome`, never silently left as success.
- Latency gates stay: software GF(2) SpMV median < 1000 ns in CI; HIL AXI-DMA < 100 µs. Do not raise those ceilings without an explicit comment and a new measured baseline.
- Bilingual FR/EN docs are welcome. Keep identifiers in English (`bulk`, `boundary`, `tau`, `syndrome_ok`) unless the existing file is already French.

## Roles (do not invent new ones without updating docs)

| Role | May | Must not |
|---|---|---|
| `observateur` | read copy of `B` | read `U`, write, flip, calibrate, commit |
| `calibrateur` | propose `(U*, B*, τ)` into quarantine | countersign own proposal, write live membrane, flip |
| `decodeur` | request flip of `B` then paired `U` | commit calibration, reset latch, read as if gardien |
| `gardien` | issue/revoke caps, commit sealed calibration, latch, reset | skip dual-control on calibration |

Capabilities are HMAC-bound tokens with TTL. Revoked or forged tokens die.

## Membrane flip F

F updates `(U, B)` in **one** step. Boundary correction and bulk update are a paired write. Do not implement “decode B, then maybe update U later.”

## Decoder ABI to preserve

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

If a request conflicts with these rules, refuse and explain briefly.
