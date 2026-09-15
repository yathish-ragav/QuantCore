# QuantCore Documentation

This documentation set is the authoritative technical and research description of the current QuantCore implementation. Claims should be kept synchronized with the code and verified repository state.

## Start here

- [Architecture](architecture/README.md) — system boundaries, dependency direction, and runtime flow.
- [Research methodology](research/README.md) — quantitative research contracts and analytical stages.
- [Data sources and temporal semantics](data-sources.md) — provider responsibilities, ingestion, PIT, provenance, and data-domain semantics.
- [Reproducibility](reproducibility/README.md) — identities, canonicalization, fingerprints, and research reproducibility.
- [API](api/README.md) — current HTTP product surface, authentication, authorization, and contract boundaries.
- [Scientific evaluation](scientific/evaluation.md) — evaluation protocol, current evidence, and pending empirical work.
- [Scientific evidence matrix](scientific/evidence-matrix.md) — implementation evidence, claim discipline, and publication-readiness mapping.
- [Publication](publication/README.md) — journal-oriented manuscript, references, and publication policy.
- [Public release checklist](release-checklist.md) — repository, scientific, data, security, and launch readiness.

## Documentation policy

1. Document implemented behavior before planned behavior.
2. Distinguish current implementation, architectural intent, and future work.
3. Never invent benchmark, financial-performance, latency, or coverage claims.
4. Record reproducibility requirements alongside the methodology they protect.
5. Keep public documentation independent of private environment values and credentials.
6. Treat the Git repository and its verified tests as the implementation source of truth.
