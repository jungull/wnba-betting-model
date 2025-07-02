from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, Boolean, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from .config import Config

Base = declarative_base()

class Odds(Base):
    __tablename__ = 'odds'
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, nullable=False)
    sport = Column(String, nullable=False, default='basketball_wnba')
    commence_time = Column(DateTime, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    bookmaker = Column(String, nullable=False)
    market_key = Column(String, nullable=False)
    price_home = Column(Float)
    point_home = Column(Float)
    price_away = Column(Float)
    point_away = Column(Float)
    last_update = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    source = Column(String, nullable=False)
    data_quality_score = Column(Float, default=1.0)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (
        UniqueConstraint('game_id', 'bookmaker', 'market_key'),
        CheckConstraint("source IN ('api', 'scrape')"),
    )

class TeamMapping(Base):
    __tablename__ = 'team_mappings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, nullable=False, unique=True)
    standard_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())

class APIUsage(Base):
    __tablename__ = 'api_usage'
    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String, nullable=False)
    requests_made = Column(Integer, nullable=False)
    requests_remaining = Column(Integer)
    reset_time = Column(DateTime)
    recorded_at = Column(DateTime, server_default=func.current_timestamp())

class DataQualityLog(Base):
    __tablename__ = 'data_quality_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    issue_type = Column(String, nullable=False)
    issue_description = Column(Text)
    affected_records = Column(Integer, default=1)
    severity = Column(String)
    created_at = Column(DateTime, server_default=func.current_timestamp())


def get_engine():
    return create_engine(Config.DATABASE_URL, echo=False, future=True)

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    print('Database initialized.') 