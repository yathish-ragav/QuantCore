# Public Release Checklist

This checklist records release concerns that are distinct from the deterministic research implementation.

## Repository hygiene

- [x] Root README describes the current implementation honestly.
- [x] Backend README points to the canonical documentation.
- [x] Technical documentation has a single top-level `docs/` home.
- [x] Obsolete ad-hoc database inspection/test scripts are not part of the production repository.
- [x] Empty deployment/configuration placeholders are not represented as implemented infrastructure.
- [ ] Decide and populate the project license before public distribution.

## Software verification

- [ ] Run the complete local test suite from the exact supported development environment.
- [ ] Run static analysis/type checks used by the project and resolve release-blocking findings.
- [ ] Verify database migrations from a clean database.
- [ ] Verify API authentication/authorization with the intended OIDC provider configuration.
- [ ] Verify production configuration does not contain secrets in the repository.

## Data and licensing

- [ ] Confirm each provider's production usage rights.
- [ ] Confirm redistribution restrictions for any published data or artifacts.
- [ ] Document source-specific coverage and freshness limits.
- [ ] Establish a policy for reproducibility when raw provider data cannot legally be redistributed.

## Scientific release

- [ ] Freeze the evaluated software commit.
- [ ] Freeze experiment definitions and dataset identities.
- [ ] Archive experiment inputs/results/artifacts permitted for release.
- [ ] Run PIT-integrity experiments.
- [ ] Run deterministic-reproducibility experiments.
- [ ] Run analytical reconciliation tests.
- [ ] Run the empirical research evaluation.
- [ ] Generate tables/figures directly from archived artifacts.
- [ ] Review all manuscript claims against reproducible evidence.

## Product release

- [ ] Complete the agentic AI layer.
- [ ] Complete the institutional frontend.
- [ ] Complete production security hardening.
- [ ] Establish observability and operational runbooks.
- [ ] Establish deployment/CI/CD infrastructure.
- [ ] Complete end-to-end production validation.
