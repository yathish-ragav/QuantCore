from logging.config import fileConfig

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String, engine_from_config, pool

from alembic import context
from quantcore.core.config import settings
from quantcore.db.database import Base

# Import every model so SQLAlchemy metadata contains
# the complete application schema.

config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _quantcore_compare_type(
    context,
    inspected_column,
    metadata_column,
    inspected_type,
    metadata_type,
):
    # QuantCore stores SQLAlchemy enums as VARCHAR + CHECK (native_enum=False).
    # PostgreSQL reflects those columns as VARCHAR; do not report a false
    # VARCHAR -> Enum type change. Still report a real undersized VARCHAR.
    if (
        isinstance(metadata_type, SQLAlchemyEnum)
        and not metadata_type.native_enum
        and isinstance(inspected_type, String)
    ):
        expected = metadata_type.length
        if expected is None:
            expected = max(
                (len(str(v)) for v in (metadata_type.enums or ())),
                default=0,
            )
        actual = inspected_type.length
        return not (actual is None or actual >= expected)
    return None


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=_quantcore_compare_type,
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
            compare_type=_quantcore_compare_type,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()