# ADR-0012: Register the domain with a foreign registrar

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The site needs a domain name pointing at the VDS. A `.tm` domain would be the natural choice for
a Turkmen library, but registering one is expensive and administratively involved compared with
a generic top-level domain from an international registrar, where a domain costs a few dollars a
year and is configured in a web panel in minutes.

The server itself is inside Turkmenistan and stays there ([ADR-0015](0015-turkmentelecom-vds-hosting.md)).
Only the name is registered abroad.

## Decision

Register a generic domain (`.com`, `.org` or similar) with an international registrar and point
its A record at the VDS's address. Use the registrar's own nameservers. Enable registrar lock
and privacy protection where available.

## Consequences

### Positive

- Cheap, fast, and self-service: no paperwork, and DNS changes take effect in minutes rather
  than requiring a request to anyone.
- The domain is portable. If the server ever moves, the name follows it by editing one record.
- Standard tooling, standard certificate issuance, nothing unusual to explain to anything.

### Negative / accepted costs

- **The registration depends on a foreign service reachable from here and payable from here.**
  Renewal failures are a silent way to lose a site; the renewal date belongs in a calendar with
  a reminder, and auto-renew should be on if the payment method allows it.
- DNS resolution for the domain depends on foreign nameservers being reachable from inside
  Turkmenistan. This is assumed and unverified — R4 in
  [`../04-risks-and-research.md`](../04-risks-and-research.md), and it blocks Sprint 02.
- A generic domain carries less local legitimacy than a `.tm` would for a library serving
  Turkmen readers.
- Certificate issuance via Let's Encrypt's HTTP challenge needs inbound port 80 to reach the
  VDS. If it is blocked, the DNS challenge is the fallback — which needs a registrar with an API,
  and is worth checking for when choosing one.

## Alternatives considered

- **A `.tm` domain.** More appropriate for the audience, and more expensive and slower to
  obtain. Worth revisiting once the project is established and the cost is justified by having
  actual readers.
- **A free subdomain** from a dynamic DNS provider. Free, and unsuitable for anything asking
  people for money.
- **No domain, just the IP address.** No certificate, no trust, and unusable in practice.
