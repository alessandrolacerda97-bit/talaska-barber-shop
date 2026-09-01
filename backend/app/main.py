import csv
import io
import logging
import re
from time import monotonic
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .core.config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import (
    Appointment,
    AppointmentStatusHistory,
    Barber,
    BarberHour,
    BlockedTime,
    BusinessHour,
    Customer,
    Gallery,
    Service,
    Setting,
    User,
)
from .schemas import (
    AppointmentIn,
    AppointmentUpdate,
    BarberHourIn,
    BarberHoursReplaceIn,
    BlockedTimeIn,
    BlockedTimesReplaceIn,
    BusinessHourIn,
    BusinessHoursReplaceIn,
    EntityIn,
    GalleryIn,
    LoginIn,
    SettingsUpdateIn,
)
from .security import create_token, current_user, verify_password


logging.basicConfig(level=logging.INFO)
APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")
ACTIVE_APPOINTMENT_STATUSES = ("scheduled", "confirmed", "completed", "pending")
VALID_APPOINTMENT_STATUSES = ("scheduled", "confirmed", "completed", "cancelled", "no_show")
PUBLIC_CACHE_SECONDS = 300
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 5
login_attempts: dict[str, list[float]] = {}

app = FastAPI(title="Talaska Barber Shop API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def now_brt() -> datetime:
    """Return a naive datetime in the business timezone used in the database."""

    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def as_brt_naive(value: datetime) -> datetime:
    """Accept an ISO datetime with or without an offset and store São Paulo time."""

    if value.tzinfo is not None:
        return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)
    return value.replace(tzinfo=None)


def out(model):
    data = {column.name: getattr(model, column.name) for column in model.__table__.columns}
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = float(value)
        elif isinstance(value, (datetime, date, time)):
            data[key] = value.isoformat()
    return data


def appointment_out(appointment: Appointment, db: Session):
    data = out(appointment)
    customer = db.get(Customer, appointment.customer_id)
    barber = db.get(Barber, appointment.barber_id)
    service = db.get(Service, appointment.service_id)
    data["customer"] = out(customer) if customer else None
    data["barber"] = out(barber) if barber else None
    data["service"] = out(service) if service else None
    return data


def normalize_phone(value: str) -> str:
    phone = re.sub(r"\D", "", value)
    if not 10 <= len(phone) <= 15:
        raise HTTPException(422, "Informe um WhatsApp válido, com DDD.")
    return phone


def set_public_cache(response: Response) -> None:
    """Cache only anonymous, non-personal content for a short period."""

    response.headers["Cache-Control"] = f"public, max-age={PUBLIC_CACHE_SECONDS}, stale-while-revalidate=600"


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def login_is_limited(address: str) -> bool:
    now = monotonic()
    recent = [attempt for attempt in login_attempts.get(address, []) if now - attempt < LOGIN_WINDOW_SECONDS]
    login_attempts[address] = recent
    return len(recent) >= LOGIN_MAX_ATTEMPTS


def record_failed_login(address: str) -> None:
    login_attempts.setdefault(address, []).append(monotonic())


def service_price_is_valid(price: Decimal | int | float | None, price_on_request: bool, active: bool) -> None:
    amount = Decimal(str(price if price is not None else 0))
    if amount < 0:
        raise HTTPException(422, "O preço não pode ser negativo.")
    if active and amount <= 0 and not price_on_request:
        raise HTTPException(
            422,
            "Serviço ativo sem preço: marque 'Valor sob consulta' antes de publicar.",
        )


def register_status_change(
    db: Session,
    appointment: Appointment,
    previous: str | None,
    current: str,
    *,
    user: User | None = None,
    label: str = "Sistema",
) -> None:
    if previous == current:
        return
    db.add(
        AppointmentStatusHistory(
            appointment_id=appointment.id,
            previous_status=previous,
            new_status=current,
            changed_by_user_id=user.id if user else None,
            changed_by_label=user.email if user else label,
        )
    )


def lock_barbers(db: Session, barber_ids: list[int]) -> None:
    """Serialize writes per barber in PostgreSQL (including reschedules)."""

    if engine.dialect.name != "postgresql":
        return
    for barber_id in sorted(set(barber_ids)):
        db.execute(text("SELECT pg_advisory_xact_lock(:barber_id)"), {"barber_id": barber_id})


def conflict(
    db: Session,
    barber_id: int,
    start: datetime,
    end: datetime,
    ignore_appointment_id: int | None = None,
):
    """Return an overlapping appointment or block for one barber, if any."""

    appointment_query = db.query(Appointment).filter(
        Appointment.barber_id == barber_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_datetime < end,
        Appointment.end_datetime > start,
    )
    if ignore_appointment_id is not None:
        appointment_query = appointment_query.filter(Appointment.id != ignore_appointment_id)
    appointment = appointment_query.first()
    if appointment:
        return appointment
    return (
        db.query(BlockedTime)
        .filter(
            or_(BlockedTime.barber_id == barber_id, BlockedTime.barber_id.is_(None)),
            BlockedTime.start_datetime < end,
            BlockedTime.end_datetime > start,
        )
        .first()
    )


def appointment_conflicts_with_block(
    db: Session, barber_id: int | None, start: datetime, end: datetime
) -> Appointment | None:
    """Prevent an admin block from silently invalidating an existing booking."""

    query = db.query(Appointment).filter(
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_datetime < end,
        Appointment.end_datetime > start,
    )
    if barber_id is not None:
        query = query.filter(Appointment.barber_id == barber_id)
    return query.first()


def schedule_hours(db: Session, barber: Barber, weekday: int):
    """Use custom barber hours only when the barber deliberately enabled them."""

    if barber.custom_hours_enabled:
        return (
            db.query(BarberHour)
            .filter_by(barber_id=barber.id, weekday=weekday, active=True)
            .order_by(BarberHour.start_time)
            .all()
        )
    return (
        db.query(BusinessHour)
        .filter_by(weekday=weekday, active=True)
        .order_by(BusinessHour.start_time)
        .all()
    )


def working(db: Session, barber: Barber, start: datetime, end: datetime) -> bool:
    if start.date() != end.date():
        return False
    return any(
        start.time() >= hour.start_time and end.time() <= hour.end_time
        for hour in schedule_hours(db, barber, start.weekday())
    )


def is_slot_aligned(db: Session, barber: Barber, service: Service, start: datetime) -> bool:
    """A direct API request cannot invent an off-grid appointment time."""

    interval = get_settings().appointment_interval_minutes
    if start.second or start.microsecond:
        return False
    for hour in schedule_hours(db, barber, start.weekday()):
        cursor = datetime.combine(start.date(), hour.start_time)
        close = datetime.combine(start.date(), hour.end_time)
        while cursor + timedelta(minutes=service.duration_minutes) <= close:
            if cursor == start:
                return True
            cursor += timedelta(minutes=interval)
    return False


def make_slots(db: Session, barber: Barber, service: Service, chosen: date) -> list[str]:
    interval = get_settings().appointment_interval_minutes
    result: list[str] = []
    for hour in schedule_hours(db, barber, chosen.weekday()):
        cursor = datetime.combine(chosen, hour.start_time)
        close = datetime.combine(chosen, hour.end_time)
        while cursor + timedelta(minutes=service.duration_minutes) <= close:
            end = cursor + timedelta(minutes=service.duration_minutes)
            if cursor > now_brt() and not conflict(db, barber.id, cursor, end):
                result.append(cursor.strftime("%H:%M"))
            cursor += timedelta(minutes=interval)
    return result


def get_barber_or_404(db: Session, barber_id: int, *, active_only: bool = False) -> Barber:
    barber = db.get(Barber, barber_id)
    if not barber or (active_only and not barber.active):
        raise HTTPException(404, "Barbeiro não encontrado ou indisponível.")
    return barber


def get_service_or_404(db: Session, service_id: int, *, active_only: bool = False) -> Service:
    service = db.get(Service, service_id)
    if not service or (active_only and not service.active):
        raise HTTPException(404, "Serviço não encontrado ou indisponível.")
    return service


def ensure_non_overlapping_hours(hours: list[object], *, ignore_id: int | None = None) -> None:
    """Reject overlapping active intervals before database writes."""

    by_weekday: dict[int, list[object]] = {}
    for hour in hours:
        if not getattr(hour, "active", True) or getattr(hour, "id", None) == ignore_id:
            continue
        by_weekday.setdefault(hour.weekday, []).append(hour)
    for weekday, intervals in by_weekday.items():
        sorted_intervals = sorted(intervals, key=lambda item: item.start_time)
        for previous, current in zip(sorted_intervals, sorted_intervals[1:]):
            if current.start_time < previous.end_time:
                raise HTTPException(422, f"Há intervalos de horário sobrepostos na semana (dia {weekday}).")


def as_business_hour(item: BusinessHourIn) -> BusinessHour:
    return BusinessHour(
        weekday=item.weekday,
        start_time=item.start_time,
        end_time=item.end_time,
        active=item.active,
    )


def as_barber_hour(barber_id: int, item: BarberHourIn | BusinessHourIn) -> BarberHour:
    return BarberHour(
        barber_id=barber_id,
        weekday=item.weekday,
        start_time=item.start_time,
        end_time=item.end_time,
        active=item.active,
    )


def normalized_block(data: BlockedTimeIn) -> tuple[int | None, datetime, datetime, str | None]:
    start = as_brt_naive(data.start_datetime)
    end = as_brt_naive(data.end_datetime)
    if end <= start:
        raise HTTPException(422, "O fim do bloqueio deve ser posterior ao início.")
    return data.barber_id, start, end, data.reason.strip() if data.reason else None


@app.on_event("startup")
def setup() -> None:
    settings = get_settings()
    settings.validate_for_startup()
    # Production must run `alembic upgrade head` before Uvicorn. Keeping
    # create_all local-only avoids bypassing constraints/migrations on Neon.
    if not settings.is_production:
        Base.metadata.create_all(engine)
    from .seed import seed

    with SessionLocal() as db:
        seed(db)


@app.get("/health")
def health():
    return {"status": "ok", "timezone": "America/Sao_Paulo"}


@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    address = client_address(request)
    if login_is_limited(address):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente novamente.")
    user = db.query(User).filter(func.lower(User.email) == data.email.lower()).first()
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        record_failed_login(address)
        raise HTTPException(401, "E-mail ou senha incorretos.")
    login_attempts.pop(address, None)
    return {"access_token": create_token(user), "token_type": "bearer"}


@app.get("/api/services")
def services(response: Response, db: Session = Depends(get_db)):
    set_public_cache(response)
    return [
        out(item)
        for item in db.query(Service).filter_by(active=True).order_by(Service.display_order, Service.name)
    ]


@app.get("/api/barbers")
def barbers(response: Response, db: Session = Depends(get_db)):
    set_public_cache(response)
    return [
        out(item)
        for item in db.query(Barber).filter_by(active=True).order_by(Barber.display_order, Barber.name)
    ]


@app.get("/api/gallery")
def gallery(response: Response, db: Session = Depends(get_db)):
    set_public_cache(response)
    return [out(item) for item in db.query(Gallery).filter_by(active=True).order_by(Gallery.display_order, Gallery.id)]


@app.get("/api/settings")
def settings(response: Response, db: Session = Depends(get_db)):
    set_public_cache(response)
    return {item.key: item.value for item in db.query(Setting)}


@app.get("/api/availability")
def availability(
    service_id: int,
    appointment_date: date,
    barber_id: int | None = None,
    db: Session = Depends(get_db),
):
    if appointment_date < now_brt().date():
        raise HTTPException(400, "Não é possível agendar no passado.")
    service = get_service_or_404(db, service_id, active_only=True)
    if barber_id is not None:
        candidates = [get_barber_or_404(db, barber_id, active_only=True)]
    else:
        candidates = db.query(Barber).filter_by(active=True).order_by(Barber.name).all()
    return [{"barber": out(barber), "slots": make_slots(db, barber, service, appointment_date)} for barber in candidates]


@app.post("/api/appointments", status_code=201)
def book(data: AppointmentIn, db: Session = Depends(get_db)):
    service = get_service_or_404(db, data.service_id, active_only=True)
    start = datetime.combine(data.appointment_date, data.start_time)
    end = start + timedelta(minutes=service.duration_minutes)
    if start <= now_brt():
        raise HTTPException(400, "Escolha um horário futuro.")

    if data.barber_id is not None:
        candidates = [get_barber_or_404(db, data.barber_id, active_only=True)]
    else:
        candidates = db.query(Barber).filter_by(active=True).order_by(Barber.id).all()
    if not candidates:
        raise HTTPException(409, "Não há barbeiros disponíveis no momento.")

    # The same lock is also used when the admin reschedules an appointment.
    lock_barbers(db, [barber.id for barber in candidates])

    valid_candidates = [
        barber
        for barber in candidates
        if working(db, barber, start, end) and is_slot_aligned(db, barber, service, start)
    ]
    if not valid_candidates:
        raise HTTPException(400, "Este horário não faz parte da agenda disponível.")
    barber = next(
        (candidate for candidate in valid_candidates if not conflict(db, candidate.id, start, end)), None
    )
    if not barber:
        raise HTTPException(409, "Este horário acabou de ser reservado. Escolha outro horário.")

    customer_name = data.customer_name.strip()
    if len(customer_name) < 2:
        raise HTTPException(422, "Informe o nome completo do cliente.")
    phone = normalize_phone(data.customer_phone)
    customer = db.query(Customer).filter_by(phone=phone).first()
    if not customer:
        customer = Customer(name=customer_name, phone=phone, email=data.customer_email)
        db.add(customer)
        db.flush()
    else:
        customer.name = customer_name
        customer.email = data.customer_email or customer.email

    appointment = Appointment(
        customer_id=customer.id,
        barber_id=barber.id,
        service_id=service.id,
        appointment_date=data.appointment_date,
        start_datetime=start,
        end_datetime=end,
        price=service.price,
        notes=data.notes.strip() if data.notes else None,
    )
    try:
        db.add(appointment)
        db.flush()
        register_status_change(db, appointment, None, appointment.status, label="Sistema")
        db.commit()
        db.refresh(appointment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este horário acabou de ser reservado. Escolha outro horário.")
    return appointment_out(appointment, db)


@app.get("/api/appointments/public/{token}")
def public_appointment(token: str, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter_by(public_token=token).first()
    if not appointment:
        raise HTTPException(404, "Agendamento não encontrado.")
    return appointment_out(appointment, db)


@app.post("/api/appointments/public/{token}/cancel")
def cancel(token: str, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter_by(public_token=token).first()
    if not appointment:
        raise HTTPException(404, "Agendamento não encontrado.")
    if appointment.status in ("cancelled", "completed", "no_show"):
        raise HTTPException(400, "Este agendamento não pode ser cancelado.")
    if appointment.start_datetime - now_brt() < timedelta(hours=get_settings().cancellation_hours):
        raise HTTPException(400, "O prazo para cancelamento já expirou.")
    previous_status = appointment.status
    appointment.status = "cancelled"
    register_status_change(db, appointment, previous_status, appointment.status, label="Cliente")
    db.commit()
    return {"message": "Agendamento cancelado com sucesso."}


@app.get("/api/admin/dashboard", dependencies=[Depends(current_user)])
def dashboard(
    start: date | None = None,
    end: date | None = None,
    barber_id: int | None = None,
    service_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    today = now_brt().date()
    week_end = today + timedelta(days=7)
    month_start = today.replace(day=1)
    base = db.query(Appointment)
    if start:
        base = base.filter(Appointment.appointment_date >= start)
    if end:
        base = base.filter(Appointment.appointment_date <= end)
    if barber_id:
        base = base.filter(Appointment.barber_id == barber_id)
    if service_id:
        base = base.filter(Appointment.service_id == service_id)
    if status:
        if status not in VALID_APPOINTMENT_STATUSES:
            raise HTTPException(422, "Status inválido.")
        base = base.filter(Appointment.status == status)
    completed = base.filter_by(status="completed")

    def count(query):
        return query.count()

    def money(query):
        return float(query.with_entities(func.coalesce(func.sum(Appointment.price), 0)).scalar())

    top_services = (
        completed.join(Service, Appointment.service_id == Service.id)
        .with_entities(Service.name, func.count(Appointment.id).label("appointments"))
        .group_by(Service.id, Service.name)
        .order_by(func.count(Appointment.id).desc(), Service.name)
        .limit(5)
        .all()
    )
    barber_rows = (
        completed.join(Barber, Appointment.barber_id == Barber.id)
        .with_entities(
            Barber.id,
            Barber.name,
            Barber.commission_percentage,
            func.count(Appointment.id).label("appointments"),
            func.coalesce(func.sum(Appointment.price), 0).label("revenue"),
        )
        .group_by(Barber.id, Barber.name, Barber.commission_percentage)
        .order_by(func.coalesce(func.sum(Appointment.price), 0).desc(), Barber.name)
        .all()
    )
    performance = [
        {
            "barber_id": row.id,
            "name": row.name,
            "appointments": row.appointments,
            "revenue": float(row.revenue),
            "commission_percentage": float(row.commission_percentage or 0),
            "estimated_commission": float(row.revenue) * float(row.commission_percentage or 0) / 100,
        }
        for row in barber_rows
    ]
    return {
        "appointments_today": count(base.filter(Appointment.appointment_date == today)),
        "appointments_tomorrow": count(
            base.filter(Appointment.appointment_date == today + timedelta(days=1))
        ),
        "appointments_week": count(base.filter(Appointment.appointment_date.between(today, week_end))),
        "appointments_month": count(base.filter(Appointment.appointment_date >= month_start)),
        "revenue_today": money(completed.filter(Appointment.appointment_date == today)),
        "revenue_week": money(completed.filter(Appointment.appointment_date.between(today, week_end))),
        "revenue_month": money(completed.filter(Appointment.appointment_date >= month_start)),
        "ticket_average": float(
            completed.with_entities(func.coalesce(func.avg(Appointment.price), 0)).scalar()
        ),
        "customers": db.query(Customer).count(),
        "cancellations": count(base.filter_by(status="cancelled")),
        "no_shows": count(base.filter_by(status="no_show")),
        "completed": count(completed),
        "top_services": [{"name": row.name, "appointments": row.appointments} for row in top_services],
        "barber_performance": performance,
    }


@app.get("/api/admin/appointments", dependencies=[Depends(current_user)])
def admin_appointments(
    start: date | None = None,
    end: date | None = None,
    barber_id: int | None = None,
    service_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment).order_by(Appointment.start_datetime.desc())
    if start:
        query = query.filter(Appointment.appointment_date >= start)
    if end:
        query = query.filter(Appointment.appointment_date <= end)
    if barber_id:
        query = query.filter(Appointment.barber_id == barber_id)
    if service_id:
        query = query.filter(Appointment.service_id == service_id)
    if status:
        if status not in VALID_APPOINTMENT_STATUSES:
            raise HTTPException(422, "Status inválido.")
        query = query.filter(Appointment.status == status)
    return [appointment_out(appointment, db) for appointment in query]


@app.get("/api/admin/appointments/export", dependencies=[Depends(current_user)])
def export_appointments_csv(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    rows = db.query(Appointment).order_by(Appointment.start_datetime.desc())
    if start:
        rows = rows.filter(Appointment.appointment_date >= start)
    if end:
        rows = rows.filter(Appointment.appointment_date <= end)
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(["Data", "Horário", "Cliente", "WhatsApp", "Serviço", "Profissional", "Status", "Valor"])
    for appointment in rows.all():
        item = appointment_out(appointment, db)
        writer.writerow(
            [
                appointment.appointment_date.isoformat(),
                appointment.start_datetime.strftime("%H:%M"),
                item["customer"]["name"] if item["customer"] else "",
                item["customer"]["phone"] if item["customer"] else "",
                item["service"]["name"] if item["service"] else "",
                item["barber"]["name"] if item["barber"] else "",
                appointment.status,
                f"{appointment.price:.2f}",
            ]
        )
    return StreamingResponse(
        iter(["\ufeff" + stream.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=agenda-talaska.csv"},
    )


@app.put("/api/admin/appointments/{appointment_id}", dependencies=[Depends(current_user)])
def update_appointment(
    appointment_id: int,
    data: AppointmentUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(404, "Agendamento não encontrado.")
    if data.status is not None and data.status not in VALID_APPOINTMENT_STATUSES:
        raise HTTPException(400, "Status inválido.")

    new_barber = (
        get_barber_or_404(db, data.barber_id, active_only=True)
        if data.barber_id is not None
        else db.get(Barber, appointment.barber_id)
    )
    new_service = (
        get_service_or_404(db, data.service_id, active_only=True)
        if data.service_id is not None
        else db.get(Service, appointment.service_id)
    )
    if not new_barber or not new_service:
        raise HTTPException(409, "O barbeiro ou serviço atual não está mais disponível.")
    new_start = as_brt_naive(data.start_datetime) if data.start_datetime is not None else appointment.start_datetime
    new_end = new_start + timedelta(minutes=new_service.duration_minutes)
    new_status = data.status if data.status is not None else appointment.status
    schedule_changed = any(
        field in data.model_fields_set for field in ("barber_id", "service_id", "start_datetime")
    )
    reactivating = appointment.status in {"cancelled", "no_show"} and new_status in ACTIVE_APPOINTMENT_STATUSES

    if (schedule_changed or reactivating) and new_status in ACTIVE_APPOINTMENT_STATUSES:
        if new_start <= now_brt():
            raise HTTPException(400, "O novo horário precisa estar no futuro.")
        if not working(db, new_barber, new_start, new_end) or not is_slot_aligned(
            db, new_barber, new_service, new_start
        ):
            raise HTTPException(400, "O novo horário não faz parte da agenda disponível.")
        # Lock both barbers in a stable order before checking the target slot.
        lock_barbers(db, [appointment.barber_id, new_barber.id])
        if conflict(db, new_barber.id, new_start, new_end, appointment.id):
            raise HTTPException(409, "O novo horário está em conflito.")

    appointment.barber_id = new_barber.id
    appointment.service_id = new_service.id
    appointment.start_datetime = new_start
    appointment.end_datetime = new_end
    appointment.appointment_date = new_start.date()
    if data.service_id is not None:
        appointment.price = new_service.price
    previous_status = appointment.status
    if data.status is not None:
        appointment.status = data.status
    if "notes" in data.model_fields_set:
        appointment.notes = data.notes.strip() if data.notes else None
    try:
        register_status_change(db, appointment, previous_status, appointment.status, user=user)
        db.commit()
        db.refresh(appointment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "O novo horário está em conflito.")
    return appointment_out(appointment, db)


@app.get("/api/admin/appointments/{appointment_id}/history", dependencies=[Depends(current_user)])
def appointment_history(appointment_id: int, db: Session = Depends(get_db)):
    if not db.get(Appointment, appointment_id):
        raise HTTPException(404, "Agendamento não encontrado.")
    return [
        out(item)
        for item in db.query(AppointmentStatusHistory)
        .filter_by(appointment_id=appointment_id)
        .order_by(AppointmentStatusHistory.changed_at.desc())
        .all()
    ]


@app.get("/api/admin/customers", dependencies=[Depends(current_user)])
def customers(q: str = "", db: Session = Depends(get_db)):
    rows = (
        db.query(Customer)
        .filter(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
        .order_by(Customer.name)
        .all()
    )
    return [
        {
            **out(customer),
            "visits": db.query(Appointment)
            .filter_by(customer_id=customer.id, status="completed")
            .count(),
            "total_spent": float(
                db.query(func.coalesce(func.sum(Appointment.price), 0))
                .filter_by(customer_id=customer.id, status="completed")
                .scalar()
            ),
        }
        for customer in rows
    ]


# --- Administrative availability management ---------------------------------


@app.get("/api/admin/business-hours", dependencies=[Depends(current_user)])
def list_business_hours(db: Session = Depends(get_db)):
    return [
        out(hour)
        for hour in db.query(BusinessHour).order_by(BusinessHour.weekday, BusinessHour.start_time).all()
    ]


@app.post("/api/admin/business-hours", dependencies=[Depends(current_user)], status_code=201)
def create_business_hour(data: BusinessHourIn, db: Session = Depends(get_db)):
    candidate = as_business_hour(data)
    existing = db.query(BusinessHour).all()
    ensure_non_overlapping_hours([*existing, candidate])
    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este intervalo já existe.")
    return out(candidate)


@app.put("/api/admin/business-hours", dependencies=[Depends(current_user)])
def replace_business_hours(data: BusinessHoursReplaceIn, db: Session = Depends(get_db)):
    candidates = [as_business_hour(hour) for hour in data.hours]
    ensure_non_overlapping_hours(candidates)
    db.query(BusinessHour).delete(synchronize_session=False)
    db.add_all(candidates)
    db.commit()
    return [
        out(hour)
        for hour in db.query(BusinessHour).order_by(BusinessHour.weekday, BusinessHour.start_time).all()
    ]


@app.put("/api/admin/business-hours/{hour_id}", dependencies=[Depends(current_user)])
def update_business_hour(hour_id: int, data: BusinessHourIn, db: Session = Depends(get_db)):
    hour = db.get(BusinessHour, hour_id)
    if not hour:
        raise HTTPException(404, "Horário de funcionamento não encontrado.")
    candidate = as_business_hour(data)
    candidate.id = hour.id
    ensure_non_overlapping_hours([*db.query(BusinessHour).all(), candidate], ignore_id=hour.id)
    hour.weekday = data.weekday
    hour.start_time = data.start_time
    hour.end_time = data.end_time
    hour.active = data.active
    try:
        db.commit()
        db.refresh(hour)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este intervalo já existe.")
    return out(hour)


@app.delete("/api/admin/business-hours/{hour_id}", dependencies=[Depends(current_user)])
def delete_business_hour(hour_id: int, db: Session = Depends(get_db)):
    hour = db.get(BusinessHour, hour_id)
    if not hour:
        raise HTTPException(404, "Horário de funcionamento não encontrado.")
    db.delete(hour)
    db.commit()
    return {"message": "Horário de funcionamento removido."}


@app.get("/api/admin/barber-hours", dependencies=[Depends(current_user)])
def list_barber_hours(barber_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(BarberHour)
    if barber_id is not None:
        get_barber_or_404(db, barber_id)
        query = query.filter_by(barber_id=barber_id)
    return [out(hour) for hour in query.order_by(BarberHour.barber_id, BarberHour.weekday, BarberHour.start_time)]


@app.post("/api/admin/barber-hours", dependencies=[Depends(current_user)], status_code=201)
def create_barber_hour(data: BarberHourIn, db: Session = Depends(get_db)):
    barber = get_barber_or_404(db, data.barber_id)
    candidate = as_barber_hour(barber.id, data)
    existing = db.query(BarberHour).filter_by(barber_id=barber.id).all()
    ensure_non_overlapping_hours([*existing, candidate])
    try:
        barber.custom_hours_enabled = True
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este intervalo já existe para o barbeiro.")
    return out(candidate)


@app.put("/api/admin/barber-hours", dependencies=[Depends(current_user)])
def replace_barber_hours(data: BarberHoursReplaceIn, db: Session = Depends(get_db)):
    barber = get_barber_or_404(db, data.barber_id)
    candidates = [as_barber_hour(barber.id, hour) for hour in data.hours]
    ensure_non_overlapping_hours(candidates)
    db.query(BarberHour).filter_by(barber_id=barber.id).delete(synchronize_session=False)
    barber.custom_hours_enabled = True
    db.add_all(candidates)
    db.commit()
    return [
        out(hour)
        for hour in db.query(BarberHour)
        .filter_by(barber_id=barber.id)
        .order_by(BarberHour.weekday, BarberHour.start_time)
        .all()
    ]


@app.put("/api/admin/barber-hours/{hour_id}", dependencies=[Depends(current_user)])
def update_barber_hour(hour_id: int, data: BarberHourIn, db: Session = Depends(get_db)):
    hour = db.get(BarberHour, hour_id)
    if not hour:
        raise HTTPException(404, "Horário do barbeiro não encontrado.")
    barber = get_barber_or_404(db, data.barber_id)
    candidate = as_barber_hour(barber.id, data)
    candidate.id = hour.id
    existing = db.query(BarberHour).filter_by(barber_id=barber.id).all()
    ensure_non_overlapping_hours([*existing, candidate], ignore_id=hour.id)
    hour.barber_id = barber.id
    hour.weekday = data.weekday
    hour.start_time = data.start_time
    hour.end_time = data.end_time
    hour.active = data.active
    barber.custom_hours_enabled = True
    try:
        db.commit()
        db.refresh(hour)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este intervalo já existe para o barbeiro.")
    return out(hour)


@app.post("/api/admin/barber-hours/{barber_id}/use-business-hours", dependencies=[Depends(current_user)])
def reset_barber_hours_to_business(barber_id: int, db: Session = Depends(get_db)):
    barber = get_barber_or_404(db, barber_id)
    db.query(BarberHour).filter_by(barber_id=barber.id).delete(synchronize_session=False)
    barber.custom_hours_enabled = False
    db.commit()
    return {"message": "O barbeiro voltou a usar os horários gerais da barbearia."}


@app.delete("/api/admin/barber-hours/{hour_id}", dependencies=[Depends(current_user)])
def delete_barber_hour(hour_id: int, db: Session = Depends(get_db)):
    hour = db.get(BarberHour, hour_id)
    if not hour:
        raise HTTPException(404, "Horário do barbeiro não encontrado.")
    db.delete(hour)
    db.commit()
    return {"message": "Horário do barbeiro removido."}


@app.get("/api/admin/blocked-times", dependencies=[Depends(current_user)])
def list_blocked_times(
    barber_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(BlockedTime)
    if barber_id is not None:
        get_barber_or_404(db, barber_id)
        query = query.filter(or_(BlockedTime.barber_id == barber_id, BlockedTime.barber_id.is_(None)))
    if start is not None:
        query = query.filter(BlockedTime.end_datetime > as_brt_naive(start))
    if end is not None:
        query = query.filter(BlockedTime.start_datetime < as_brt_naive(end))
    return [out(block) for block in query.order_by(BlockedTime.start_datetime).all()]


@app.post("/api/admin/blocked-times", dependencies=[Depends(current_user)], status_code=201)
def create_blocked_time(data: BlockedTimeIn, db: Session = Depends(get_db)):
    barber_id, start, end, reason = normalized_block(data)
    if barber_id is not None:
        get_barber_or_404(db, barber_id)
    existing_appointment = appointment_conflicts_with_block(db, barber_id, start, end)
    if existing_appointment:
        raise HTTPException(
            409,
            "Há um agendamento ativo nesse período. Reagende ou cancele-o antes de bloquear o horário.",
        )
    block = BlockedTime(barber_id=barber_id, start_datetime=start, end_datetime=end, reason=reason)
    db.add(block)
    db.commit()
    db.refresh(block)
    return out(block)


@app.put("/api/admin/blocked-times", dependencies=[Depends(current_user)])
def replace_blocked_times(data: BlockedTimesReplaceIn, db: Session = Depends(get_db)):
    candidates: list[BlockedTime] = []
    for item in data.blocked_times:
        barber_id, start, end, reason = normalized_block(item)
        if barber_id is not None:
            get_barber_or_404(db, barber_id)
        if appointment_conflicts_with_block(db, barber_id, start, end):
            raise HTTPException(
                409,
                "Há um agendamento ativo em um dos períodos informados. Nenhum bloqueio foi alterado.",
            )
        candidates.append(
            BlockedTime(barber_id=barber_id, start_datetime=start, end_datetime=end, reason=reason)
        )
    db.query(BlockedTime).delete(synchronize_session=False)
    db.add_all(candidates)
    db.commit()
    return [out(block) for block in db.query(BlockedTime).order_by(BlockedTime.start_datetime).all()]


@app.put("/api/admin/blocked-times/{block_id}", dependencies=[Depends(current_user)])
def update_blocked_time(block_id: int, data: BlockedTimeIn, db: Session = Depends(get_db)):
    block = db.get(BlockedTime, block_id)
    if not block:
        raise HTTPException(404, "Bloqueio não encontrado.")
    barber_id, start, end, reason = normalized_block(data)
    if barber_id is not None:
        get_barber_or_404(db, barber_id)
    existing_appointment = appointment_conflicts_with_block(db, barber_id, start, end)
    if existing_appointment:
        raise HTTPException(
            409,
            "Há um agendamento ativo nesse período. Reagende ou cancele-o antes de bloquear o horário.",
        )
    block.barber_id = barber_id
    block.start_datetime = start
    block.end_datetime = end
    block.reason = reason
    db.commit()
    db.refresh(block)
    return out(block)


@app.delete("/api/admin/blocked-times/{block_id}", dependencies=[Depends(current_user)])
def delete_blocked_time(block_id: int, db: Session = Depends(get_db)):
    block = db.get(BlockedTime, block_id)
    if not block:
        raise HTTPException(404, "Bloqueio não encontrado.")
    db.delete(block)
    db.commit()
    return {"message": "Bloqueio removido."}


# --- Site settings and gallery -----------------------------------------------


@app.get("/api/admin/settings", dependencies=[Depends(current_user)])
def admin_settings(db: Session = Depends(get_db)):
    return {item.key: item.value for item in db.query(Setting)}


@app.put("/api/admin/settings", dependencies=[Depends(current_user)])
def update_settings(data: SettingsUpdateIn, db: Session = Depends(get_db)):
    allowed = set(data.model_fields)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key not in allowed or value is None:
            continue
        normalized = value.strip()
        if key == "instagram" and normalized and not re.match(r"^https://(www\.)?instagram\.com/", normalized, re.I):
            raise HTTPException(422, "Informe uma URL válida do Instagram iniciando com https://.")
        if key == "whatsapp" and normalized:
            normalize_phone(normalized)
        setting = db.get(Setting, key)
        if setting:
            setting.value = normalized
        else:
            db.add(Setting(key=key, value=normalized))
    db.commit()
    return {item.key: item.value for item in db.query(Setting)}


@app.get("/api/admin/gallery", dependencies=[Depends(current_user)])
def admin_gallery(db: Session = Depends(get_db)):
    return [out(item) for item in db.query(Gallery).order_by(Gallery.display_order, Gallery.id)]


@app.post("/api/admin/gallery", dependencies=[Depends(current_user)], status_code=201)
def create_gallery_item(data: GalleryIn, db: Session = Depends(get_db)):
    item = Gallery(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return out(item)


@app.put("/api/admin/gallery/{item_id}", dependencies=[Depends(current_user)])
def update_gallery_item(item_id: int, data: GalleryIn, db: Session = Depends(get_db)):
    item = db.get(Gallery, item_id)
    if not item:
        raise HTTPException(404, "Imagem não encontrada.")
    for key, value in data.model_dump().items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(item)
    return out(item)


@app.delete("/api/admin/gallery/{item_id}", dependencies=[Depends(current_user)])
def delete_gallery_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Gallery, item_id)
    if not item:
        raise HTTPException(404, "Imagem não encontrada.")
    db.delete(item)
    db.commit()
    return {"message": "Imagem removida da galeria."}


# --- Other administrative records -------------------------------------------


@app.get("/api/admin/{kind}", dependencies=[Depends(current_user)])
def list_entities(kind: str, db: Session = Depends(get_db)):
    model = {"barbers": Barber, "services": Service}.get(kind)
    if not model:
        raise HTTPException(404, "Recurso não encontrado.")
    order_columns = (Barber.display_order, Barber.name) if kind == "barbers" else (Service.display_order, Service.name)
    return [out(item) for item in db.query(model).order_by(*order_columns).all()]


@app.post("/api/admin/{kind}", dependencies=[Depends(current_user)], status_code=201)
def create_entity(kind: str, data: EntityIn, db: Session = Depends(get_db)):
    model = {"barbers": Barber, "services": Service}.get(kind)
    if not model:
        raise HTTPException(404, "Recurso não encontrado.")
    if not data.name:
        raise HTTPException(422, "O nome é obrigatório.")
    if kind == "services" and data.duration_minutes is None:
        raise HTTPException(422, "A duração do serviço é obrigatória.")
    allowed = {column.name for column in model.__table__.columns}
    values = {
        key: value
        for key, value in data.model_dump(exclude_none=True).items()
        if key in allowed
    }
    if kind == "services":
        service_price_is_valid(
            values.get("price", 0),
            bool(values.get("price_on_request", False)),
            bool(values.get("active", True)),
        )
    item = model(**values)
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um registro com esse nome.")
    return out(item)


@app.put("/api/admin/{kind}/{item_id}", dependencies=[Depends(current_user)])
def edit_entity(kind: str, item_id: int, data: EntityIn, db: Session = Depends(get_db)):
    model = {"barbers": Barber, "services": Service}.get(kind)
    item = db.get(model, item_id) if model else None
    if not item:
        raise HTTPException(404, "Registro não encontrado.")
    if kind == "services":
        requested = data.model_dump(exclude_unset=True)
        service_price_is_valid(
            requested.get("price", item.price),
            bool(requested.get("price_on_request", item.price_on_request)),
            bool(requested.get("active", item.active)),
        )
    protected_fields = {"id", "created_at", "duration_minutes"} if kind == "barbers" else {"id", "created_at"}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in protected_fields or not hasattr(item, key):
            continue
        # Non-null columns are never cleared through an omitted/null field.
        if value is None and key in {"name", "duration_minutes", "price"}:
            continue
        setattr(item, key, value)
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um registro com esse nome.")
    return out(item)

