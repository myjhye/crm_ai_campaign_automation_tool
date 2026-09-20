import {el,errorMessage} from '../../components/dom.js';
import {request} from '../../api/client.js';
import {apiPeriod} from '../../app/router.js';
import {campaignSetup} from './setup.js';

export function campaignAssistant({route,signal,read,apply,applyFull,fingerprint,isBusy,setBusy}) {
  const setup=campaignSetup(route,signal);
  const mode=el('fieldset',{className:'campaign-ai-modes'},el('legend',{text:'캠페인 AI 작업'}));
  mode.value='copy';
  const choices=[];
  for(const [value,label] of [['copy','카피만 수정'],['full','전체 초안 생성']]){
    const input=el('input',{type:'checkbox',value});
    input.checked=value===mode.value;
    choices.push(input);
    input.addEventListener('change',()=>{
      mode.value=value;
      for(const choice of choices)choice.checked=choice.value===value;
    },{signal});
    mode.append(el('label',{},input,el('span',{text:label})));
  }
  mode.append(el('p',{className:'small muted',text:'한 번에 한 가지 작업을 선택합니다.'}));
  const badge=el('span',{className:'badge',text:'연결 확인 중'});
  const prompt=el('textarea',{'aria-label':'AI 카피 요청',rows:4,maxlength:2000,placeholder:'예: A안은 혜택을 강조하고 B안은 친근한 인사로 작성해줘'});
  const status=el('p',{className:'small',role:'status'});
  let noticeTimer;
  function resetNotice(){
    clearTimeout(noticeTimer);
    status.className='small';status.textContent='';
  }
  function showSuccess(full,responseMode){
    resetNotice();status.className='small campaign-ai-success';
    status.textContent=`✓ ${full?'전체 초안을':'A/B 카피를'} 입력했습니다. 검토 후 저장해주세요.${responseMode==='mock'?' (모의 응답)':''}`;
    noticeTimer=setTimeout(resetNotice,4000);
  }
  signal.addEventListener('abort',()=>clearTimeout(noticeTimer),{once:true});
  mode.addEventListener('change',resetNotice,{signal});
  const guidance=el('p',{className:'small muted',text:'왼쪽의 대상·채널·혜택으로 A/B 제목, 본문, 가설을 채웁니다.'});
  const generate=el('button',{className:'button',type:'button',text:'AI로 A/B 카피 채우기'});
  const root=el('section',{className:'card campaign-ai','aria-label':'캠페인 AI 어시스턴트'},
    el('div',{className:'panel-heading'},el('h2',{text:'✦ 캠페인 어시스턴트'}),badge),mode,
    guidance,
    setup.root,el('label',{},el('span',{text:'추가 요청 (선택)'}),prompt),generate,status,
    el('p',{className:'small muted',text:'생성된 문안은 직접 수정할 수 있습니다. 확인 후 메인 폼에서 저장해주세요.'}));
  request('/ai/status',{signal}).then(s=>{badge.textContent=s.mode==='mock'?'모의 응답':'실제 AI';if(!s.available)badge.textContent='연결 설정 필요';}).catch(()=>{if(!signal.aborted)badge.textContent='연결 확인 실패';});
  mode.addEventListener('change',()=>{setup.root.hidden=mode.value!=='full';generate.textContent=mode.value==='full'?'전체 초안 만들기':'AI로 A/B 카피 채우기';prompt.placeholder=mode.value==='full'?'선택한 설정 외에 원하는 표현이 있으면 적어주세요. 비워도 생성할 수 있습니다.':'예: A안은 혜택, B안은 관계를 강조해줘';},{signal});
  mode.addEventListener('change',()=>{guidance.textContent=mode.value==='full'?'아래에서 대상과 혜택을 지정하고 나머지 추천 설정을 확인하세요. 추가 문장 없이 생성할 수 있습니다.':'왼쪽의 대상·채널·혜택으로 A/B 제목, 본문, 가설을 채웁니다.';status.textContent='';},{signal});
  generate.addEventListener('click',async()=>{
    if(isBusy())return;
    resetNotice();
    let snapshot;
    const full=mode.value==='full';
    try {snapshot=full?{fingerprint:fingerprint(),setup:setup.read()}:read();} catch(error){status.textContent=error.message;return;}
    setup.root.disabled=true;
    mode.disabled=true;
    setBusy(true);generate.disabled=true;prompt.disabled=true;status.textContent='A/B 카피를 생성하고 있습니다…';
    try {
      const period=apiPeriod(route.from,route.to);
      const response=await request(full?'/ai/campaign-plan':'/ai/campaign-draft',{method:'POST',signal,body:{dataset_id:route.dataset,...period,
        reference_at:period.to,prompt:prompt.value.trim()||'제공된 혜택을 유지하고 서로 다른 강조점으로 A/B 카피를 작성해주세요.',campaign_brief:snapshot.brief,campaign_setup:snapshot.setup},
        validate:r=>(full&&r?.result_type==='clarification'&&typeof r.message==='string')||(r?.result_type==='campaign_draft'&&Array.isArray(r.data?.variants)&&r.data.variants.length===2&&
          ['A','B'].every(n=>r.data.variants.filter(v=>v.variant_name===n&&['subject','body','hypothesis'].every(k=>typeof v[k]==='string')).length===1))});
      if(signal.aborted)return;
      if(response.result_type==='clarification'){status.textContent=response.message+' 요청에 답을 덧붙여 다시 생성해주세요.';return;}
      if(fingerprint()!==snapshot.fingerprint){status.textContent='입력 내용이 변경되어 자동 채우기를 취소했습니다. 다시 생성해주세요.';return;}
      if(full) applyFull(response.data,response.segment_name);
      else apply(response.data.variants);
      showSuccess(full,response.mode);
    } catch(error){if(!signal.aborted)status.textContent=errorMessage(error);}
    finally {if(!signal.aborted){setBusy(false);generate.disabled=false;prompt.disabled=false;mode.disabled=false;setup.root.disabled=false;}}
  },{signal});
  return root;
}
