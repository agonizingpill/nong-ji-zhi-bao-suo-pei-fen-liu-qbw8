from fastapi import APIRouter,Depends
from sqlalchemy import select
from .database import Session
from .security import current,allow
from .models import Claim
from .quarantine_models import SampleQuarantine
from .schemas import QuarantineIn
from . import quarantine_service as qs
router=APIRouter()
@router.get('/samples/history')
def history(u=Depends(current)):
    with Session() as s:
        qmap={q.claim_id:q for q in s.scalars(select(SampleQuarantine))}
        return [qs.sample_view(c,qmap.get(c.id)) for c in s.scalars(select(Claim).where(Claim.historical==True).order_by(Claim.id))]
@router.get('/samples/quarantines')
def quarantines(u=Depends(current)):
    with Session() as s:return [qs.quarantine_view(s,q) for q in s.scalars(select(SampleQuarantine).order_by(SampleQuarantine.id.desc()))]
@router.post('/samples/quarantines')
def create(d:QuarantineIn,u=Depends(current)):
    allow(u,'admin')
    with Session.begin() as s:return qs.quarantine(s,d,u)
