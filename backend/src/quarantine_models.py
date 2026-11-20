from sqlalchemy import String,Integer,Float,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class QuarantineMeta(Base):
    __tablename__='quarantine_meta'
    id:Mapped[int]=mapped_column(primary_key=True)
    epoch:Mapped[int]=mapped_column(Integer,default=0)
class SampleQuarantine(Base):
    __tablename__='sample_quarantines'
    id:Mapped[int]=mapped_column(primary_key=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('claims.id'),unique=True)
    reason:Mapped[str]=mapped_column(Text)
    actor:Mapped[str]=mapped_column(String(120))
    affected:Mapped[str]=mapped_column(Text,default='[]')
    epoch:Mapped[int]=mapped_column(Integer)
    created_at:Mapped[str]=mapped_column(String(40))
class RiskScore(Base):
    __tablename__='risk_scores'
    id:Mapped[int]=mapped_column(primary_key=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('claims.id'),index=True)
    risk:Mapped[float]=mapped_column(Float)
    metrics:Mapped[str]=mapped_column(Text)
    state:Mapped[str]=mapped_column(String(20),default='valid')
    created_at:Mapped[str]=mapped_column(String(40))
class RiskScoreSample(Base):
    __tablename__='risk_score_samples'
    score_id:Mapped[int]=mapped_column(ForeignKey('risk_scores.id'),primary_key=True)
    sample_id:Mapped[int]=mapped_column(ForeignKey('claims.id'),primary_key=True)
