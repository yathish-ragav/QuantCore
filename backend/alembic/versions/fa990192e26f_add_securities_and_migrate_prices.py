"""add securities and migrate prices

Revision ID: fa990192e26f
Revises: d10b31c37d56
Create Date: 2026-08-13 15:46:25.324161

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision: str = "fa990192e26f"

down_revision: Union[str, Sequence[str], None] = "d10b31c37d56"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---------------------------------------------------------
    # 1. Create securities table
    # ---------------------------------------------------------

    op.create_table(
        "securities",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "exchange",
            sa.String(length=50),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_securities_company_id",
        "securities",
        ["company_id"],
        unique=False,
    )

    op.create_index(
        "ix_securities_symbol",
        "securities",
        ["symbol"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 2. Create one security for every existing company
    # ---------------------------------------------------------

    op.execute(
        """
        INSERT INTO securities (
            company_id,
            symbol,
            exchange
        )
        SELECT
            id,
            symbol,
            exchange
        FROM companies
        """
    )

    # ---------------------------------------------------------
    # 3. Add security_id to existing prices
    # ---------------------------------------------------------

    op.add_column(
        "prices",
        sa.Column(
            "security_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_prices_security_id",
        "prices",
        ["security_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 4. Migrate existing prices from company_id → security_id
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE prices AS p
        SET security_id = s.id
        FROM securities AS s
        WHERE p.company_id = s.company_id
        """
    )

    # ---------------------------------------------------------
    # 5. Safety check
    #
    # Every existing price must now have a security.
    # If not, abort the migration instead of losing data.
    # ---------------------------------------------------------

    op.execute(
    sa.text(
        """
        DO $$
        DECLARE
            missing_prices INTEGER;
        BEGIN
            SELECT COUNT(*)
            INTO missing_prices
            FROM prices
            WHERE security_id IS NULL;

            IF missing_prices <> 0 THEN
                RAISE EXCEPTION
                    'Migration aborted: % price rows could not be mapped to a security.',
                    missing_prices;
            END IF;
        END
        $$;
        """
    )
)
    op.alter_column(
        "prices",
        "security_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 7. Add FK from prices → securities
    # ---------------------------------------------------------

    op.create_foreign_key(
        "prices_security_id_fkey",
        "prices",
        "securities",
        ["security_id"],
        ["id"],
    )

    # ---------------------------------------------------------
    # 8. Remove old company/date unique index
    # ---------------------------------------------------------

    op.drop_index(
        "ix_prices_company_date",
        table_name="prices",
    )

    # ---------------------------------------------------------
    # 9. Remove old company_id FK
    # ---------------------------------------------------------

    op.drop_constraint(
        "prices_company_id_fkey",
        "prices",
        type_="foreignkey",
    )

    # ---------------------------------------------------------
    # 10. Remove old company_id index
    # ---------------------------------------------------------

    op.drop_index(
        "ix_prices_company_id",
        table_name="prices",
    )

    # ---------------------------------------------------------
    # 11. Remove old company_id column
    # ---------------------------------------------------------

    op.drop_column(
        "prices",
        "company_id",
    )

    # ---------------------------------------------------------
    # 12. Create new security/date unique index
    # ---------------------------------------------------------

    op.create_index(
        "ix_prices_security_date",
        "prices",
        ["security_id", "date"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ---------------------------------------------------------
    # 1. Restore company_id on prices
    # ---------------------------------------------------------

    op.add_column(
        "prices",
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_prices_company_id",
        "prices",
        ["company_id"],
        unique=False,
    )

    # ---------------------------------------------------------
    # 2. Restore company_id using securities
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE prices AS p
        SET company_id = s.company_id
        FROM securities AS s
        WHERE p.security_id = s.id
        """
    )

    # ---------------------------------------------------------
    # 3. Safety check
    # ---------------------------------------------------------

    connection = op.get_bind()

    missing_companies = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM prices
            WHERE company_id IS NULL
            """
        )
    ).scalar_one()

    if missing_companies != 0:
        raise RuntimeError(
            f"Downgrade aborted: {missing_companies} price rows "
            "could not be mapped back to a company."
        )

    # ---------------------------------------------------------
    # 4. Make company_id mandatory
    # ---------------------------------------------------------

    op.alter_column(
        "prices",
        "company_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 5. Restore company FK
    # ---------------------------------------------------------

    op.create_foreign_key(
        "prices_company_id_fkey",
        "prices",
        "companies",
        ["company_id"],
        ["id"],
    )

    # ---------------------------------------------------------
    # 6. Remove security/date unique index
    # ---------------------------------------------------------

    op.drop_index(
        "ix_prices_security_date",
        table_name="prices",
    )

    # ---------------------------------------------------------
    # 7. Remove security FK
    # ---------------------------------------------------------

    op.drop_constraint(
        "prices_security_id_fkey",
        "prices",
        type_="foreignkey",
    )

    # ---------------------------------------------------------
    # 8. Remove security_id index
    # ---------------------------------------------------------

    op.drop_index(
        "ix_prices_security_id",
        table_name="prices",
    )

    # ---------------------------------------------------------
    # 9. Remove security_id
    # ---------------------------------------------------------

    op.drop_column(
        "prices",
        "security_id",
    )

    # ---------------------------------------------------------
    # 10. Restore original company/date unique index
    # ---------------------------------------------------------

    op.create_index(
        "ix_prices_company_date",
        "prices",
        ["company_id", "date"],
        unique=True,
    )

    # ---------------------------------------------------------
    # 11. Remove securities indexes
    # ---------------------------------------------------------

    op.drop_index(
        "ix_securities_symbol",
        table_name="securities",
    )

    op.drop_index(
        "ix_securities_company_id",
        table_name="securities",
    )

    # ---------------------------------------------------------
    # 12. Remove securities table
    # ---------------------------------------------------------

    op.drop_table("securities")