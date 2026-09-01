from datetime import time

from sqlalchemy.orm import Session

from .core.config import get_settings
from .models import Barber, BusinessHour, Service, Setting, User
from .security import hash_password


def seed(db: Session):
    if not db.query(User).first():
        db.add(
            User(
                email=get_settings().admin_email,
                password_hash=hash_password(get_settings().admin_initial_password),
            )
        )
    if not db.query(Barber).first():
        db.add_all(
            [
                Barber(name="Wilian", bio="Especialista em cortes modernos.", display_order=1),
                Barber(name="Moisés", bio="Precisão e atendimento personalizado.", display_order=2),
                Barber(name="Herick", bio="Estilo clássico e contemporâneo.", display_order=3),
            ]
        )
    if not db.query(Service).first():
        # No price was supplied. Make the services consultation-only rather
        # than publishing an inaccurate R$ 0,00.
        db.add_all(
            [
                Service(name="Corte", description="Corte premium personalizado.", price=0, price_on_request=True, duration_minutes=45, display_order=1),
                Service(name="Barba", description="Barba impecável e bem cuidada.", price=0, price_on_request=True, duration_minutes=30, display_order=2),
                Service(name="Combo Corte + Barba", description="Experiência completa Talaska.", price=0, price_on_request=True, duration_minutes=60, display_order=3),
            ]
        )
    if not db.query(BusinessHour).first():
        db.add_all(
            [BusinessHour(weekday=day, start_time=time(9), end_time=time(12)) for day in range(1, 6)]
            + [BusinessHour(weekday=day, start_time=time(13), end_time=time(19)) for day in range(1, 6)]
        )

    defaults = {
        "business_name": "Talaska Barber Shop",
        "whatsapp": "5551981201434",
        "address": "Avenida Santa Rita, 627 - Centro",
        "instagram": "https://www.instagram.com/talaskabarbershop/",
        "about": "A Talaska Barber Shop é um espaço criado para quem valoriza estilo, cuidado e atendimento de qualidade. Mais do que um corte, buscamos proporcionar uma experiência completa para nossos clientes.",
        "hero_desktop_position": "72% center",
        "hero_mobile_position": "64% center",
    }
    for key, value in defaults.items():
        if not db.get(Setting, key):
            db.add(Setting(key=key, value=value))
    db.commit()

