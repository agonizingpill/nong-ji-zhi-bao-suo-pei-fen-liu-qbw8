from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score,roc_auc_score
import numpy as np
from sqlalchemy import select,func
from .models import Claim,Machine
from .quarantine_models import SampleQuarantine

def assess(s,claim):
    history=s.scalars(select(Claim).where(Claim.historical==True,Claim.id.not_in(select(SampleQuarantine.claim_id)))).all()
    excluded=s.scalar(select(func.count()).select_from(SampleQuarantine))or 0
    if len(history)<40:raise ValueError(f'可用历史样本不足40条（已隔离{excluded}条错标样本），不能训练分流模型')
    def row(c):
        m=s.get(Machine,c.machine_id)
        return [m.model,c.part,c.hours_at_failure,c.age_days,int(c.leak_flag)]
    X=np.array([row(c) for c in history],dtype=object)
    y=np.array([c.disputed for c in history])
    a,b=train_test_split(np.arange(len(y)),test_size=.25,stratify=y,random_state=42)
    pre=ColumnTransformer([('category',OneHotEncoder(handle_unknown='ignore'),[0,1]),('numeric',StandardScaler(),[2,3,4])])
    model=make_pipeline(pre,LogisticRegression(max_iter=1000,random_state=42))
    model.fit(X[a],y[a]); p=model.predict_proba(X[b])[:,1]
    risk=float(model.predict_proba(np.array([row(claim)],dtype=object))[0,1])
    metrics={'training_rows':len(a),'holdout_rows':len(b),'accuracy':round(float(accuracy_score(y[b],p>=.5)),4),'roc_auc':round(float(roc_auc_score(y[b],p)),4),'seed':42,'high_risk_threshold':.5,'method':'OneHotEncoder + StandardScaler + LogisticRegression','excluded_quarantined':excluded,'coefficients':{str(k):round(float(v),4) for k,v in zip(model[0].get_feature_names_out(),model[1].coef_[0])}}
    return risk,metrics,[c.id for c in history]
