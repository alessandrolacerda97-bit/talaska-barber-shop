from datetime import datetime, timedelta
from app.main import conflict
from app.models import Appointment, Barber, Customer, Service
def test_overlap_is_detected(db):
    b=Barber(name="Teste"); s=Service(name="Teste",price=0,duration_minutes=30); c=Customer(name="Cliente",phone="51999999999")
    db.add_all([b,s,c]);db.commit(); start=datetime.now()+timedelta(days=2)
    db.add(Appointment(customer_id=c.id,barber_id=b.id,service_id=s.id,appointment_date=start.date(),start_datetime=start,end_datetime=start+timedelta(minutes=30),price=0));db.commit()
    assert conflict(db,b.id,start+timedelta(minutes=15),start+timedelta(minutes=45))
    assert not conflict(db,b.id,start+timedelta(minutes=30),start+timedelta(minutes=60))
