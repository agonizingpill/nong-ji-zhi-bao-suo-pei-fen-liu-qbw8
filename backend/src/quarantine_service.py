import json
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import Claim
from .quarantine_models import QuarantineMeta,SampleQuarantine,RiskScore,RiskScoreSample
from .claim_service import audit
DECIDED=('paid','denied')
def now():return datetime.now(timezone.utc).isoformat()
def lock_meta(s):
    meta=s.scalar(select(QuarantineMeta).where(QuarantineMeta.id==1).with_for_update())
    if not meta:
        meta=QuarantineMeta(id=1,epoch=0);s.add(meta);s.flush()
        meta=s.scalar(select(QuarantineMeta).where(QuarantineMeta.id==1).with_for_update())
    return meta
def sample_view(c,q=None):
    return {'id':c.id,'code':c.code,'part':c.part,'hours_at_failure':c.hours_at_failure,'age_days':c.age_days,'leak_flag':c.leak_flag,'disputed':c.disputed,'status':c.status,'quarantined':q is not None,'quarantine_reason':q.reason if q else None}
def quarantine_view(s,q):
    c=s.get(Claim,q.claim_id)
    return {'id':q.id,'claim_id':q.claim_id,'code':c.code if c else str(q.claim_id),'reason':q.reason,'actor':q.actor,'epoch':q.epoch,'created_at':q.created_at,'affected':json.loads(q.affected or '[]')}
def quarantine(s,data,u):
    meta=lock_meta(s)
    c=s.scalar(select(Claim).where(Claim.code==data.code))
    if not c:raise HTTPException(404,'历史样本不存在')
    if not c.historical:raise HTTPException(409,'仅已结案的历史样本可隔离')
    existing=s.scalar(select(SampleQuarantine).where(SampleQuarantine.claim_id==c.id))
    if existing:return quarantine_view(s,existing)|{'already':True}
    q=SampleQuarantine(claim_id=c.id,reason=data.reason,actor=u['email'],epoch=meta.epoch+1,created_at=now(),affected='[]')
    s.add(q);s.flush();meta.epoch+=1
    affected=[]
    referenced=select(RiskScoreSample.score_id).where(RiskScoreSample.sample_id==c.id)
    pairs=s.execute(select(RiskScore,Claim).join(Claim,Claim.id==RiskScore.claim_id).where(RiskScore.state=='valid',RiskScore.id.in_(referenced))).all()
    for score,claim in pairs:
        cur=s.scalar(select(Claim.status).where(Claim.id==claim.id).with_for_update())
        if cur in DECIDED:continue
        score.state='stale'
        claim.status='recall';claim.risk=None
        claim.assessment_note=f'评分引用的历史样本 {c.code} 被隔离，需重新分流计算后才能签赔'
        audit(s,u,'score_revoked',f'{claim.code} ← 隔离样本 {c.code}')
        affected.append(claim.code)
    traced=select(RiskScore.claim_id).where(RiskScore.state=='valid')
    for claim in s.scalars(select(Claim).where(Claim.status=='assessed',Claim.id.not_in(traced))).all():
        cur=s.scalar(select(Claim.status).where(Claim.id==claim.id).with_for_update())
        if cur!='assessed':continue
        claim.status='recall';claim.risk=None
        claim.assessment_note=f'旧评分缺少样本溯源，隔离 {c.code} 后须重新分流计算'
        audit(s,u,'score_revoked',f'{claim.code} ← 旧评分无法确认未引用 {c.code}')
        affected.append(claim.code)
    q.affected=json.dumps(affected,ensure_ascii=False)
    audit(s,u,'sample_quarantined',f'{c.code}：{data.reason}；撤回 {len(affected)} 条未裁决评分')
    s.flush()
    return quarantine_view(s,q)|{'already':False}
