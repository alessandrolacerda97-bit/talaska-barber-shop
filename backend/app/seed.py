from datetime import time
from sqlalchemy.orm import Session
from .models import Barber,Service,BusinessHour,Setting,User
from .security import hash_password
from .core.config import get_settings
def seed(db:Session):
    if not db.query(User).first(): db.add(User(email=get_settings().admin_email,password_hash=hash_password(get_settings().admin_initial_password)))
    if not db.query(Barber).first(): db.add_all([Barber(name="Wilian",bio="Especialista em cortes modernos."),Barber(name="Moisés",bio="Precisão e atendimento personalizado."),Barber(name="Herick",bio="Estilo clássico e contemporâneo.")])
    if not db.query(Service).first(): db.add_all([Service(name="Corte",description="Corte premium personalizado.",price=0,duration_minutes=45,display_order=1),Service(name="Barba",description="Barba impecável e bem cuidada.",price=0,duration_minutes=30,display_order=2),Service(name="Combo Corte + Barba",description="Experiência completa Talaska.",price=0,duration_minutes=60,display_order=3)])
    if not db.query(BusinessHour).first(): db.add_all([BusinessHour(weekday=d,start_time=time(9),end_time=time(12)) for d in range(1,6)]+[BusinessHour(weekday=d,start_time=time(13),end_time=time(19)) for d in range(1,6)])
    defaults={"business_name":"Talaska Barber Shop","whatsapp":"5551981201434","address":"Avenida Santa Rita, 627 - Centro","instagram":"","about":"A Talaska Barber Shop é um espaço criado para quem valoriza estilo, cuidado e atendimento de qualidade. Mais do que um corte, buscamos proporcionar uma experiência completa para nossos clientes."}
    for k,v in defaults.items():
        if not db.get(Setting,k):db.add(Setting(key=k,value=v))
    db.commit()
