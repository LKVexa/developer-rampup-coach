# Developer Ramp-Up Coach

**0.1.2a1 — experimental partial candidate, JY-S011-P001**

A pure Python library that maps a supplied Python snapshot, orders technical
reading, proposes source-grounded exercises and records cumulative progress.
Every playbook includes four human mentoring touchpoints. It never replaces
human mentoring, team integration or judgment about a person.

## Install and use

Python 3.10 or newer; no third-party runtime dependencies.

~~~sh
python -m pip install .
python -m unittest discover -s tests -t .
~~~

~~~python
from rampup.core import (capture_learner_profile, analyze_codebase, reading_path,
                        generate_exercises, build_playbook, adapt)

profile = capture_learner_profile({
    "name_or_handle": "learner", "goal": "understand the API",
    "skill_level": "intermediate", "constraints": ["4h/day"]
})
codebase = analyze_codebase({
    "pkg/util.py": "def helper(): pass",
    "pkg/api.py": "from . import util\nasync def endpoint(): pass"
})
playbook = build_playbook(profile, codebase,
    reading_path(codebase, profile["goal"]), generate_exercises(codebase, profile))
updated = adapt(playbook, {"reading": ["pkg/util.py"], "exercises": [0]})
~~~

Profiles accept beginner/intermediate/advanced. Constraints are descriptive input
for mentor planning; exercise selection does not enforce a time budget.

## Snapshot and import boundaries

Paths must be relative Python file labels from a consistent import root. Windows
separators normalize to slashes. Absolute/traversing paths and duplicate normalized
paths are rejected. No path is opened, and source code is never executed.

Module identities include packages, so left/util.py and right/util.py remain
distinct. Qualified and relative imports resolve against supplied files. Package
initializers use their containing package name. A top-level __init__.py has the
placeholder identity __root__; include a named package directory for useful
relative-import resolution. Import-root and src-layout choices remain caller duties.

Ambiguous module identities and missing/broken/external dependencies remain
explicit. Imports found in function or conditional bodies are conservative graph
edges, not proof of runtime loading. Dynamic imports and runtime search paths are
not resolved. Public async functions are included.

Reading order uses resolved dependencies first with stable alphabetical ties.
Strongly connected components identify actual cycles; blocked_by_cycle marks
downstream modules separately. Every step carries a source digest, citation and
uncertainty note. Parse errors are retained; a plan over a partial snapshot is
incomplete guidance and needs mentor review.

## Guidance and progress

Exercises refer to actual public symbols with source file, line and digest.
A limit of zero returns no exercises; valid limits are 0..100. Playbook creation
recomputes the reading path and exercise prefix from the profile and codebase,
rejecting substituted guidance.

Profiles, codebase maps and playbooks use canonical content digests. Changes
invalidate downstream artifacts; regenerate rather than mixing snapshots.
Digests do not authenticate content or protect against a caller rewriting both
an artifact and its hash.

adapt accepts known reading paths and zero-based exercise indices. Progress is
cumulative, repeated events are idempotent, and prior completion is never reset.
New completion deltas append to progress_history with a sequence and previous
playbook digest. This is caller-reported progress, not assessment or proof of work.
Pace adjustments and closing sessions remain human mentor decisions.

## Input limits and compatibility

At most 1,000 source files, 1 MiB UTF-8 per file, 16 MiB combined source/model data,
and 10,000 resolved dependency edges. Profile labels are bounded to 512 characters,
goals to 4,096, constraints to 100 strings, and paths to 1,024 characters.
Invalid API input raises ValueError; malformed Python is an explicit parse error.

Version 0.1.1-partial -> 0.1.2a1 changes module identity, canonical digests,
citations and progress semantics. Regenerate profiles, maps and playbooks with
the public constructors. Artifact schema remains v1 with additive fields.

53 tests include 16 inherited checks and 37 regressions. Source and installed-wheel
results are in [CHECK_RUNS](docs/CHECK_RUNS.json); see [AUDIT](docs/AUDIT.md) and
[SECURITY](SECURITY.md). CI covers Linux Python 3.10/3.12/3.14 and Windows Python 3.12.

Multi-language analysis, model guidance, service architecture, platform decisions,
phase gates and the original 233-unit roadmap remain outside this candidate.
No production readiness, performance review or personnel decision is provided.

## License

Copyright 2026 **RUSSELL PHILIP SMITHSON**.
[Apache License 2.0](LICENSE), with [NOTICE](NOTICE).
No third-party code is vendored.
