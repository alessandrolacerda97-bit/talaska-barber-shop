"""product hardening: safe prices, ordering, gallery metadata and audit log

Revision ID: 0003_product_hardening
Revises: 0002_availability_safety
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_product_hardening"
down_revision = "0002_availability_safety"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _checks(bind, table: str) -> set[str]:
    return {
        check["name"]
        for check in sa.inspect(bind).get_check_constraints(table)
        if check.get("name")
    }


def upgrade():
    bind = op.get_bind()

    if "display_order" not in _columns(bind, "barbers"):
        op.add_column("barbers", sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))

    if "price_on_request" not in _columns(bind, "services"):
        op.add_column(
            "services",
            sa.Column("price_on_request", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    # Existing zero-price services are preserved and become consultation-only.
    # This is the only safe automatic interpretation; no value is invented.
    op.execute("UPDATE services SET price_on_request = true WHERE price = 0")

    if "alt_text" not in _columns(bind, "gallery"):
        op.add_column("gallery", sa.Column("alt_text", sa.String(length=200), nullable=True))
    if "display_order" not in _columns(bind, "gallery"):
        op.add_column("gallery", sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))

    if "appointment_status_history" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "appointment_status_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
            sa.Column("previous_status", sa.String(length=20), nullable=True),
            sa.Column("new_status", sa.String(length=20), nullable=False),
            sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("changed_by_label", sa.String(length=120), nullable=False, server_default="Sistema"),
            sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_appointment_status_history_appointment_id", "appointment_status_history", ["appointment_id"])
        op.create_index("ix_appointment_status_history_changed_at", "appointment_status_history", ["changed_at"])

    # Keep old appointments valid but present the new standardized terminology.
    op.execute("UPDATE appointments SET status = 'scheduled' WHERE status = 'pending'")

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'")
        if "services_active_price_or_consultation" not in _checks(bind, "services"):
            op.execute(
                "ALTER TABLE services ADD CONSTRAINT services_active_price_or_consultation "
                "CHECK (active = false OR price > 0 OR price_on_request = true)"
            )
        op.execute(
            "CREATE INDEX IF NOT EXISTS appointments_date_status_idx "
            "ON appointments (appointment_date, status)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS appointments_barber_start_idx "
            "ON appointments (barber_id, start_datetime)"
        )
        # The user explicitly supplied the official account. Only blank legacy
        # values are filled, so an owner-provided setting is never overwritten.
        op.execute(
            "UPDATE settings SET value = 'https://www.instagram.com/talaskabarbershop/' "
            "WHERE key = 'instagram' AND trim(value) = ''"
        )
        op.execute(
            "INSERT INTO settings (key, value) VALUES "
            "('instagram', 'https://www.instagram.com/talaskabarbershop/') "
            "ON CONFLICT (key) DO NOTHING"
        )
        for key, value in (
            ("hero_desktop_position", "72% center"),
            ("hero_mobile_position", "64% center"),
        ):
            bind.execute(
                sa.text(
                    "INSERT INTO settings (key, value) VALUES (:key, :value) "
                    "ON CONFLICT (key) DO NOTHING"
                ),
                {"key": key, "value": value},
            )


def downgrade():
    # No destructive downgrade: gallery metadata, audit history and existing
    # prices are business records and should only be removed by an explicit
    # data-retention decision.
    pass

