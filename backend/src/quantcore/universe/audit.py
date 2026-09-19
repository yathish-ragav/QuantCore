from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from quantcore.core.enums import SecurityType
from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus
from quantcore.universe.providers.massive import MassiveUniverseProvider
from quantcore.universe.symbol_reconciliation import symbol_aliases

MAX_CANDIDATES = 10


def _security_rows(db: Session) -> list[Security]:
    return list(
        db.scalars(
            select(Security)
            .options(joinedload(Security.company))
            .join(Company, Company.id == Security.company_id)
            .where(Security.status == SecurityStatus.ACTIVE)
            .order_by(Security.id)
        ).all()
    )


def audit(db: Session, provider: MassiveUniverseProvider) -> dict:
    securities = _security_rows(db)
    classifications = provider.fetch()

    by_identity = {}
    for item in classifications:
        key = (item.cik, item.symbol)
        by_identity[key] = item

    symbols_by_cik: dict[str, set[str]] = defaultdict(set)
    ciks_by_symbol: dict[str, set[str]] = defaultdict(set)
    by_reconciled_identity: dict[tuple[str, str], list] = defaultdict(list)
    for item in classifications:
        symbols_by_cik[item.cik].add(item.symbol)
        ciks_by_symbol[item.symbol].add(item.cik)
        for alias in symbol_aliases(item.symbol):
            by_reconciled_identity[(item.cik, alias)].append(item)

    unknown = []
    unmatched = []
    classified = []
    reconciled = []

    def resolve(cik: str, symbol: str):
        exact = by_identity.get((cik, symbol))
        if exact is not None:
            return exact, False

        candidates = []
        seen = set()
        for alias in symbol_aliases(symbol):
            for item in by_reconciled_identity.get((cik, alias), []):
                identity = (item.cik, item.symbol)
                if identity not in seen:
                    seen.add(identity)
                    candidates.append(item)

        if len(candidates) == 1:
            return candidates[0], True
        return None, False

    for security in securities:
        cik = security.company.cik
        symbol = security.symbol.upper()
        item, was_reconciled = resolve(cik, symbol)
        if item is not None:
            if item.security_type is SecurityType.UNKNOWN:
                unknown.append(
                    {
                        "security_id": security.id,
                        "cik": cik,
                        "symbol": symbol,
                        "exchange": security.exchange,
                        "company_name": security.company.name,
                        "provider_type": item.provider_type,
                        "source_reference": item.source_reference,
                    }
                )
            else:
                classified.append(security.id)
                if was_reconciled:
                    reconciled.append(
                        {
                            "security_id": security.id,
                            "cik": cik,
                            "symbol": symbol,
                            "exchange": security.exchange,
                            "company_name": security.company.name,
                            "massive_symbol": item.symbol,
                            "provider_type": item.provider_type,
                            "source_reference": item.source_reference,
                        }
                    )
            continue

        cik_candidates = sorted(symbols_by_cik.get(cik, set()))
        symbol_candidates = sorted(ciks_by_symbol.get(symbol, set()))
        if cik_candidates and symbol_candidates:
            reason = "CIK_AND_SYMBOL_PRESENT_BUT_CROSS-MATCHED"
        elif cik_candidates:
            reason = "CIK_PRESENT_DIFFERENT_SYMBOL"
        elif symbol_candidates:
            reason = "SYMBOL_PRESENT_DIFFERENT_CIK"
        else:
            reason = "NEITHER_CIK_NOR_SYMBOL_PRESENT"

        unmatched.append(
            {
                "security_id": security.id,
                "cik": cik,
                "symbol": symbol,
                "exchange": security.exchange,
                "company_name": security.company.name,
                "reason": reason,
                "massive_symbols_for_cik": cik_candidates[:MAX_CANDIDATES],
                "massive_ciks_for_symbol": symbol_candidates[:MAX_CANDIDATES],
            }
        )

    unknown_by_type = Counter(item["provider_type"] or "<MISSING>" for item in unknown)
    unmatched_by_reason = Counter(item["reason"] for item in unmatched)

    observed_types = Counter(
        item.provider_type or "<MISSING>" for item in classifications
    )

    now = datetime.now(timezone.utc)
    report = {
        "generated_at": now.isoformat(),
        "scope": {
            "database_security_status": SecurityStatus.ACTIVE.value,
            "provider": "MASSIVE",
            "provider_scope": "active stock reference tickers",
            "database_security_count": len(securities),
            "provider_reference_count": len(classifications),
        },
        "summary": {
            "classified": len(classified),
            "unknown": len(unknown),
            "unmatched": len(unmatched),
            "classified_plus_unknown_plus_unmatched": (
                len(classified) + len(unknown) + len(unmatched)
            ),
        },
        "unknown": {
            "by_provider_type": dict(sorted(unknown_by_type.items())),
            "securities": unknown,
        },
        "unmatched": {
            "by_reason": dict(sorted(unmatched_by_reason.items())),
            "securities": unmatched,
        },
        "reconciliation": {
            "alias_resolved_count": len(reconciled),
            "alias_resolved": reconciled,
        },
        "provider_type_distribution": dict(sorted(observed_types.items())),
    }
    return report
