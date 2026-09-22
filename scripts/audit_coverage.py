from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Integer, func, select

from quantcore.db.database import SessionLocal
from quantcore.models.balance_sheet import BalanceSheet
from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.models.corporate_action import CorporateAction
from quantcore.models.financial_statement_revision import FinancialStatementRevision
from quantcore.models.income_statement import IncomeStatement
from quantcore.models.price import Price
from quantcore.models.price_observation_revision import PriceObservationRevision
from quantcore.models.sec_filing import SECFiling
from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation
from quantcore.models.security import Security
from quantcore.core.enums import FinancialStatementType, SecurityType
from quantcore.models.provenance import DataSource


STATEMENT_MODELS = {
    "income_statement": IncomeStatement,
    "balance_sheet": BalanceSheet,
    "cash_flow_statement": CashFlowStatement,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only historical coverage audit for a deterministic QuantCore cohort."
        )
    )
    parser.add_argument(
        "--cohort-size",
        type=int,
        default=25,
        help="Deterministic classified common-stock cohort size (default: 25).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def _date_value(value):
    return value.isoformat() if value is not None else None


def _datetime_value(value):
    return value.isoformat() if value is not None else None


def _calendar_gap_stats(dates: list[date | datetime]) -> dict[str, object]:
    normalized = sorted({value.date() if isinstance(value, datetime) else value for value in dates})
    if len(normalized) < 2:
        return {
            "distinct_dates": len(normalized),
            "max_calendar_gap_days": None,
            "calendar_gaps_gt_7d": 0,
        }
    gaps = [(right - left).days for left, right in zip(normalized, normalized[1:])]
    return {
        "distinct_dates": len(normalized),
        "max_calendar_gap_days": max(gaps),
        "calendar_gaps_gt_7d": sum(gap > 7 for gap in gaps),
    }


def audit_prices(db, security_ids: tuple[int, ...]) -> dict:
    rows = db.execute(
        select(Price.security_id, Price.date)
        .where(Price.security_id.in_(security_ids))
        .order_by(Price.security_id, Price.date)
    ).all()
    dates_by_security: dict[int, list[datetime]] = defaultdict(list)
    for security_id, observed_at in rows:
        dates_by_security[security_id].append(observed_at)

    revision_rows = db.execute(
        select(PriceObservationRevision.price_id, PriceObservationRevision.known_at)
        .join(Price, Price.id == PriceObservationRevision.price_id)
        .where(Price.security_id.in_(security_ids))
    ).all()
    revisions_by_price: dict[int, list[datetime]] = defaultdict(list)
    for price_id, known_at in revision_rows:
        revisions_by_price[price_id].append(known_at)

    price_ids = db.execute(
        select(Price.id, Price.security_id)
        .where(Price.security_id.in_(security_ids))
    ).all()
    security_revision_times: dict[int, list[datetime]] = defaultdict(list)
    for price_id, security_id in price_ids:
        security_revision_times[security_id].extend(revisions_by_price.get(price_id, []))

    result = {}
    for security_id in security_ids:
        dates = dates_by_security.get(security_id, [])
        gap_stats = _calendar_gap_stats(dates)
        known_at = security_revision_times.get(security_id, [])
        result[str(security_id)] = {
            "observation_count": len(dates),
            "earliest": _datetime_value(min(dates)) if dates else None,
            "latest": _datetime_value(max(dates)) if dates else None,
            **gap_stats,
            "revision_count": len(known_at),
            "earliest_revision_known_at": _datetime_value(min(known_at)) if known_at else None,
            "latest_revision_known_at": _datetime_value(max(known_at)) if known_at else None,
        }
    return result


def audit_corporate_actions(db, security_ids: tuple[int, ...]) -> tuple[dict, dict]:
    rows = db.execute(
        select(
            CorporateAction.security_id,
            func.count(CorporateAction.id),
            func.min(CorporateAction.effective_date),
            func.max(CorporateAction.effective_date),
        )
        .where(CorporateAction.security_id.in_(security_ids))
        .group_by(CorporateAction.security_id)
    ).all()
    by_security = {
        str(security_id): {
            "event_count": count,
            "earliest_effective_date": _date_value(earliest),
            "latest_effective_date": _date_value(latest),
        }
        for security_id, count, earliest, latest in rows
    }

    duplicate_provider_rows = db.execute(
        select(
            CorporateAction.security_id,
            CorporateAction.effective_date,
            CorporateAction.action_type,
            CorporateAction.source,
            CorporateAction.source_reference,
            func.count(CorporateAction.id).label("count"),
        )
        .where(CorporateAction.security_id.in_(security_ids))
        .group_by(
            CorporateAction.security_id,
            CorporateAction.effective_date,
            CorporateAction.action_type,
            CorporateAction.source,
            CorporateAction.source_reference,
        )
        .having(func.count(CorporateAction.id) > 1)
    ).all()

    same_day_type_rows = db.execute(
        select(
            CorporateAction.security_id,
            CorporateAction.effective_date,
            CorporateAction.action_type,
            func.count(CorporateAction.id).label("count"),
        )
        .where(CorporateAction.security_id.in_(security_ids))
        .group_by(
            CorporateAction.security_id,
            CorporateAction.effective_date,
            CorporateAction.action_type,
        )
        .having(func.count(CorporateAction.id) > 1)
    ).all()

    duplicate_summary = {
        "duplicate_provider_identity_groups": len(duplicate_provider_rows),
        "duplicate_provider_identity_rows": sum(row.count for row in duplicate_provider_rows),
        "same_day_same_type_groups": len(same_day_type_rows),
        "max_same_day_same_type_count": max((row.count for row in same_day_type_rows), default=1),
    }
    return by_security, duplicate_summary


def audit_statements(db, security_company_ids: dict[int, int]) -> dict:
    company_ids = tuple(sorted(set(security_company_ids.values())))
    result: dict[str, dict] = {}
    for name, model in STATEMENT_MODELS.items():
        current_rows = db.execute(
            select(
                model.company_id,
                func.count(model.id),
                func.min(model.fiscal_date),
                func.max(model.fiscal_date),
                func.min(model.filing_date),
                func.max(model.filing_date),
                func.min(model.fetched_at),
                func.max(model.fetched_at),
            )
            .where(model.company_id.in_(company_ids))
            .group_by(model.company_id)
        ).all()
        current_by_company = {
            company_id: {
                "current_row_count": count,
                "earliest_fiscal_date": _date_value(earliest_fiscal),
                "latest_fiscal_date": _date_value(latest_fiscal),
                "earliest_filing_date": _date_value(earliest_filing),
                "latest_filing_date": _date_value(latest_filing),
                "earliest_fetched_at": _datetime_value(earliest_fetched),
                "latest_fetched_at": _datetime_value(latest_fetched),
            }
            for (
                company_id,
                count,
                earliest_fiscal,
                latest_fiscal,
                earliest_filing,
                latest_filing,
                earliest_fetched,
                latest_fetched,
            ) in current_rows
        }

        revision_rows = db.execute(
            select(
                FinancialStatementRevision.company_id,
                func.count(FinancialStatementRevision.id),
                func.min(FinancialStatementRevision.fiscal_date),
                func.max(FinancialStatementRevision.fiscal_date),
                func.min(FinancialStatementRevision.filing_date),
                func.max(FinancialStatementRevision.filing_date),
                func.min(FinancialStatementRevision.known_at),
                func.max(FinancialStatementRevision.known_at),
            )
            .where(
                FinancialStatementRevision.company_id.in_(company_ids),
                FinancialStatementRevision.statement_type == {
                    "income_statement": FinancialStatementType.INCOME,
                    "balance_sheet": FinancialStatementType.BALANCE_SHEET,
                    "cash_flow_statement": FinancialStatementType.CASH_FLOW,
                }[name],
            )
            .group_by(FinancialStatementRevision.company_id)
        ).all()
        revisions_by_company = {
            company_id: {
                "revision_count": count,
                "earliest_revision_fiscal_date": _date_value(earliest_fiscal),
                "latest_revision_fiscal_date": _date_value(latest_fiscal),
                "earliest_revision_filing_date": _date_value(earliest_filing),
                "latest_revision_filing_date": _date_value(latest_filing),
                "earliest_revision_known_at": _datetime_value(earliest_known),
                "latest_revision_known_at": _datetime_value(latest_known),
            }
            for (
                company_id,
                count,
                earliest_fiscal,
                latest_fiscal,
                earliest_filing,
                latest_filing,
                earliest_known,
                latest_known,
            ) in revision_rows
        }

        for security_id, company_id in security_company_ids.items():
            result.setdefault(str(security_id), {})[name] = {
                **current_by_company.get(company_id, {
                    "current_row_count": 0,
                    "earliest_fiscal_date": None,
                    "latest_fiscal_date": None,
                    "earliest_filing_date": None,
                    "latest_filing_date": None,
                    "earliest_fetched_at": None,
                    "latest_fetched_at": None,
                }),
                **revisions_by_company.get(company_id, {
                    "revision_count": 0,
                    "earliest_revision_fiscal_date": None,
                    "latest_revision_fiscal_date": None,
                    "earliest_revision_filing_date": None,
                    "latest_revision_filing_date": None,
                    "earliest_revision_known_at": None,
                    "latest_revision_known_at": None,
                }),
            }
    return result


def audit_sec_filings(db, security_company_ids: dict[int, int]) -> dict:
    company_ids = tuple(sorted(set(security_company_ids.values())))
    rows = db.execute(
        select(
            SECFiling.company_id,
            func.count(SECFiling.id),
            func.count(func.distinct(SECFiling.accession_number)),
            func.min(SECFiling.filing_date),
            func.max(SECFiling.filing_date),
            func.min(SECFiling.report_date),
            func.max(SECFiling.report_date),
            func.min(SECFiling.acceptance_datetime),
            func.max(SECFiling.acceptance_datetime),
            func.sum(func.cast(SECFiling.is_amendment, Integer)),
        )
        .where(SECFiling.company_id.in_(company_ids))
        .group_by(SECFiling.company_id)
    ).all()
    by_company = {
        company_id: {
            "filing_count": count,
            "distinct_accessions": distinct_accessions,
            "earliest_filing_date": _date_value(earliest_filing),
            "latest_filing_date": _date_value(latest_filing),
            "earliest_report_date": _date_value(earliest_report),
            "latest_report_date": _date_value(latest_report),
            "earliest_acceptance_datetime": _datetime_value(earliest_acceptance),
            "latest_acceptance_datetime": _datetime_value(latest_acceptance),
            "amendment_count": amendment_count or 0,
        }
        for (
            company_id,
            count,
            distinct_accessions,
            earliest_filing,
            latest_filing,
            earliest_report,
            latest_report,
            earliest_acceptance,
            latest_acceptance,
            amendment_count,
        ) in rows
    }
    duplicate_accessions = db.execute(
        select(SECFiling.accession_number, func.count(SECFiling.id))
        .where(SECFiling.company_id.in_(company_ids))
        .group_by(SECFiling.accession_number)
        .having(func.count(SECFiling.id) > 1)
    ).all()
    result = {}
    for security_id, company_id in security_company_ids.items():
        result[str(security_id)] = by_company.get(company_id, {
            "filing_count": 0,
            "distinct_accessions": 0,
            "earliest_filing_date": None,
            "latest_filing_date": None,
            "earliest_report_date": None,
            "latest_report_date": None,
            "earliest_acceptance_datetime": None,
            "latest_acceptance_datetime": None,
            "amendment_count": 0,
        })
    return {
        "by_security": result,
        "duplicate_accession_groups": len(duplicate_accessions),
    }


def audit_xbrl(db, security_company_ids: dict[int, int]) -> dict:
    company_ids = tuple(sorted(set(security_company_ids.values())))
    rows = db.execute(
        select(
            SECXBRLFactObservation.company_id,
            func.count(SECXBRLFactObservation.id),
            func.count(func.distinct(SECXBRLFactObservation.accession_number)),
            func.min(SECXBRLFactObservation.period_end),
            func.max(SECXBRLFactObservation.period_end),
            func.min(SECXBRLFactObservation.filed_at),
            func.max(SECXBRLFactObservation.filed_at),
            func.min(SECXBRLFactObservation.accepted_at),
            func.max(SECXBRLFactObservation.accepted_at),
            func.sum(func.cast(SECXBRLFactObservation.accepted_at.is_(None), Integer)),
            func.sum(func.cast(SECXBRLFactObservation.filing_id.is_(None), Integer)),
        )
        .where(SECXBRLFactObservation.company_id.in_(company_ids))
        .group_by(SECXBRLFactObservation.company_id)
    ).all()
    by_company = {
        company_id: {
            "observation_count": count,
            "distinct_accessions": distinct_accessions,
            "earliest_period_end": _date_value(earliest_period),
            "latest_period_end": _date_value(latest_period),
            "earliest_filed_at": _date_value(earliest_filed),
            "latest_filed_at": _date_value(latest_filed),
            "earliest_accepted_at": _datetime_value(earliest_accepted),
            "latest_accepted_at": _datetime_value(latest_accepted),
            "accepted_at_null_count": accepted_null or 0,
            "filing_id_null_count": filing_id_null or 0,
        }
        for (
            company_id,
            count,
            distinct_accessions,
            earliest_period,
            latest_period,
            earliest_filed,
            latest_filed,
            earliest_accepted,
            latest_accepted,
            accepted_null,
            filing_id_null,
        ) in rows
    }
    duplicate_identity_rows = db.execute(
        select(SECXBRLFactObservation.identity_hash, func.count(SECXBRLFactObservation.id))
        .where(SECXBRLFactObservation.company_id.in_(company_ids))
        .group_by(SECXBRLFactObservation.identity_hash)
        .having(func.count(SECXBRLFactObservation.id) > 1)
    ).all()
    result = {}
    for security_id, company_id in security_company_ids.items():
        result[str(security_id)] = by_company.get(company_id, {
            "observation_count": 0,
            "distinct_accessions": 0,
            "earliest_period_end": None,
            "latest_period_end": None,
            "earliest_filed_at": None,
            "latest_filed_at": None,
            "earliest_accepted_at": None,
            "latest_accepted_at": None,
            "accepted_at_null_count": 0,
            "filing_id_null_count": 0,
        })
    return {
        "by_security": result,
        "duplicate_identity_groups": len(duplicate_identity_rows),
        "pit_timestamp_field": "accepted_at",
        "pit_timestamp_note": (
            "SEC XBRL observations do not have a dedicated known_at column; "
            "accepted_at is reported as the SEC acceptance timestamp and should not "
            "be conflated with QuantCore fetch time."
        ),
    }


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        if args.cohort_size <= 0:
            raise ValueError("cohort-size must be greater than zero")
        securities = db.execute(
            select(Security.id, Security.company_id, Security.symbol, Security.exchange)
            .where(
                Security.status == "ACTIVE",
                Security.security_type == SecurityType.COMMON_STOCK,
                Security.security_type_source == DataSource.MASSIVE,
                Security.security_type_fetched_at.is_not(None),
            )
            .order_by(Security.id)
            .limit(args.cohort_size)
        ).all()
        if len(securities) != args.cohort_size:
            raise RuntimeError(
                f"Requested coverage cohort of {args.cohort_size}, but only "
                f"{len(securities)} classified active common stocks are available."
            )
        members = tuple((row.id, row.symbol, row.exchange) for row in securities)
        cohort_fingerprint = hashlib.sha256(
            json.dumps(members, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        security_ids = tuple(row.id for row in securities)
        security_company_ids = {row.id: row.company_id for row in securities}
        security_meta = {
            str(row.id): {
                "symbol": row.symbol,
                "exchange": row.exchange,
                "company_id": row.company_id,
            }
            for row in securities
        }

        corporate_actions, corporate_action_identity = audit_corporate_actions(db, security_ids)
        statements = audit_statements(db, security_company_ids)
        filings = audit_sec_filings(db, security_company_ids)
        xbrl = audit_xbrl(db, security_company_ids)
        prices = audit_prices(db, security_ids)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "cohort": {
                "type": "CURRENT_CLASSIFIED_COMMON_STOCK_COHORT",
                "size": len(security_ids),
                "fingerprint": cohort_fingerprint,
                "symbols": [row.symbol for row in securities],
            },
            "security_metadata": security_meta,
            "coverage": {
                "prices": prices,
                "corporate_actions": {
                    "by_security": corporate_actions,
                    "identity_audit": corporate_action_identity,
                },
                "financial_statements": statements,
                "sec_filings": filings,
                "sec_xbrl_facts": xbrl,
            },
        }
        output = json.dumps(payload, indent=2, sort_keys=True)
        print(output)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output + "\n", encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
