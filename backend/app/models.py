import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def token() -> str:
    return uuid.uuid4().hex[:16].upper()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Barber(Base):
    __tablename__ = "barbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    specialties: Mapped[str | None] = mapped_column(Text, nullable=True)
    commission_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    # When true, an empty barber_hours schedule intentionally means unavailable.
    # This keeps an admin from accidentally falling back to the shop schedule after
    # removing the last custom interval.
    custom_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes >= 5", name="services_duration_minimum"),
        CheckConstraint("price >= 0", name="services_price_non_negative"),
        CheckConstraint(
            "active = false OR price > 0 OR price_on_request = true",
            name="services_active_price_or_consultation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # A zero price is only public when the owner deliberately marks it as
    # consultation-only. This avoids exposing an accidental R$ 0,00.
    price_on_request: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="appointments_valid_time_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_token: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=token)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    appointment_date: Mapped[date] = mapped_column(Date)
    start_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AppointmentStatusHistory(Base):
    __tablename__ = "appointment_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20))
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_by_label: Mapped[str] = mapped_column(String(120), default="Sistema")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class BusinessHour(Base):
    __tablename__ = "business_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="business_hours_valid_weekday"),
        CheckConstraint("end_time > start_time", name="business_hours_valid_time_range"),
        UniqueConstraint("weekday", "start_time", "end_time", name="business_hours_unique_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BarberHour(Base):
    __tablename__ = "barber_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="barber_hours_valid_weekday"),
        CheckConstraint("end_time > start_time", name="barber_hours_valid_time_range"),
        UniqueConstraint(
            "barber_id", "weekday", "start_time", "end_time", name="barber_hours_unique_interval"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    barber_id: Mapped[int] = mapped_column(ForeignKey("barbers.id"))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlockedTime(Base):
    __tablename__ = "blocked_times"
    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="blocked_times_valid_time_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # A null barber_id blocks the entire shop.
    barber_id: Mapped[int | None] = mapped_column(ForeignKey("barbers.id"), nullable=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Gallery(Base):
    __tablename__ = "gallery"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

