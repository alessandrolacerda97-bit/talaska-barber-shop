import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app import models
@pytest.fixture
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); s=sessionmaker(bind=engine)()
    yield s; s.close()
