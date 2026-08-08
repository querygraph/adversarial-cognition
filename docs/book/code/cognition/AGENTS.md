# Repository Guidance

- The benchmark core (`adversarial_cognition/`) is dependency-free Python;
  keep it that way. OSS system adapters under `adapters/` own their isolated
  environments and never leak dependencies into the core.
- Safety gates are zero-tolerance and never averaged into quality. Reports
  carry bounded IDs, digests, counts, and timings — never memory plaintext.
- The corpus is versioned by content digest in
  `fixtures/marciana-adversarial-v1/manifest.json`; any case change must
  repin via `run_benchmark.py --pin-corpus` in the same commit.
- Adapters never fake capability: a system executes only when explicitly
  configured, a failing adapter reports `error`, and genuinely unclaimed
  capabilities are declared `"supported": false` rather than scored.
- Keep files small and single-purpose, tests in separate files under
  `tests/`, and one authoritative implementation per digest, validation, or
  scoring rule.
- Maintain `CHANGELOG.md` in the same change that introduces an outcome.
