import {el,button,formatTime} from '../../components/dom.js';
import {routeHash} from '../../app/router.js';
import {renderPreview} from '../segments/preview.js';
import {comparison} from './comparison.js';
const labels={total_customers:'전체 고객',active_customers:'활성 고객',new_customers:'신규 고객',dormant_customers:'휴면 고객',purchase_conversion_rate:'구매 전환율',repeat_purchase_rate:'재구매율'};
export function messageNode(message,{route,signal,confirm,fill,isBusy}){
  const bubble=el('article',{className:`ai-message ai-message-${message.role}${message.saved?' ai-message-saved':''}`},el('span',{className:'sr-only',text:message.role==='user'?'나의 메시지':message.role==='system'?'시스템 안내':'AI 응답'}));
  if(!message.response){bubble.append(el('p',{text:message.content,role:message.error?'alert':null}));return bubble;}
  const response=message.response,data=response.data;
  const card=el('section',{className:'ai-result'},el('p',{text:response.message}));
  if(response.result_type==='metric')for(const [key,metric] of Object.entries(data.metrics))card.append(el('h3',{text:labels[key]||key}),el('strong',{className:'ai-metric-value',text:metric.value==null?'집계할 데이터가 없습니다':`${Number(metric.value).toLocaleString('ko-KR')}${metric.unit==='percent'?'%':'명'}`}));
  if(response.result_type==='segment_preview'){if(data.name)card.append(el('h3',{text:data.name}));card.append(renderPreview(data));}
  if(response.result_type==='campaign_comparison')card.append(comparison(data,route));
  if(response.result_type==='campaign_draft'){
    const draft=data.draft||data.payload||data;
    card.append(el('h3',{text:draft.name}),el('p',{text:`${draft.channel} · ${draft.benefit} · 전환율 목표 ${draft.target_value}% · A/B 50:50`}),el('p',{className:'small muted',text:'목표·말투·배분은 제안 기본값입니다. 저장 후 Campaigns에서 편집할 수 있습니다.'}),
      el('div',{className:'ai-draft-variants'},...(draft.variants||[]).map(v=>el('section',{},el('h4',{text:`${v.variant_name}안`}),el('strong',{text:v.subject||'SMS'}),el('p',{text:v.body}),el('p',{className:'small muted',text:`가설: ${v.hypothesis}`})))));
  }
  if(data.proposal_id){
    const segment=response.result_type==='segment_preview';
    const apply=button(message.saved?'저장 완료':segment?'확인 후 세그먼트 저장':'확인 후 캠페인 저장',()=>confirm(message),signal,'button');apply.disabled=!!message.saved||!!message.saving||isBusy();
    card.append(el('p',{className:'small muted',text:`제안 만료: ${formatTime(data.expires_at)}`}),apply,el('p',{role:'status',className:message.error?'error-text':'small',text:message.saving?'저장 중…':message.notice||''}));
    if(message.saved){card.append(button(segment?'저장된 세그먼트 보기':'저장된 캠페인 보기',()=>{location.hash=routeHash({view:segment?'segments':'campaigns',resource:message.saved.id,dataset:route.dataset,from:route.from,to:route.to});},signal));
      if(segment)card.append(button('이 세그먼트로 캠페인 초안 만들어',()=>fill('이 세그먼트로 캠페인 초안 만들어',message.saved.context_hint),signal,'ai-followup'));}
  }
  card.append(el('p',{className:'small muted',text:`${response.mode==='mock'?'모의 응답':'실제 AI'} · ${formatTime(message.at)}`}));bubble.append(card);return bubble;
}
