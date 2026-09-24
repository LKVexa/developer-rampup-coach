# 0.1.2a1 — 2026-09-23

- Validate canonical profiles and resolve package-aware static import graphs.
- Include async symbols; separate actual cycles from blocked dependents.
- Bind exercise citations and playbook guidance to source snapshots.
- Record cumulative, idempotent progress with validated completion history.
- Add 37 regressions, packaging, Apache 2.0 LICENSE/NOTICE, README and CI.
- Compatibility: regenerate profiles, codebase maps and playbooks.

# Changelog — Contextualized Developer Ramp-Up Coach (JY-S011-P001)

## 0.1.1-partial — 2026-09-14 (maintenance/hardening, factory v3.0.0 audit A012)

Baseline fingerprint: build-0001 product.zip
sha256 b401ed1b303ce1768a1029d3b5755f2e15112f4a8ccb3963787c8ff84a806e07 (7850 bytes),
version 0.1.0-partial. All 13 baseline tests passed before patching; every
finding below was reproduced live on the unmodified baseline.

### Fixed
- **A012-F1 (high)** — GRD-01 guardrail escape via aliasing. `build_playbook`
  embedded the module-level `MENTOR_TOUCHPOINTS` list by reference; observed:
  a consumer clearing one playbook's `human_mentoring_touchpoints` emptied the
  module constant, so every subsequent playbook was produced with 0 mentoring
  touchpoints. Expected: the mandatory touchpoints cannot be removed from
  future playbooks by mutating a returned one. Fixed by deep-copying on embed.
- **A012-F2 (medium)** — shared mutable state across returned objects.
  `build_playbook` embedded `codebase["modules"]`, `parse_errors`, profile,
  reading path and exercises by reference, and `adapt` returned a shallow copy;
  observed: mutating a playbook's `codebase_map` mutated the analyzer output,
  and mutating an adapted playbook's `learner` mutated the original playbook.
  Expected: returned structures are isolated. Fixed with `copy.deepcopy` in
  `build_playbook` and `adapt`.
- **A012-F3 (medium)** — error-contract leaks. Observed on baseline:
  `reading_path(cb, None)` -> AttributeError; `generate_exercises` with an
  invalid skill level -> KeyError; `analyze_codebase({"a.py": 42})` ->
  TypeError; `adapt(pb, None)` -> AttributeError; `adapt(pb, {"exercises": 5})`
  -> TypeError; `capture_learner_profile(42)` -> TypeError. Expected: the
  documented ValueError with a descriptive message. Fixed with explicit input
  validation (including rejecting bool as an exercise index).

### Compatibility
- No public API removed or renamed; all valid inputs behave as before
  (13/13 baseline tests still pass unmodified). Only previously-crashing
  invalid inputs now raise ValueError, and returned playbooks no longer share
  mutable state with inputs (callers relying on aliasing side effects would
  need adjustment — none exist in the shipped code/tests).
- Rollback: restore build-0001 product.zip (fingerprint above).

## 0.1.0-partial — build-0001
Initial partial candidate (PAPER-CAP-01..05 slices).
