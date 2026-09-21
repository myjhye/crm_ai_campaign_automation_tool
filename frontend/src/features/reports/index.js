import {request} from '../../api/client.js';
import {apiPeriod,navigate} from '../../app/router.js';
import {el,button,heading,stateCard} from '../../components/dom.js';
import {performanceAssistant} from '../ai/performance.js';

const number=value=>Number(value||0).toLocaleString('ko-KR');
export async function renderReports(root,route,signal){
  const period=apiPeriod(route.from,route.to);const query=new URLSearchParams({dataset_id:route.dataset,from:period.from,to:period.to});
  const [summary,campaigns]=await Promise.all([request(`/reports/summary?${query}`,{signal}),request(`/reports/campaigns?${query}`,{signal})]);
  const cards=el('div',{className:'report-kpis'},
    ...[['완료 캠페인',`${number(summary.campaign_count)}개`],['전달 고객',`${number(summary.delivered_customers)}명`],['전환 고객',`${number(summary.conversion_customers)}명`],['기여 매출',`${number(summary.attributed_revenue)}원`]].map(([label,value])=>el('div',{className:'card'},el('span',{text:label}),el('strong',{text:value}))));
  const exportLink=el('a',{className:'button secondary',href:`/api/v1/reports/export?${query}`,download:'growthpilot-report.csv',text:'CSV 다운로드'});
  const analysisArea=el('div');
  const openAnalysis=row=>{analysisArea.replaceChildren(el('h2',{text:row.campaign.name}),performanceAssistant({route,signal,campaignId:row.campaign.id}));analysisArea.scrollIntoView({block:'start',behavior:'smooth'});};
  const table=campaigns.items.length?el('div',{className:'card report-table'},el('table',{},
    el('thead',{},el('tr',{},...['캠페인','채널','전달','클릭률','전환율','기여 매출','실험','분석'].map(text=>el('th',{text})))),
    el('tbody',{},...campaigns.items.map(row=>el('tr',{},el('td',{},button(row.campaign.name,()=>navigate({view:'campaigns',resource:row.campaign.id,tab:'results'}),signal,'chart-label')),
      el('td',{text:row.campaign.channel}),el('td',{text:`${number(row.totals.delivered_customers)}명`}),el('td',{text:row.totals.click_rate.value==null?'—':`${row.totals.click_rate.value}%`}),
      el('td',{text:row.totals.conversion_rate.value==null?'—':`${row.totals.conversion_rate.value}%`}),el('td',{text:`${number(row.totals.revenue)}원`}),el('td',{text:row.experiment.winner?`${row.experiment.winner}안 우세`:'판단 보류'}),el('td',{},button('분석 열기',()=>openAnalysis(row),signal,'button secondary'))))))):
    stateCard('집계할 완료 캠페인이 없습니다','선택 기간에 모의 발송을 완료한 캠페인이 생기면 여기에 표시됩니다.');
  root.replaceChildren(heading('Reports','캠페인 성과와 기여 매출을 같은 계산 기준으로 확인합니다.',exportLink),
    el('p',{className:'notice',text:`${route.from} ~ ${route.to} 발송 cohort · 마지막 클릭 7일 귀속 · ${summary.contains_simulated_data?'모의 데이터 포함':'모의 데이터 없음'}`}),cards,table,
    el('p',{className:'small muted',text:'무발송 통제군이 없어 증분 전환율과 증분 매출은 제공하지 않습니다.'}),
    analysisArea);
}
