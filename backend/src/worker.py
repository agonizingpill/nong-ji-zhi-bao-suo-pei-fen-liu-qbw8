import json,time,os
from pathlib import Path
from redis import Redis
from sqlalchemy import select
from .database import Session
from .models import Claim,Machine
from .risk_model import assess
from .quarantine_models import RiskScore,RiskScoreSample,SampleQuarantine
from .quarantine_service import lock_meta,now
def process(s,cid):
    c=s.get(Claim,cid)
    if not c or c.status!='queued':return None
    m=s.get(Machine,c.machine_id)
    if c.hours_at_failure>m.warranty_hours:c.status='out_of_warranty';c.assessment_note='超出质保工时';return None
    risk,metrics,sample_ids=assess(s,c)
    lock_meta(s)
    conflict=s.scalars(select(SampleQuarantine.claim_id).where(SampleQuarantine.claim_id.in_(sample_ids)).with_for_update()).all()
    if conflict:
        c.assessment_note=f'训练快照含 {len(conflict)} 条已隔离样本，本次评分未生效，重新排队计算'
        return 'requeue'
    score=RiskScore(claim_id=c.id,risk=risk,metrics=json.dumps(metrics,ensure_ascii=False),state='valid',created_at=now())
    s.add(score);s.flush()
    s.add_all([RiskScoreSample(score_id=score.id,sample_id=sid)for sid in sample_ids])
    for old in s.scalars(select(RiskScore).where(RiskScore.claim_id==c.id,RiskScore.state=='valid',RiskScore.id!=score.id)):old.state='superseded'
    c.risk=risk;c.status='assessed';c.assessment_note=json.dumps(metrics,ensure_ascii=False)
    return metrics
def run(r):
    while True:
        Path('/artifacts/worker-heartbeat').write_text(str(time.time()))
        item=r.blpop('claim-risk',timeout=2)
        if not item:continue
        cid=int(item[1]);requeue=False
        try:
            with Session.begin() as s:
                result=process(s,cid)
                requeue=result=='requeue'
                if isinstance(result,dict):Path(f'/artifacts/claim-{cid}-model.json').write_text(json.dumps(result))
        except Exception as e:
            with Session.begin() as s:
                c=s.get(Claim,cid)
                if c:c.status='failed';c.assessment_note=str(e)
        if requeue:r.rpush('claim-risk',cid)
if __name__=='__main__':run(Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True))
