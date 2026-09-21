import {request} from '../../api/client.js';
import {apiPeriod,navigate} from '../../app/router.js';
import {el,button,heading,stateCard} from '../../components/dom.js';
import {campaignAnalysis} from '../campaigns/analysis.js';

const holdLabels={OBSERVATION_OPEN:'관찰 기간 진행 중',INSUFFICIENT_SAMPLE:'표본 부족',GUARDRAIL_WORSE:'수신거부율 악화',REVENUE_SIGNIFICANCE_NOT_AVAILABLE:'매출 주지표 판정 미지원'};
const kpiLabels={click_rate:'클릭률',conversion_rate:'전환율',revenue:'기여 매출'};
const pendingReasons=new Set(['OBSERVATION_OPEN','INSUFFICIENT_SAMPLE','REVENUE_SIGNIFICANCE_NOT_AVAILABLE']);

function campaignName(value){
  const parts=value.split(' · ').map(part=>part.trim()).filter(Boolean);
  return parts.length>1&&parts.every(part=>part===parts[0])?parts[0]:value;
}
function metricFor(test,item){return test.primary_kpi==='click_rate'?item.click_rate:item.conversion_rate;}
function countFor(test,item){return test.primary_kpi==='click_rate'?item.click_customers:item.conversion_customers;}
function percent(value){return value==null?'—':`${Number(value).toFixed(2)}%`;}
function verdict(test,a,b){
  const kpi=kpiLabels[test.primary_kpi]||'주요 지표';

  if(test.winner){
    const loser=test.winner==='A'?'B':'A';
    return {kind:'winner',badge:`${test.winner}안 우세`,description:`${test.winner}안이 ${loser}안보다 ${kpi} ${Math.abs(test.absolute_difference_pp).toFixed(2)}%p 높습니다 · 95% 유의수준 기준 유의`};
  }
  if(test.reasons?.includes('NO_SIGNIFICANT_DIFFERENCE')) {
    const av=metricFor(test,a)?.value,bv=metricFor(test,b)?.value;
    const leader=av!=null&&bv!=null&&av!==bv?(av>bv?'A':'B'):null;
    return {kind:'uncertain',badge:'승자 확정 불가',description:`${leader?`${leader}안이 수치상 우세하지만 (A ${percent(av)} vs B ${percent(bv)})`:'두 안의 관측 비율이 같습니다'}, 통계적으로 유의한 차이는 확인되지 않았습니다.`,recommendation:leader?`권장: 표본을 늘려 재검증하세요. 지금 선택해야 한다면 ${leader}안을 잠정 사용하되 추가 실험을 계속하세요.`:'권장: 비용과 운영 편의에 따라 선택하고 표본을 늘려 재검증하세요.'};
  }
  if(test.reasons?.includes('GUARDRAIL_WORSE')&&!test.reasons.some(reason=>pendingReasons.has(reason))) return {kind:'guardrail',badge:'안전 지표 악화',description:'수신거부율 가드레일이 악화되어 우세안을 선택하지 않았습니다.'};
  const reasons=(test.reasons||[]).filter(reason=>reason!=='NO_SIGNIFICANT_DIFFERENCE').map(code=>holdLabels[code]||code);
  return {kind:'pending',badge:'판단 보류',description:reasons.join(' · ')||'판정에 필요한 조건을 확인해주세요.',recommendation:test.reasons?.includes('REVENUE_SIGNIFICANCE_NOT_AVAILABLE')?'권장: 클릭률 또는 전환율 실험을 함께 확인하세요.':test.reasons?.includes('OBSERVATION_OPEN')?'권장: 관찰 기간이 끝난 뒤 다시 확인하세요.':'권장: 대상 고객을 늘려 추가 실험을 진행하세요.'};
}

export async function renderExperiments(root,route,signal){
  const period=apiPeriod(route.from,route.to);const query=new URLSearchParams({dataset_id:route.dataset,from:period.from,to:period.to,page_size:'100'});
  const rows=await request(`/reports/campaigns?${query}`,{signal});
  const selected=route.resource?rows.items.find(row=>row.campaign.id===route.resource):rows.items[0];
  const analysisTab=route.tab==='ai-analysis';
  const analyses=new Map(rows.items.filter(row=>row.campaign.status==='COMPLETED').map(row=>[row.campaign.id,campaignAnalysis({route,signal,campaign:row.campaign,view:'experiments',experiment:row.experiment})]));
  const cards=rows.items.map(row=>{
    const variants=Object.fromEntries(row.variants.map(item=>[item.name,item]));const a=variants.A||{},b=variants.B||{},test=row.experiment;
    const result=verdict(test,a,b);
    const revenue=test.primary_kpi==='revenue';
    const valueOf=item=>revenue?Number(item.revenue):metricFor(test,item)?.value;
    const maximum=Math.max(0,...[a,b].map(item=>Number(valueOf(item))||0));
    // Shared fixed percentage ticks, never normalize the larger arm to 100%.
    const scale=revenue?Math.max(1,maximum):([5,10,20,50,100].find(limit=>maximum<=limit)||100);
    const leader=valueOf(a)!=null&&valueOf(b)!=null&&valueOf(a)!==valueOf(b)?(valueOf(a)>valueOf(b)?'A':'B'):null;
    const interval=ci=>ci?`${ci.low}% ~ ${ci.high}%`:'해당 없음';
    const variant=(name,item)=>{
      const value=valueOf(item),count=countFor(test,item);
      const width=value==null?0:Math.min(100,Math.max(0,Number(value))/scale*100);
      return el('div',{className:'experiment-variant'},el('strong',{text:`${name}안`}),
        el('strong',{className:'experiment-rate',text:revenue?(Number.isFinite(value)?`${value.toLocaleString('ko-KR')}원`:'—'):percent(value)}),
        el('div',{className:'experiment-bar-track','aria-hidden':'true'},el('span',{className:`experiment-bar${leader===name?' is-leader':''}`,style:`width:${width}%`})),
        el('div',{className:'experiment-axis','aria-hidden':'true'},el('span',{text:revenue?'0원':'0%'}),el('span',{text:revenue?`${scale.toLocaleString('ko-KR')}원`:`${scale}%`})),
        el('span',{className:'small muted',text:`${revenue?'':`${test.primary_kpi==='click_rate'?'클릭':'전환'} ${count??0}명 / `}발송 ${item.delivered_customers??0}명`}));
    };
    const difference=test.absolute_difference_pp;
    return el('article',{className:'card experiment-card'},
      el('header',{className:'experiment-header'},el('h2',{text:campaignName(row.campaign.name)}),
        el('div',{className:'experiment-meta',text:`${row.campaign.channel} · ${kpiLabels[test.primary_kpi]||test.primary_kpi} 목표`})),
      el('div',{className:`experiment-conclusion is-${result.kind}`},el('h3',{text:`결론: ${result.badge}`}),el('p',{text:result.description}),result.recommendation?el('p',{className:'experiment-recommendation',text:result.recommendation}):null),
      el('div',{className:'experiment-variants'},variant('A',a),variant('B',b)),

      el('section',{className:'experiment-method','aria-label':'통계 상세'},el('h3',{className:'small muted',text:'통계 상세'}),
        el('div',{className:'experiment-details'},
          el('table',{'aria-label':'실험 통계 상세'},
            el('thead',{},el('tr',{},el('th',{scope:'col',text:'통계 지표'}),el('th',{scope:'col',text:'값'}))),
            el('tbody',{},...[
              ['p-value',revenue?'해당 없음':test.p_value??'계산할 수 없음'],
              ['A안 95% CI',interval(revenue?null:test.a_confidence_interval)],
              ['B안 95% CI',interval(revenue?null:test.b_confidence_interval)],
              ['표본 (A / B)',`${a.delivered_customers??0} / ${b.delivered_customers??0}명`],
              ['필요 표본 (안별)',`약 ${(test.power_sample_per_variant??test.minimum_sample_per_variant).toLocaleString('ko-KR')}명`],
              ['B−A 차이',revenue?'해당 없음':`${difference??'—'}%p · 상대 ${test.relative_uplift_percent??'—'}%`],
            ].map(([label,value])=>el('tr',{},el('th',{scope:'row',text:label}),el('td',{text:value}))))),
          el('p',{text:`필요 표본은 상대 MDE 50%·검정력 80% 가정의 추정치입니다. 시연 판정 하한은 안별 ${test.minimum_sample_per_variant}명입니다.`}),
          el('p',{text:'이 실험은 두 발송안의 비교입니다. 무발송 대비 효과는 포함되지 않습니다.'}))),
      button('캠페인 결과 열기',()=>navigate({view:'campaigns',resource:row.campaign.id,tab:'results'}),signal,'button secondary'),
      analyses.get(row.campaign.id)?.entry);

  });
  const tabs=el('nav',{className:'campaign-tabs','aria-label':'실험 화면'});
  for(const [id,label] of [['results','실험 결과'],['ai-analysis','AI 분석']]){
    const control=button(label,()=>navigate({view:'experiments',resource:selected?.campaign.id||'',tab:id}),signal,'button campaign-tab');
    control.setAttribute('aria-current',(analysisTab?id==='ai-analysis':id==='results')?'page':'false');
    if(id==='ai-analysis')control.disabled=!selected||!analyses.has(selected.campaign.id);
    tabs.append(control);
  }
  const content=el('div');
  if(analysisTab){
    const selection=el('select',{'aria-label':'분석할 실험 캠페인'},el('option',{value:'',text:'캠페인을 선택해주세요'}),
      ...rows.items.filter(row=>analyses.has(row.campaign.id)).map(row=>el('option',{value:row.campaign.id,text:campaignName(row.campaign.name)})));
    selection.value=selected?.campaign.id||'';
    selection.addEventListener('change',()=>{if(selection.value)navigate({resource:selection.value,tab:'ai-analysis'});},{signal});
    content.append(el('label',{className:'experiment-analysis-select'},el('span',{text:'분석할 캠페인'}),selection),
      selected&&analyses.has(selected.campaign.id)?analyses.get(selected.campaign.id).panel:stateCard('분석할 캠페인을 선택해주세요','선택 기간의 완료된 실험을 선택하면 성과를 분석할 수 있습니다.'));
  }else content.append(cards.length?el('div',{className:'experiment-list'},...cards):stateCard('완료된 실험이 없습니다','캠페인 모의 발송을 완료하면 A/B 결과를 비교할 수 있습니다.'));
  root.replaceChildren(heading('Experiments','A/B 주요 지표 차이와 판단 가능한 범위를 확인합니다.'),tabs,content);
}
