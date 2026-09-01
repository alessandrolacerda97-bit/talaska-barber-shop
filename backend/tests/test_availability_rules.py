from datetime import date, datetime, time, timedelta

import pytest
from fastapi import HTTPException

from app.core.config import normalize_database_url
from app.main import ensure_non_overlapping_hours, schedule_hours, working
from app.models import Barber, BarberHour, BusinessHour


def test_neon_connection_url_uses_psycopg_driver():
    assert normalize_database_url("postgresql://user:secret@ep-neon/db?sslmode=require").startswith(
        "postgresql+psycopg://"
    )


def test_empty_custom_schedule_does_not_fall_back_to_shop_hours(db):
    barber = Barber(name="Profissional", custom_hours_enabled=True)
    db.add_all(
        [
            barber,
            BusinessHour(weekday=0, start_time=time(9), end_time=time(18), active=True),
        ]
    )
    db.commit()
    start = datetime.combine(date(2030, 1, 7), time(10))  # Monday

    assert schedule_hours(db, barber, 0) == []
    assert not working(db, barber, start, start + timedelta(minutes=30))


def test_overlapping_active_hours_are_rejected():
    first = BusinessHour(weekday=0, start_time=time(9), end_time=time(12), active=True)
    second = BusinessHour(weekday=0, start_time=time(11), end_time=time(14), active=True)

    with pytest.raises(HTTPException) as error:
        ensure_non_overlapping_hours([first, second])
    assert error.value.status_code == 422


def test_inactive_intervals_do_not_block_a_valid_schedule():
    first = BarberHour(barber_id=1, weekday=0, start_time=time(9), end_time=time(12), active=True)
    second = BarberHour(barber_id=1, weekday=0, start_time=time(10), end_time=time(11), active=False)

    ensure_non_overlapping_hours([first, second])
