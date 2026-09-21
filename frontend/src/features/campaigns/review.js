import {el, button, errorMessage, formatTime} from '../../components/dom.js';
import {request} from '../../api/client.js';
import {apiPeriod} from '../../app/router.js';
import {campaignAnalysis} from './analysis.js';

const labels={WITHDRAWN:'탈퇴',NO_CONSENT:'채널 미동의',INVALID_CONTACT:'연락처 없음·오류',EXCLUDED_SEGMENT:'제외 세그먼트',DUPLICATE_CAMPAIGN:'기수신',DAILY_LIMIT:'일일 한도 초과',WEEKLY_LIMIT:'피로도 초과'};
const failureLabels={WITHDRAWN:'발송 시점 탈퇴',NO_CONSENT:'발송 시점 동의 철회',INVALID_CONTACT:'연락처 없음·오류',DUPLICATE_CAMPAIGN:'기수신',DAILY_LIMIT:'일일 한도 초과',WEEKLY_LIMIT:'피로도 초과',SYSTEM_ERROR:'시뮬레이터 전송 실패'};
const runLabels={PENDING:'대기 중',RUNNING:'처리 중',COMPLETED:'완료',FAILED:'실패'};
const number=value=>Number(value||0).toLocaleString('ko-KR');

export function campaignReview({route,signal,getCampaign,onCampaign,onRun=()=>{},getSegmentName=()=>''}) {
  const panel=el('section',{className:'card campaign-review-panel campaign-tab-panel','aria-label':'정책 검수와 승인'});
  const resultsPanel=el('section',{className:'campaign-results campaign-tab-panel','aria-label':'발송과 결과'});
  let state=null,busy=false,activeRun=null,performance=null,pollTimer=null,idempotencyKey=null;
  const analysisPanels=new Map();
  const aiPanel=el('section',{className:'campaign-tab-panel','aria-label':'AI 분석 탭'});
  const referenceAt=()=>new Date(`${route.to}T23:59:59+09:00`).toISOString();
  async function call(path,body) {
    if (busy) return; busy=true; draw();
    try {await request(path,{method:'POST',body,signal}); await load();}
    catch(error) {state={...(state||{}),error:errorMessage(error)};}
    finally {busy=false; draw();}
  }
  const stopPolling=()=>{if(pollTimer){clearTimeout(pollTimer);pollTimer=null;}};
  signal.addEventListener('abort',stopPolling,{once:true});
  async function loadRun(campaign) {
    try {
      activeRun=(await request(`/campaigns/${campaign.id}/runs?dataset_id=${route.dataset}`,{signal})).run;
      if(activeRun?.status==='COMPLETED'){
        const period=apiPeriod(route.from,route.to);const query=new URLSearchParams({dataset_id:route.dataset,from:period.from,to:period.to});
        performance=await request(`/campaigns/${campaign.id}/performance?${query}`,{signal});
      }else performance=null;
    }
    catch(error) {if(!signal.aborted) state={...(state||{}),error:errorMessage(error)};}
  }
  function schedulePoll() {
    stopPolling();
    if(!activeRun||!['PENDING','RUNNING'].includes(activeRun.status)||signal.aborted)return;
    pollTimer=setTimeout(async()=>{try{
      activeRun=await request(`/campaigns/${activeRun.campaign_id}/runs/${activeRun.id}?dataset_id=${route.dataset}`,{signal});
      if(['COMPLETED','FAILED'].includes(activeRun.status)){await load();await onRun(activeRun);}else{draw();schedulePoll();}
    }catch(error){if(!signal.aborted){state={...(state||{}),error:errorMessage(error)};draw();}}},1000);
  }
  async function simulate(campaign=getCampaign()) {
    if(!campaign||campaign.status!=='APPROVED'||busy)return false;
    busy=true; idempotencyKey=idempotencyKey||crypto.randomUUID(); draw();
    try {
      activeRun=await request(`/campaigns/${campaign.id}/simulate-send`,{method:'POST',signal,headers:{'Idempotency-Key':idempotencyKey},body:{dataset_id:route.dataset,campaign_version:campaign.version}});
      await load(); await onRun(activeRun); schedulePoll(); return true;
    } catch(error) {if(!signal.aborted)state={...(state||{}),error:errorMessage(error)};return false;}
    finally {busy=false;draw();}
  }
  const resumeEditing=(campaign=getCampaign())=>campaign&&['REVIEW','APPROVED'].includes(campaign.status)?call(`/campaigns/${campaign.id}/resume-editing`,{dataset_id:route.dataset,campaign_version:campaign.version}):Promise.resolve();

  function drawReview(campaign) {
    if (!campaign) {panel.replaceChildren(el('h2',{text:'정책 검수·승인'}),el('p',{className:'small muted',text:'캠페인 초안을 저장하면 대상자 검수와 승인을 진행할 수 있습니다.'})); return;}
    const validation=state?.validation,approval=state?.approval;
    const status={DRAFT:'작성 중',REVIEW:'승인 검토 중',APPROVED:'승인 완료',RUNNING:'발송 중',COMPLETED:'발송 완료'}[campaign.status]||campaign.status;
    const children=[el('div',{className:'panel-heading'},el('div',{},el('p',{className:'small muted',text:'CAMPAIGN REVIEW'}),el('h2',{text:'정책 검수·승인'})),el('span',{className:`badge status-${campaign.status.toLowerCase()}`,text:status}))];
    if(state?.error)children.push(el('p',{className:'error-text',text:state.error}));
    if(validation){
      const blockers=validation.blockers||[],expired=Date.parse(validation.expires_at)<=Date.now();
      if(blockers.length)children.push(el('div',{className:'review-blockers',role:'alert'},el('strong',{text:'캠페인 전체 차단'}),...blockers.map(row=>el('p',{text:row.message}))));
      children.push(el('div',{className:'review-overview-cards'},
        el('div',{},el('span',{text:'최초 대상'}),el('strong',{text:`${number(validation.initial_count)}명`})),
        el('div',{},el('span',{text:'제외'}),el('strong',{text:`${number(validation.excluded_count)}명`})),
        el('div',{className:validation.eligible_count?'is-pass':'is-blocked'},el('span',{text:'승인 대상'}),el('strong',{text:`${number(validation.eligible_count)}명`}))));
      children.push(el('div',{className:'review-detail'},el('h3',{text:'사유별 제외 내역'}),el('ul',{className:'review-reason-list'},...(validation.rules||[]).map(row=>{
        const count=row.primary_count??row.affected_count??0;return el('li',{className:count?'has-exclusions':''},el('span',{text:labels[row.rule_code]||row.message}),el('strong',{text:`${number(count)}명`}));
      }))));
      children.push(el('p',{className:`small ${expired&&campaign.status==='DRAFT'?'error-text':'muted'}`,text:expired&&campaign.status==='DRAFT'?'검수 결과가 만료되었습니다. 다시 실행해주세요.':`${formatTime(validation.expires_at)}까지 승인 요청에 사용할 수 있습니다.`}));
    }else if(campaign.status==='DRAFT')children.push(el('p',{className:'small muted',text:'아직 검수하지 않았습니다. 저장 후 검수를 실행해주세요.'}));
    const actions=el('div',{className:'row campaign-review-actions'});
    if(campaign.status==='DRAFT'){
      actions.append(button('정책 검수 실행',()=>call(`/campaigns/${campaign.id}/validate`,{dataset_id:route.dataset,campaign_version:campaign.version,reference_at:referenceAt()}),signal));
      if(validation){
        const expired=Date.parse(validation.expires_at)<=Date.now(),blockers=validation.blockers||[],reasons=[];
        if(!validation.passed)reasons.push('검수를 통과하지 못했습니다.');if(expired)reasons.push('검수 결과가 만료되었습니다.');if(blockers.length)reasons.push('캠페인 차단 사유를 먼저 해결해주세요.');if(validation.eligible_count<=0)reasons.push('승인 가능한 대상 고객이 없습니다.');if(validation.campaign_version!==campaign.version)reasons.push('캠페인이 변경되어 다시 검수해야 합니다.');
        const approvalButton=button('승인 요청',()=>call(`/campaigns/${campaign.id}/request-approval`,{dataset_id:route.dataset,campaign_version:campaign.version,validation_run_id:validation.id}),signal);approvalButton.disabled=!!reasons.length;approvalButton.dataset.validationDisabled=reasons.length?'true':'false';actions.append(approvalButton);
        if(reasons.length)children.push(el('p',{className:'small error-text review-disabled-reason',text:reasons.join(' ')}));
      }
    }else if(campaign.status==='REVIEW'&&approval?.status==='PENDING'){
      children.push(el('p',{text:'검수 내용을 확인한 뒤 승인하거나 반려해주세요.'}));actions.append(button('승인',()=>call(`/campaigns/${campaign.id}/approve`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id}),signal),button('반려',()=>call(`/campaigns/${campaign.id}/reject`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id,comment:'보완 후 다시 검토'}),signal,'button secondary'));
    }else if(campaign.status==='APPROVED')children.push(el('p',{className:'review-approved',text:'✓ 이 버전은 승인되었습니다. 발송·결과 탭에서 실행할 수 있습니다.'}));
    if(['REVIEW','APPROVED'].includes(campaign.status))actions.append(button('편집 재개',()=>resumeEditing(campaign),signal,'button secondary'));
    children.push(actions);panel.replaceChildren(...children);panel.querySelectorAll('button').forEach(node=>{node.disabled=busy||node.dataset.validationDisabled==='true';});
  }

  function metric(label,value,tone=''){return el('div',{className:`run-metric ${tone}`},el('span',{text:label}),el('strong',{text:`${number(value)}명`}));}
  function drawResults(campaign){
    let analysis=null;
    if(campaign?.status==='COMPLETED'){
      const key=`${campaign.id}:${campaign.version}`;
      if(!analysisPanels.has(key))analysisPanels.set(key,campaignAnalysis({route,signal,campaign}));
      analysis=analysisPanels.get(key);aiPanel.replaceChildren(analysis.panel);
    }else aiPanel.replaceChildren();
    if(!campaign){resultsPanel.replaceChildren(el('div',{className:'card'},el('h2',{text:'발송·결과'}),el('p',{className:'muted',text:'캠페인을 선택해주세요.'})));return;}
    const variants=campaign.variants||[],run=activeRun;
    const segmentName=getSegmentName(campaign.segment_revision_id)||'저장된 대상 세그먼트';
    const header=el('section',{className:'card run-header'},el('div',{},el('p',{className:'small muted',text:'SIMULATED DELIVERY'}),el('h2',{text:campaign.name}),el('p',{className:'small muted',text:`${campaign.channel} · 대상 ${segmentName} · A ${(variants[0]?.allocation_bp||0)/100}% / B ${(variants[1]?.allocation_bp||0)/100}%`})),el('span',{className:`badge status-${(run?.status||campaign.status).toLowerCase()}`,text:run?runLabels[run.status]||run.status:'발송 전'}));
    const children=[header];if(state?.error)children.push(el('p',{className:'card error-text',text:state.error}));
    if(campaign.status==='APPROVED'&&!run)header.append(button('모의 발송 실행',()=>simulate(campaign),signal));
    if(!run){children.push(el('section',{className:'card state'},el('h3',{text:campaign.status==='APPROVED'?'모의 발송을 시작할 수 있습니다.':'승인 후 발송할 수 있습니다.'}),el('p',{text:'승인된 대상 스냅샷을 기준으로 실행 직전 안전 조건을 다시 확인합니다.'})));resultsPanel.replaceChildren(...children);return;}
    children.push(el('section',{className:'run-metrics'},metric('예약',run.reserved_count),metric('실행 전 제외',run.excluded_count,run.excluded_count?'is-warning':''),metric('발송 성공',run.sent_count,'is-success'),metric('발송 실패',run.failed_count,run.failed_count?'is-danger':'')));
    const failures=Object.entries(run.failure_summary||{});
    children.push(el('section',{className:'card run-breakdown'},el('h3',{text:'실패·제외 사유'}),failures.length?el('table',{},el('thead',{},el('tr',{},el('th',{text:'사유'}),el('th',{text:'인원'}))),el('tbody',{},...failures.map(([reason,count])=>el('tr',{},el('td',{text:failureLabels[reason]||reason}),el('td',{text:`${number(count)}명`}))))):el('p',{className:'small muted',text:'실행 전 제외나 발송 실패가 없습니다.'})));
    children.push(el('div',{className:'run-result-grid'},el('section',{className:'card'},el('h3',{text:'A/B 발송 결과'}),...(run.variant_summary||[]).map(row=>el('div',{className:'run-summary-row'},el('strong',{text:`${row.variant_name}안`}),el('span',{text:`발송 ${number(row.sent)}명 · 실패 ${number(row.failed)}명`})))),el('section',{className:'card'},el('h3',{text:'이벤트 집계'}),...Object.entries({DELIVERED:'전달',OPEN:'오픈',CLICK:'클릭',CONVERSION:'전환',UNSUBSCRIBE:'수신거부'}).map(([key,label])=>el('div',{className:'run-summary-row'},el('span',{text:label}),el('strong',{text:`${number(run.event_summary?.[key])}명`}))))));
    if(performance){const totals=performance.totals,test=performance.experiment;children.push(el('section',{className:'card performance-summary'},el('div',{className:'panel-heading'},el('h3',{text:'성과와 A/B 판단'}),el('span',{className:`badge ${test.winner?'status-completed':'status-review'}`,text:test.winner?`${test.winner}안 우세`:'판단 보류'})),
      el('div',{className:'run-result-grid'},el('div',{},el('span',{className:'small muted',text:'클릭률'}),el('strong',{text:totals.click_rate.value==null?'—':`${totals.click_rate.value}%`})),el('div',{},el('span',{className:'small muted',text:'전환율'}),el('strong',{text:totals.conversion_rate.value==null?'—':`${totals.conversion_rate.value}%`})),el('div',{},el('span',{className:'small muted',text:'기여 매출'}),el('strong',{text:`${number(totals.revenue)}원`})),el('div',{},el('span',{className:'small muted',text:'B−A 전환 차이'}),el('strong',{text:test.absolute_difference_pp==null?'—':`${test.absolute_difference_pp}%p`}))),
      el('p',{className:'small muted',text:`7일 마지막 클릭 귀속 · ${performance.observation.complete?'관찰 완료':'관찰 진행 중'} · 증분 지표 제공 불가`})))}
    if(campaign.status==='COMPLETED'&&performance){
      children.find(child=>child.classList.contains('performance-summary')).append(analysis.entry);
    }
    resultsPanel.replaceChildren(...children);
    resultsPanel.querySelectorAll('button').forEach(node=>{if(!node.closest('.ai-performance'))node.disabled=busy;});
  }
  function draw(){const campaign=getCampaign();drawReview(campaign);drawResults(campaign);}
  async function load(){
    const campaign=getCampaign();if(!campaign){state=null;activeRun=null;draw();return;}
    state=await request(`/campaigns/${campaign.id}/review?dataset_id=${route.dataset}`,{signal});if(!state?.campaign?.id)throw new Error('검수 상태 응답 형식이 올바르지 않습니다.');onCampaign(state.campaign);
    if(['APPROVED','RUNNING','COMPLETED'].includes(state.campaign.status))await loadRun(state.campaign);else{activeRun=null;performance=null;}draw();schedulePoll();
  }
  draw();return {panel,resultsPanel,aiPanel,load,draw,simulate,resumeEditing};
}
