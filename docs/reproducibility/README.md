# Reproducibility

Reproducibility is a first-class design objective of QuantCore's research layer.

## Identity hierarchy

The research system uses explicit identities for the objects that determine a result:

```text
observation / feature identity
          |
          v
factor identity
          |
          v
signal identity
          |
          v
strategy identity
          |
          v
portfolio / backtest configuration
          |
          v
experiment definition
```

Where appropriate, identities are `(key, version)` pairs rather than mutable names.

## Canonicalization

Research definitions and result structures expose canonical payloads. Collections whose order is not semantically meaningful are normalized before fingerprinting. Timestamp and identity normalization is explicit rather than delegated to incidental Python object representation.

## Fingerprints

The current implementation provides deterministic fingerprints for, among other objects:

- research feature-vector inputs;
- historical research datasets;
- experiment definitions and run inputs;
- experiment execution results;
- artifacts and artifact provenance;
- experiment selections and comparisons.

Fingerprints are intended to identify the exact canonical research input/output contract represented by an object. They are not cryptographic proof that external data providers themselves are immutable.

## Dataset binding

Experiment runs can be bound to concrete research dataset snapshots. This prevents an experiment record from being identified only by a high-level strategy name while the underlying historical input changes.

## Temporal reproducibility

A reproducible historical result requires more than storing a calendar date. QuantCore therefore retains temporal semantics such as `known_at`, filing dates, and explicit research `as_of` values. Revision-aware domains are aligned through the PIT layer before downstream research computation.

## Reproduction protocol

A future published experiment should record at least:

1. QuantCore software commit/version.
2. Research definition identities and versions.
3. Dataset identity and fingerprint.
4. Feature/factor/signal/strategy identities.
5. Portfolio/backtest configuration.
6. Experiment run/execution identity.
7. Result and artifact fingerprints.
8. Data-provider/source configuration and licensing context where publication permits disclosure.

The repository should not publish private credentials or provider secrets as part of a reproduction artifact.
