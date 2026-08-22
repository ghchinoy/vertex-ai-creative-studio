# Extending the System

> **Purpose:** practical guidance for scoping and dispatching new work — a new recurring job or a
> one-off review — sized to the work in front of you.

The system described in these documents isn't a fixed list of jobs; it's a way of working. When
new work appears, the question is always the same: **how much process does this change actually
need?** Too little process on a risky change lets breakage through; too much process on a trivial
change wastes everyone's time. This document is about getting that match right.

## The principle: size the process to the work

> **Match the amount of process to the size and risk of the change.**

Two rough tiers cover most cases:

| The work is… | Give it… |
|---|---|
| **Small and well-bounded** — a focused fix, a mechanical cleanup, a clearly-scoped bump. | **A developer plus an independent reviewer**, dispatched directly. No extra structure. |
| **Larger or cross-cutting** — touches many areas, needs investigation and design, or carries real risk. | **A dedicated owner** who runs the full lifecycle: investigate → design → implement → review, coordinating sub-tracks as needed. |

The tiers aren't rigid categories to litigate — they're a prompt to ask "is this a quick, safe
change, or something that needs its own plan?" and to resource it accordingly.

### Small, well-bounded work

Most day-to-day work lands here: a bug fix, a dependency bump, a branch cleanup, a doc update. It
gets a developer to do the work and — following [review discipline](./review-discipline.md) — a
**separate** person to review it. That's the whole process. The branch-hygiene cleanup and the
individual PR reviews described elsewhere in this set are examples of small, well-bounded work.

Even small work keeps the two non-negotiables from the rest of this system:

- The author never reviews their own change (see [review-discipline.md](./review-discipline.md)).
- Dependency changes are verified empirically before merge (see
  [verification-principle.md](./verification-principle.md)).

### Larger, cross-cutting work

When a change is too big for one developer-plus-reviewer pass — it spans multiple components, needs
research before anything can be designed, or carries enough risk to warrant a plan — it gets a
**dedicated owner**. That owner doesn't just write code; they run the whole arc:

1. **Investigate** — understand the current state and the real requirements.
2. **Design** — decide the approach before building.
3. **Implement** — do the work, often split across parallel sub-tracks.
4. **Review** — with the same author-≠-reviewer independence, applied to each piece.

The dedicated owner keeps the tracks coordinated and reports progress and decisions up to the human
owner — surfacing open questions rather than guessing on them.

## A real illustration: the `credentio` adoption workstream

A concrete example of large, cross-cutting work sized this way was the **`credentio-adoption`**
workstream. (Source: `c2pa-credentio/`. The detail below is intentionally high-level — it's an
example of *sizing*, not a guide to the underlying technical content.)

The question being investigated was whether the project could adopt a new content-provenance
validation library. That's exactly the kind of work that does *not* fit a single quick fix:

- It required **investigation first** — surveying where the current library was used across the main
  product and its experiments before any decision could be made.
- It was **cross-cutting** — spanning multiple parts of the codebase.
- It carried **real open questions** for the human owner (motivation, future direction, tolerance
  for an early-stage dependency) rather than an obvious answer.

So it was run as a **dedicated-owner effort split into parallel tracks** — a Primary track plus
Secondary, Tertiary, and Signing tracks — each investigating its piece and reporting findings up,
rather than one person trying to do it all in a single pass. The output was a grounded findings
report and a clear set of decisions for the owner, not a rushed merge.

The point isn't the specifics of that workstream. The point is the **shape**: a large,
uncertain, multi-part effort got a dedicated owner and parallel tracks, whereas a one-line
dependency bump gets a developer and a reviewer. Same values, different amount of process.

## How to apply this

When new work shows up, ask, in order:

1. **Is it small and well-bounded?** → developer + independent reviewer, dispatch it directly.
2. **Is it larger, cross-cutting, or risky?** → give it a dedicated owner who runs
   investigate → design → implement → review.
3. **Either way**, keep the invariants: author ≠ reviewer, and verify dependency changes
   empirically before merge.
4. **When unsure which tier it is**, treat it as the larger one until investigation proves it's
   small. Under-scoping a risky change is the more expensive mistake.

---

*A note on terminology: this project happens to implement the "dedicated owner" and "developer +
reviewer" roles using an agent-orchestration system, but nothing here depends on that. Read it as a
general delegation principle — **match the amount of process to the size and risk of the change** —
and the specific tooling is just one way to carry it out.*
