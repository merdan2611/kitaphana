# ADR-0002: Store PDFs on the server's local disk

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The library's payload is PDF files — eventually around 30 GB, individually between a few
megabytes and a hundred. They must be stored somewhere and served to readers in Turkmenistan.
The obvious industry answer is object storage with a CDN in front. The obvious industry answer
assumes things that are not true here: a foreign payment card to pay the bill, traffic priced
in a foreign currency, and network paths in and out of the country that are fast and dependable.

The VDS has 120 GB of SSD, which is enough for the known collection with room left over.

## Decision

PDFs live on the VDS's local disk, under a directory outside the git repository. Files are
named by their SHA-256 content hash, not by title, and the original filename is metadata in the
database. No external storage service, no CDN.

## Consequences

### Positive

- No external dependency, no foreign billing relationship, and no third party who can take the
  collection offline.
- Serving from inside the country is the shortest network path to the readers who matter.
- Content-hash naming gives de-duplication for free: the same scan uploaded twice is detected
  before it is stored twice, which matters for the Phase 3 import of a collection assembled
  over years.
- Hash names are unguessable, so nobody enumerates the library by walking URLs.

### Negative / accepted costs

- **120 GB is a hard ceiling**, and the only remedy is a bigger plan. Disk headroom has to be
  watched rather than assumed — R6 in [`../04-risks-and-research.md`](../04-risks-and-research.md).
- The files are on one disk in one building. They are not backed up to anywhere else; that is a
  deliberate and separate decision, [ADR-0011](0011-backup-policy.md).
- All download bandwidth is the VDS's bandwidth. If the library becomes popular, this is the
  first thing that hurts.
- Hash filenames are meaningless to a human. Recovering a readable name means the database,
  so a database loss makes the files anonymous — another reason ADR-0011 is about the database.

## Alternatives considered

- **Object storage plus a CDN** (S3, Backblaze, Cloudflare R2). Solves bandwidth and durability,
  and introduces a foreign card payment, a monthly bill in dollars, and an outside party
  between the library and its readers. Rejected as a dependency the project should not have.
- **A second VDS as a file server.** Doubles the cost to solve a problem the project does not
  yet have.
- **Storing files in SQLite as blobs.** Tempting for the single-file backup story, and wrong: it
  would put 30 GB through the Python process on every download and make the database
  unmanageable.
