import {el, button, errorMessage, formatTime} from '../../components/dom.js';
import {request} from '../../api/client.js';

const labels={WITHDRAWN:'탈퇴',NO_CONSENT:'채널 미동의',INVALID_CONTACT:'연락처 없음·오류',EXCLUDED_SEGMENT:'제외 세그먼트',DUPLICATE_CAMPAIGN:'기수신',DAILY_LIMIT:'일일 한도 초과',WEEKLY_LIMIT:'피로도 초과'};

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
      const blockers=validation.blockers||[], expired=Date.parse(validation.expires_at)<=Date.now();
      if (blockers.length) children.push(el('div',{className:'review-blockers',role:'alert'},
        el('strong',{text:'캠페인 전체 차단'}),...blockers.map(row=>el('p',{text:row.message}))));
      children.push(el('div',{className:'review-summary'},
        el('div',{className:'review-total'},el('span',{text:'최초 대상'}),el('strong',{text:`${validation.initial_count.toLocaleString('ko-KR')}명`})),
        el('ul',{className:'review-reason-list'},...(validation.rules||[]).map(row=>{
          const count=row.primary_count??row.affected_count??0;
          return el('li',{className:count?'has-exclusions':''},el('span',{text:labels[row.rule_code]||row.message}),
            el('strong',{text:`${count.toLocaleString('ko-KR')}명`}));
        })),
        el('div',{className:`review-eligible ${validation.eligible_count?'is-pass':'is-blocked'}`},
          el('span',{text:'승인 대상'}),el('strong',{text:`${validation.eligible_count.toLocaleString('ko-KR')}명${validation.eligible_count?' ✓':''}`}))));
      children.push(el('p',{className:`small ${expired?'error-text':'muted'}`,text:expired?'검수 결과가 만료되었습니다. 다시 실행해주세요.':`${formatTime(validation.expires_at)}까지 유효`}));
    } else if (campaign.status==='DRAFT') {
      children.push(el('p',{className:'small muted',text:'아직 검수하지 않았습니다. 저장 후 검수를 실행해주세요.'}));
    }
    if (campaign.status==='DRAFT') {
      children.push(button('정책 검수 실행',()=>call(`/campaigns/${campaign.id}/validate`,{dataset_id:route.dataset,campaign_version:campaign.version,reference_at:referenceAt()}),signal));
      if (validation) {
        const expired=Date.parse(validation.expires_at)<=Date.now(), blockers=validation.blockers||[];
        const reasons=[];
        if (!validation.passed) reasons.push('검수를 통과하지 못했습니다.');
        if (expired) reasons.push('검수 결과가 만료되었습니다.');
        if (blockers.length) reasons.push('캠페인 차단 사유를 먼저 해결해주세요.');
        if (validation.eligible_count<=0) reasons.push('승인 가능한 대상 고객이 없습니다.');
        if (validation.campaign_version!==campaign.version) reasons.push('캠페인이 변경되어 다시 검수해야 합니다.');
        const canRequest=!reasons.length;
        const approvalButton=button('승인 요청',()=>call(`/campaigns/${campaign.id}/request-approval`,{dataset_id:route.dataset,campaign_version:campaign.version,validation_run_id:validation.id}),signal);
        approvalButton.disabled=!canRequest; approvalButton.dataset.validationDisabled=canRequest?'false':'true';
        children.push(approvalButton);
        if (!canRequest) children.push(el('p',{className:'small error-text review-disabled-reason',text:reasons.join(' ')}));
      }
    } else if (campaign.status==='REVIEW' && approval?.status==='PENDING') {
      children.push(el('p',{text:'검수 내용을 확인한 뒤 승인하거나 반려해주세요.'}),
        el('div',{className:'row'},button('승인',()=>call(`/campaigns/${campaign.id}/approve`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id}),signal),
          button('반려',()=>call(`/campaigns/${campaign.id}/reject`,{dataset_id:route.dataset,campaign_version:campaign.version,approval_id:approval.id,comment:'보완 후 다시 검토'}),signal)));
    } else if (campaign.status==='APPROVED') children.push(el('p',{className:'review-approved',text:'✓ 이 버전은 승인되었습니다.'}));
    if (['REVIEW','APPROVED'].includes(campaign.status)) children.push(button('편집 재개',()=>call(`/campaigns/${campaign.id}/resume-editing`,{dataset_id:route.dataset,campaign_version:campaign.version}),signal));
    panel.replaceChildren(...children); panel.querySelectorAll('button').forEach(node=>{node.disabled=busy||node.dataset.validationDisabled==='true';});
  }
  async function load() {
    const campaign=getCampaign(); if (!campaign) {state=null; draw(); return;}
    state=await request(`/campaigns/${campaign.id}/review?dataset_id=${route.dataset}`,{signal});
    if (!state?.campaign?.id) throw new Error('검수 상태 응답 형식이 올바르지 않습니다.');
    onCampaign(state.campaign); draw();
  }
  draw(); return {panel,load,draw};
}
