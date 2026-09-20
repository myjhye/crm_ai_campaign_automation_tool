import {el, button, errorMessage} from '../../components/dom.js';
import {request} from '../../api/client.js';

const labels={WITHDRAWN:'탈퇴',NO_CONSENT:'수신 미동의',INVALID_CONTACT:'연락처 오류',EXCLUDED_SEGMENT:'제외 세그먼트',DUPLICATE_CAMPAIGN:'같은 캠페인 기수신',DAILY_LIMIT:'일일 한도',WEEKLY_LIMIT:'7일 한도'};

export function campaignReview({route,signal,getCampaign,onCampaign}) {
  const panel=el('section',{className:'card campaign-review-panel','aria-label':'정책 검수와 승인'});
  let state=null,busy=false;
  const referenceAt=()=>new Date(`${route.to}T23:59:59+09:00`).toISOString();
  async function call(path,body) {
    if (busy) return; busy=true; draw();
    try {await request(path,{method:'POST',body,signal}); await load();}
    catch(error) {state={...(state||{}),error:errorMessage(error)};}
    finally {busy=false; draw();}
  }
  function draw() {
    const campaign=getCampaign();
    if (!campaign) {panel.replaceChildren(el('h2',{text:'정책 검수·승인'}),el('p',{className:'small muted',text:'캠페인 초안을 저장하면 대상자 검수와 승인을 진행할 수 있습니다.'})); return;}
    const validation=state?.validation, approval=state?.approval;
    const status={DRAFT:'작성 중',REVIEW:'승인 검토 중',APPROVED:'승인 완료'}[campaign.status]||campaign.status;
    const children=[el('div',{className:'panel-heading'},el('h2',{text:'정책 검수·승인'}),el('span',{className:`badge status-${campaign.status.toLowerCase()}`,text:status}))];
    if (state?.error) children.push(el('p',{className:'error-text',text:state.error}));
    if (validation) {
      children.push(el('div',{className:'review-counts'},
        el('div',{},el('strong',{text:String(validation.initial_count)}),el('span',{text:'최초 대상'})),
        el('div',{},el('strong',{text:String(validation.excluded_count)}),el('span',{text:'제외'})),
        el('div',{},el('strong',{text:String(validation.eligible_count)}),el('span',{text:'승인 대상'}))));
      children.push(el('ul',{className:'review-rules'},...validation.rules.filter(row=>row.affected_count).map(row=>
        el('li',{},el('span',{text:labels[row.rule_code]||row.message}),el('strong',{text:`${row.affected_count}명`})))));
      for (const blocker of validation.blockers) children.push(el('p',{className:'review-blocker',text:blocker.message}));
      children.push(el('p',{className:'small muted',text:`검수 결과 ${validation.passed?'통과':'차단'} · 30분 동안 유효`}));
    }
    if (campaign.status==='DRAFT') {
      children.push(button('정책 검수 실행',()=>call(`/campaigns/${campaign.id}/validate`,{dataset_id:route.dataset,campaign_version:campaign.version,reference_at:referenceAt()}),signal));
      if (validation?.passed && validation.campaign_version===campaign.version) children.push(button('승인 요청',()=>call(`/campaigns/${campaign.id}/request-approval`,{dataset_id:route.dataset,campaign_version:campaign.version,validation_run_id:validation.id}),signal));
    } else if (campaign.status==='REVIEW' && approval?.status==='PENDING') {
      children.push(el('p',{text:'검수 내용을 확인한 뒤 승인하거나 반려해주세요.'}),
        el('div',{className:'row'},button('승인',()=>call(`/campaigns/${campaign.id}/approve`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id}),signal),
          button('반려',()=>call(`/campaigns/${campaign.id}/reject`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id,comment:'보완 후 다시 검토'}),signal)));
    } else if (campaign.status==='APPROVED') children.push(el('p',{className:'review-approved',text:'✓ 이 버전은 승인되었습니다.'}));
    if (['REVIEW','APPROVED'].includes(campaign.status)) children.push(button('편집 재개',()=>call(`/campaigns/${campaign.id}/resume-editing`,{dataset_id:route.dataset,campaign_version:campaign.version}),signal));
    panel.replaceChildren(...children); panel.querySelectorAll('button').forEach(node=>node.disabled=busy);
  }
  async function load() {
    const campaign=getCampaign(); if (!campaign) {state=null; draw(); return;}
    state=await request(`/campaigns/${campaign.id}/review?dataset_id=${route.dataset}`,{signal});
    if (!state?.campaign?.id) throw new Error('검수 상태 응답 형식이 올바르지 않습니다.');
    onCampaign(state.campaign); draw();
  }
  draw(); return {panel,load,draw};
}
