# Audit and hardening — 0.1.2a1

Date: 2026-09-23. Source: JY-S011-P001 / 0.1.1-partial / run-0001 / product.
Reviewed all profile, graph, exercise, playbook and adaptation code. Original
source remains separate from this checkout.

## Repaired findings

- Profile fields were loosely typed and constraints could become a list of
  characters; repr-based digests were unstable across equivalent JSON orderings.
  Bounded labels/list validation and canonical content digests replace this.
- Filename-only module identities collided across packages. Relative and qualified
  imports were lost or misresolved. Package-aware identities and explicit
  unresolved/ambiguous imports now preserve scope.
- Public async functions were omitted. They now carry symbol line provenance.
- Kahn-sort leftovers were all called cyclic. Strongly connected components now
  distinguish cycle members from dependents blocked by a cycle.
- Exercise limit zero returned every eligible exercise and invalid limits were
  accepted. Limits now validate and zero produces no exercises.
- Guidance lacked source content/line binding and playbooks accepted arbitrary
  reading/exercise input. Citations now bind source snapshots and guidance is
  recomputed before playbook construction.
- Exported mentoring rules were mutable. Immutable templates plus detached
  playbook data preserve mandatory touchpoints across ordinary API use.
- Reading updates reset prior completion, unknown paths/indices were silently
  ignored and no history existed. Cumulative validated updates now append only
  new completion deltas, remain idempotent and preserve prior history.
- Profile, graph and playbook mutation can no longer pass unnoticed to downstream
  APIs; canonical digest validation rejects mismatches. Input sizes are bounded.

## Verification and release

16 inherited tests passed before changes. 53 source and installed-wheel tests
pass after repairs, including 37 new regressions. Historical check evidence
remains separate. CI covers Linux Python 3.10/3.12/3.14 and Windows Python 3.12.

Version 0.1.1-partial -> 0.1.2a1. Regenerate profiles, maps and playbooks; module
identities and digests change. Added packaging, pinned-action CI, README, security
docs and Apache 2.0 LICENSE/NOTICE naming RUSSELL PHILIP SMITHSON.

There are no third-party runtime dependencies to upgrade or scan. No build-tool
vulnerability scan is claimed. Import analysis remains heuristic and progress
caller-reported. Human mentoring and the original roadmap remain authoritative;
this release is not a production-readiness or people-management decision.
