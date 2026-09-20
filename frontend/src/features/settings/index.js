import {el, heading, errorMessage} from '../../components/dom.js';
import {request} from '../../api/client.js';

const channels=[['EMAIL','이메일'],['PUSH','앱 푸시'],['SMS','SMS']];
const lines=value=>(value||[]).join('\n');
const parse=value=>[...new Set(value.split('\n').map(row=>row.trim()).filter(Boolean))];

export async function renderSettings(root,route,signal) {
  let policy=await request(`/policy-settings?dataset_id=${route.dataset}`,{signal});
  const form=el('form',{className:'card settings-policy'}),notice=el('div',{role:'status'});
  const daily=el('input',{type:'number',min:1,max:20,value:policy.daily_limit,required:''});
  const weekly=el('input',{type:'number',min:1,max:100,value:policy.weekly_limit,required:''});
  const forbidden={},required={};
  form.append(el('h2',{text:'채널 검수 정책'}),el('p',{className:'muted',text:'모든 방문자가 함께 사용하는 데모 정책입니다. 변경 즉시 기존 검수 결과가 만료됩니다.'}),
    el('div',{className:'form-grid'},el('label',{},el('span',{text:'하루 최대 발송 횟수'}),daily),el('label',{},el('span',{text:'최근 7일 최대 발송 횟수'}),weekly)));
  for (const [code,label] of channels) {
    forbidden[code]=el('textarea',{rows:3,value:lines(policy.forbidden_phrases[code]),placeholder:'한 줄에 하나'});
    required[code]=el('textarea',{rows:3,value:lines(policy.required_phrases[code]),placeholder:'한 줄에 하나'});
    form.append(el('fieldset',{className:'campaign-section'},el('legend',{text:label}),el('label',{},el('span',{text:'금지 표현'}),forbidden[code]),el('label',{},el('span',{text:'필수 문구'}),required[code])));
  }
  const submit=el('button',{className:'button',type:'submit',text:'정책 저장'}); form.append(notice,submit);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;notice.textContent='저장 중…';
    try {policy=await request('/policy-settings',{method:'PUT',signal,body:{dataset_id:route.dataset,version:policy.version,daily_limit:Number(daily.value),weekly_limit:Number(weekly.value),
      forbidden_phrases:Object.fromEntries(channels.map(([code])=>[code,parse(forbidden[code].value)])),required_phrases:Object.fromEntries(channels.map(([code])=>[code,parse(required[code].value)]))}}); notice.textContent='정책이 저장되었습니다. 새 검수부터 적용됩니다.';}
    catch(error){notice.textContent=errorMessage(error);}finally{submit.disabled=false;}},{signal});
  root.replaceChildren(heading('Settings','발송 한도와 채널별 문구 정책을 관리하세요.'),form);
}
