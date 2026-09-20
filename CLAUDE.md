# Working on Kitaphana

## Start every session here

Read [`docs/03-roadmap.md`](docs/03-roadmap.md) first. It is the memory between sessions:
it names the current sprint, what shipped already, and what comes next. Then open the
sprint document it links to and work through that sprint's task list.

## Ground rules

- **The ADRs are settled.** [`docs/adr/`](docs/adr/) records decisions that were argued
  through once and should not be relitigated mid-sprint. If one genuinely needs to change,
  write a new ADR that supersedes the old one rather than editing the old one in place.
- **Respect the sprint's No-gos.** Every sprint document ends with a list of things that are
  explicitly out of scope. They are there to stop a one-week sprint turning into three.
- **Research is not development.** Open questions live in
  [`docs/04-risks-and-research.md`](docs/04-risks-and-research.md), not hidden inside task
  lists. If a task turns out to be blocked on an unknown, move it there.
- **Update the roadmap at the end of a sprint**, not the beginning: flip the status, add a
  line to the shipped log, and move the current-sprint block to the next sprint.

## Constraints worth remembering

The server has 2 vCPU and 2 GB RAM, and the developer has 5-10 hours a week. Both of these
rule out a lot of otherwise reasonable choices. Prefer the boring option that runs in
little memory and can be understood again after a two-week gap.

Large PDFs are served by nginx via `X-Accel-Redirect`, never streamed through the Python
process — see [ADR-0014](docs/adr/0014-x-accel-redirect-for-downloads.md).
