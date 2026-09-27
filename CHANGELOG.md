# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- `.zenodo.json` adds the `spark-ai-nlp` Zenodo community.
- The archived v0.1.0 source tree (DOI 10.5281/zenodo.22985531) is now git tag `v0.1.2` on the rewritten history (same files); the old `v0.1.0` tag was removed.
- Docstring labels in `oes32_v14_improved.py` no longer call the formula outputs quantum quantities ("Entanglement fidelity metric" → heuristic formula output, SYNTHETIC).
- CI actions bumped to `actions/checkout@v7` and `actions/setup-python@v7` (Node 24).

## [0.1.0] - 2026-09-26

### Added
- Seeded smoke-run CI (seed 42, SYNTHETIC), `--seed` option, README skeleton, `CITATION.cff` (DOI 10.5281/zenodo.22985531; concept DOI 10.5281/zenodo.22985530).

### Changed
- All outputs tagged SYNTHETIC; investor framing removed; conditional status line; `requirements.txt` added.
