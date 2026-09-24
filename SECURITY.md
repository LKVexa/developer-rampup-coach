# Security and human mentoring boundaries

This library analyzes supplied strings and returns advisory technical plans.
It performs no source execution, filesystem writes, messaging or people-management
decisions. Every generated playbook retains human mentoring touchpoints.

Learner profiles, docstring summaries, file labels and symbol names can contain
sensitive information. No redaction is performed. Minimize input and review output
before sharing. Do not interpret progress as an assessment of an individual's
ability, job performance or eligibility.

Static import resolution is incomplete. Package roots, dynamic imports, runtime
module paths and conditional imports require mentor verification. Ambiguous or
missing dependencies are explicit, but a reading plan is not a runtime dependency
guarantee. Constraints are recorded rather than automatically enforced.

Content digests bind snapshots and guidance; they are not authentication,
signatures or tamper-proof storage. Progress is caller-reported. History is
preserved during API updates, but a caller can construct a new artifact and hash.
Persist and authorize records independently in any deployed integration.

Size/count limits protect ordinary API use, not hostile in-process Python code,
concurrent mutation or every parser resource attack. Exposed services need request
limits and OS isolation. No third-party runtime dependencies exist; no build-tool
vulnerability scan is claimed. Report defects privately with synthetic examples.
