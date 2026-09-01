from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.main import service_price_is_valid
from app.models import Appointment, AppointmentStatusHistory, Barber, Customer, Service


def test_active_service_requires_price_or_explicit_consultation():
    with pytest.raises(HTTPException) as error:
        service_price_is_valid(0, False, True)
    assert error.value.status_code == 422

    service_price_is_valid(0, True, True)
    service_price_is_valid(Decimal("45.00"), False, True)


def test_zero_price_service_is_persisted_only_as_consultation(db):
    service = Service(name="Consulta", price=0, price_on_request=True, duration_minutes=30)
    db.add(service)
    db.commit()
    assert service.price_on_request is True


def test_status_history_preserves_previous_and_new_status(db):
    barber = Barber(name="Histórico")
    service = Service(name="Serviço histórico", price=0, price_on_request=True, duration_minutes=30)
    customer = Customer(name="Cliente histórico", phone="51988887777")
    db.add_all([barber, service, customer])
    db.commit()
    appointment = Appointment(
        customer_id=customer.id,
        barber_id=barber.id,
        service_id=service.id,
        appointment_date=date(2030, 1, 1),
        start_datetime=datetime(2030, 1, 1, 10),
        end_datetime=datetime(2030, 1, 1, 10, 30),
        price=0,
        status="scheduled",
    )
    db.add(appointment)
    db.flush()
    db.add(AppointmentStatusHistory(appointment_id=appointment.id, previous_status="scheduled", new_status="confirmed", changed_by_label="admin"))
    db.commit()
    history = db.query(AppointmentStatusHistory).filter_by(appointment_id=appointment.id).one()
    assert (history.previous_status, history.new_status) == ("scheduled", "confirmed")

