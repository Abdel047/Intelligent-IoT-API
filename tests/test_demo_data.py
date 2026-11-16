from datetime import datetime, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from database import Base, Reading, DomainEvent, Alarm
from scripts.seed_demo_data import seed, samples

def test_seed_atomic_and_repeatable():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    end=datetime(2026,11,16,12,tzinfo=timezone.utc)
    with Session(engine) as session, session.begin():
        session.add(Reading(device_id='EXISTING',wind_speed=20,anomaly_detected=False))
        count, alarms=seed(session,end)
        assert count==579 and alarms>0
    with Session(engine) as session, session.begin():
        assert seed(session,end)==(0,0)
        assert session.scalar(select(func.count()).select_from(Reading))==580
        assert session.scalar(select(func.count()).select_from(DomainEvent))==579+2*alarms
        assert session.scalar(select(func.count()).select_from(Alarm))==alarms
        assert session.scalar(select(Reading).where(Reading.device_id=='EXISTING')).wind_speed==20
        assert all(r.anomaly_detected==(r.wind_speed>25) for r in session.scalars(select(Reading)))
    rows=list(samples(end))
    assert len(rows)==579 and rows[0][2]<rows[-1][2]==end
    assert (rows[-1][2]-rows[0][2]).total_seconds()==48*3600
