"""availability controls and PostgreSQL booking protection

Revision ID: 0002_availability_safety
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_availability_safety"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _constraint_names(bind, table_name: str) -> set[str]:
    return {
        constraint.get("name")
        for constraint in sa.inspect(bind).get_check_constraints(table_name)
        if constraint.get("name")
    }


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 0001 historically used metadata.create_all(), so inspect first: a fresh
    # database running the current metadata already contains this field, while
    # an older database receives it here.
    if "custom_hours_enabled" not in _column_names(bind, "barbers"):
        op.add_column(
            "barbers",
            sa.Column(
                "custom_hours_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if dialect != "postgresql":
        return

    check_constraints = {
        table: _constraint_names(bind, table)
        for table in ("services", "appointments", "business_hours", "barber_hours", "blocked_times")
    }
    statements = (
        ("services", "services_duration_minimum", "ALTER TABLE services ADD CONSTRAINT services_duration_minimum CHECK (duration_minutes >= 5)"),
        ("services", "services_price_non_negative", "ALTER TABLE services ADD CONSTRAINT services_price_non_negative CHECK (price >= 0)"),
        ("appointments", "appointments_valid_time_range", "ALTER TABLE appointments ADD CONSTRAINT appointments_valid_time_range CHECK (end_datetime > start_datetime)"),
        ("business_hours", "business_hours_valid_weekday", "ALTER TABLE business_hours ADD CONSTRAINT business_hours_valid_weekday CHECK (weekday BETWEEN 0 AND 6)"),
        ("business_hours", "business_hours_valid_time_range", "ALTER TABLE business_hours ADD CONSTRAINT business_hours_valid_time_range CHECK (end_time > start_time)"),
        ("barber_hours", "barber_hours_valid_weekday", "ALTER TABLE barber_hours ADD CONSTRAINT barber_hours_valid_weekday CHECK (weekday BETWEEN 0 AND 6)"),
        ("barber_hours", "barber_hours_valid_time_range", "ALTER TABLE barber_hours ADD CONSTRAINT barber_hours_valid_time_range CHECK (end_time > start_time)"),
        ("blocked_times", "blocked_times_valid_time_range", "ALTER TABLE blocked_times ADD CONSTRAINT blocked_times_valid_time_range CHECK (end_datetime > start_datetime)"),
    )
    for table, name, statement in statements:
        if name not in check_constraints[table]:
            op.execute(statement)

    # Database-level protection complements advisory locks and also protects
    # writes made outside this API. btree_gist supplies the integer equality
    # operator required by the mixed GiST exclusion constraint.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # SQLAlchemy's inspector does not consistently report exclusion constraints,
    # so PostgreSQL's catalog is the reliable source here.
    exclusion_exists = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = "
            "'appointments_no_active_overlap'"
        )
    ).scalar()
    if not exclusion_exists:
        op.execute(
            "ALTER TABLE appointments ADD CONSTRAINT appointments_no_active_overlap "
            "EXCLUDE USING gist (barber_id WITH =, "
            "tsrange(start_datetime, end_datetime, '[)') WITH &&) "
            "WHERE (status IN ('pending', 'confirmed', 'completed'))"
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_no_active_overlap")
        for table, name in (
            ("blocked_times", "blocked_times_valid_time_range"),
            ("barber_hours", "barber_hours_valid_time_range"),
            ("barber_hours", "barber_hours_valid_weekday"),
            ("business_hours", "business_hours_valid_time_range"),
            ("business_hours", "business_hours_valid_weekday"),
            ("appointments", "appointments_valid_time_range"),
            ("services", "services_price_non_negative"),
            ("services", "services_duration_minimum"),
        ):
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    if "custom_hours_enabled" in _column_names(bind, "barbers"):
        op.drop_column("barbers", "custom_hours_enabled")
