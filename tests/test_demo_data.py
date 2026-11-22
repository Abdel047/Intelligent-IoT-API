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

def test_vindmoelle_pilot_resume_and_events():
    from scripts.seed_demo_data import vindmoelle_samples
    from datetime import timedelta
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    end=datetime(2026,11,22,12,tzinfo=timezone.utc)
    data=list(vindmoelle_samples(end))
    assert len(data)==150
    assert all(end-timedelta(days=7)<at<=end for _,_,at in data)
    assert sum(speed>25 for _,speed,_ in data)==6
    assert all(8<=speed<=24 or 26<=speed<=35 for _,speed,_ in data)
    with Session(engine) as session, session.begin():
        session.add(Reading(device_id='VINDMOELLE-01',wind_speed=20,anomaly_detected=False))
        assert seed(session,end,'vindmoelle',4)==(4,1)
    with Session(engine) as session, session.begin():
        # Resume on another day still uses the original timestamps and batch.
        assert seed(session,end+timedelta(days=1),'vindmoelle')==(146,5)
    with Session(engine) as session, session.begin():
        assert seed(session,end+timedelta(days=2),'vindmoelle')==(0,0)
        assert session.scalar(select(func.count()).select_from(Reading))==151
        assert session.scalar(select(func.count()).select_from(DomainEvent))==162
        assert session.scalar(select(func.count()).select_from(Alarm))==6
        for row in session.scalars(select(Reading).where(Reading.id>1)):
            events=list(session.scalars(select(DomainEvent).where(DomainEvent.reading_id==row.id).order_by(DomainEvent.id)))
            assert [e.event_type for e in events]==(['SensorValueReceived','AnomalyDetected','AlarmCreated'] if row.wind_speed>25 else ['SensorValueReceived'])
            assert all(e.created_at==row.created_at and e.device_id==row.device_id for e in events)
            if row.wind_speed>25:
                alarm=session.get(Alarm,events[-1].alarm_id)
                assert alarm.reading_id==row.id and alarm.created_at==row.created_at
