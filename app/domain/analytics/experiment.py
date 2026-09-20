import math
from statistics import NormalDist

Z95=NormalDist().inv_cdf(0.975)
Z80=NormalDist().inv_cdf(0.8)
# 포트폴리오 시연용: 실제 서비스에서는 사전 검정력 분석으로 MDE를 더 보수적으로 설정해야 함.
MINIMUM_DETECTABLE_RELATIVE_EFFECT=0.50
# 포트폴리오 시연용 최소 실행 표본. 이론상 검정력 표본도 응답에 별도로 보존한다.
DEMO_MINIMUM_SAMPLE_PER_VARIANT=30

def ratio(numerator,denominator):
    if not denominator:return {'status':'no_denominator','numerator':numerator,'denominator':denominator,'value':None}
    return {'status':'available','numerator':numerator,'denominator':denominator,'value':round(numerator/denominator*100,2)}

def wilson(successes,total):
    if not total:return None
    p=successes/total; denominator=1+Z95**2/total
    center=(p+Z95**2/(2*total))/denominator
    spread=Z95*math.sqrt(p*(1-p)/total+Z95**2/(4*total**2))/denominator
    return {'low':round(max(0,center-spread)*100,2),'high':round(min(1,center+spread)*100,2)}

def minimum_sample(baseline):
    p1=min(max(baseline,0.01),0.8);p2=min(p1*(1+MINIMUM_DETECTABLE_RELATIVE_EFFECT),0.95);pooled=(p1+p2)/2
    value=((Z95*math.sqrt(2*pooled*(1-pooled))+Z80*math.sqrt(p1*(1-p1)+p2*(1-p2)))**2)/(p2-p1)**2
    return max(100,math.ceil(value))

def compare(a_success,a_total,b_success,b_total,observation_complete,guardrail_worse=False):
    a_rate=a_success/a_total if a_total else None;b_rate=b_success/b_total if b_total else None
    baseline=a_rate if a_rate is not None else 0.05;power_sample=minimum_sample(baseline);required=DEMO_MINIMUM_SAMPLE_PER_VARIANT
    absolute=None if a_rate is None or b_rate is None else round((b_rate-a_rate)*100,2)
    relative=None if not a_rate or b_rate is None else round((b_rate-a_rate)/a_rate*100,2)
    p_value=None
    if a_total and b_total:
        pooled=(a_success+b_success)/(a_total+b_total);se=math.sqrt(pooled*(1-pooled)*(1/a_total+1/b_total))
        if se:p_value=round(2*(1-NormalDist().cdf(abs(b_rate-a_rate)/se)),4)
    reasons=[]
    if not observation_complete:reasons.append('OBSERVATION_OPEN')
    if min(a_total,b_total)<required:reasons.append('INSUFFICIENT_SAMPLE')
    if guardrail_worse:reasons.append('GUARDRAIL_WORSE')
    winner=None
    if not reasons and p_value is not None and p_value<0.05:winner='B' if b_rate>a_rate else 'A'
    if not reasons and winner is None:reasons.append('NO_SIGNIFICANT_DIFFERENCE')
    return {'status':'HOLD' if reasons else 'WINNER','winner':winner,'reasons':reasons,'minimum_sample_per_variant':required,
        'power_sample_per_variant':power_sample,'minimum_sample_basis':'portfolio_demo',
        'absolute_difference_pp':absolute,'relative_uplift_percent':relative,'p_value':p_value,
        'a_confidence_interval':wilson(a_success,a_total),'b_confidence_interval':wilson(b_success,b_total)}
