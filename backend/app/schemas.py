from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AppointmentIn(BaseModel):
    service_id: int
    barber_id: int | None = None
    appointment_date: date
    start_time: time
    customer_name: str = Field(min_length=2, max_length=150)
    customer_phone: str = Field(min_length=8, max_length=30)
    customer_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentUpdate(BaseModel):
    status: str | None = None
    barber_id: int | None = None
    service_id: int | None = None
    start_datetime: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class EntityIn(BaseModel):
    """Shared payload for barber/service administration.

    Every field is optional so a PATCH-like PUT cannot reactivate a record just
    because its `active` field was omitted. Creation validates its required
    fields in the route according to the entity type.
    """

    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    active: bool | None = None
    bio: str | None = Field(default=None, max_length=2000)
    photo_url: str | None = Field(default=None, max_length=500)
    specialties: str | None = Field(default=None, max_length=1000)
    commission_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    image_url: str | None = Field(default=None, max_length=500)
    display_order: int | None = Field(default=None, ge=0)


class HourIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=segunda-feira; 6=domingo")
    start_time: time
    end_time: time
    active: bool = True

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("O horário final deve ser posterior ao horário inicial.")
        return self


class BusinessHourIn(HourIn):
    pass


class BarberHourIn(HourIn):
    barber_id: int


class BusinessHoursReplaceIn(BaseModel):
    hours: list[BusinessHourIn] = Field(default_factory=list)


class BarberHoursReplaceIn(BaseModel):
    barber_id: int
    hours: list[HourIn] = Field(default_factory=list)


class BlockedTimeIn(BaseModel):
    barber_id: int | None = None
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("O fim do bloqueio deve ser posterior ao início.")
        return self


class BlockedTimesReplaceIn(BaseModel):
    blocked_times: list[BlockedTimeIn] = Field(default_factory=list)
