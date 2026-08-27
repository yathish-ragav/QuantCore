from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from quantcore.core.config import settings
from quantcore.db.database import Base

# Import every model so SQLAlchemy metadata contains
# the complete application schema.
from quantcore.models.company import Company
from quantcore.models.security import Security
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.models.price import Price
from quantcore.models.news import News
from quantcore.models.income_statement import IncomeStatement
from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.models.balance_sheet import BalanceSheet
from quantcore.models.provenance import CompanyFieldProvenance
from quantcore.models.ingestion import IngestionRun, IngestionState
from quantcore.models.sec_filing import FilingEvent, SECFiling
from quantcore.models.corporate_action import CorporateAction
from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation
from quantcore.models.macro import MacroObservation, MacroSeries
from quantcore.models.macro_ingestion import MacroIngestionState


config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()