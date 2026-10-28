# Architecture Decision Records

Short, permanent records of decisions that are expensive to reverse or that many files
depend on. One file per decision: `NNNN-short-title.md` (zero-padded, never renumbered).

**Statuses:** `Proposed` (written, awaiting review) -> `Accepted` (implement it verbatim)
-> optionally `Superseded by NNNN`. An accepted ADR is not edited to change the decision;
write a new ADR that supersedes it. Typo/clarification fixes are fine.

**Sections used:** Context, Decision, Invariants, Alternatives considered, Consequences,
Open questions, and — for decisions that drive a migration — an explicit checklist of
everything affected, so the implementing task does not rediscover scope mid-flight.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-currency-storage.md) | Currency storage: whole-Toman amounts held as integer Rial | Accepted |
