# Security identity and corporate actions

QUANTCORE treats a ticker as a **listing identifier**, not as the durable identity of a security.

## Security identity

`Security` is the durable internal security identity and is attached to a `Company`. A ticker/exchange
combination is represented as a time-bounded row in `security_identifier_history`.

External identifiers such as CUSIP, ISIN, SEDOL, FIGI, LEI, and provider-specific identifiers are stored
in `security_identifiers`. Each mapping has:

- `valid_from` / `valid_to`: when the identifier was effective, with `valid_to` exclusive
- `known_at`: when QUANTCORE knew the mapping
- `source` / `source_reference`: provenance

Historical research must resolve identifiers using both the effective date and the knowledge timestamp.
A mapping learned after the research cutoff must not leak into an earlier snapshot.

The security universe sync closes effective listing intervals when a ticker/exchange association disappears.
If the same listing later returns, a new effective interval is created instead of overwriting the old history.

## Corporate actions

Corporate actions are normalized as security-level events. In addition to dividends and stock splits, the
canonical taxonomy supports identity-impacting events such as mergers, acquisitions, spin-offs, ticker or
exchange changes, share-class changes, delistings, conversions, tender offers, recapitalizations, and
liquidations.

Identity-impacting events can reference a related security and carry old/new ticker and exchange values.
`corporate_action_revisions` preserves immutable knowledge snapshots so a point-in-time read can reconstruct
what QUANTCORE knew at a historical timestamp.

Provider adapters remain responsible for translating their source-specific corporate-action vocabulary into
this canonical model. No provider is assumed to supply every event type.

## Research invariant

For historical analysis, QUANTCORE should follow this chain:

`provider identifier -> security identity -> effective interval -> known-at cutoff -> research observation`

Never infer security identity solely from a current ticker string.
