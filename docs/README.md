# Kitaphana documentation

Small project, one developer. These documents exist so that a session which starts with no
memory of the last one can pick the work back up in a few minutes.

## Which file answers which question

| Question | File |
|---|---|
| Where am I, what is next? | [`03-roadmap.md`](03-roadmap.md) — **open this first** |
| Why does Kitaphana exist, and what will it never be? | [`00-vision.md`](00-vision.md) |
| What does this word mean? | [`01-glossary.md`](01-glossary.md) |
| What is the shape of the whole project? | [`02-phases.md`](02-phases.md) |
| What do I not know yet, and what could go wrong? | [`04-risks-and-research.md`](04-risks-and-research.md) |
| Why was this built this way? | [`adr/`](adr/) |
| What exactly am I building this week? | [`sprints/`](sprints/) |

[`99-origin-prompt.md`](99-origin-prompt.md) is the Turkish planning note these documents were
generated from. It is kept for provenance and is not maintained.

## Conventions

- **Status marks:** ⚪ Pending · 🟡 In progress · 🟢 Shipped · 🔴 Blocked
- **ADRs** are numbered `NNNN-kebab-title.md`, never renumbered, and immutable once accepted —
  a decision that changes gets a *new* ADR that supersedes the old one.
- **Sprints** are numbered `sprint-NN-name.md` and sized to roughly one week at 5-10 hours.
  Every sprint document ends with a **No-gos** list; that list is what keeps a sprint to a week.
- Documents in `docs/` are written in English. Text shown to users is in Turkmen, and appears
  in these documents only as quoted UI copy.

## Writing sprint documents for later phases

Only Phase 1 sprints are written out in full. Phases 2-4 have goals and exit criteria in
[`02-phases.md`](02-phases.md); their sprint documents get written when that phase is reached,
so they can be informed by what Phase 1 actually taught. Copy the structure of an existing
sprint document rather than inventing a new one.
