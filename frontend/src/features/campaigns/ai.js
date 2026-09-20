import {el,errorMessage} from '../../components/dom.js';
import {request} from '../../api/client.js';
import {apiPeriod} from '../../app/router.js';
import {campaignSetup} from './setup.js';

export function campaignAssistant({route,signal,applyFull,fingerprint,isBusy,setBusy}) {
  const setup=campaignSetup(route,signal);
  setup.root.hidden=false;
  const badge=el('span',{className:'badge',text:'연결 확인 중'});
  const prompt=el('textarea',{'aria-label':'AI 카피 요청',rows:4,maxlength:2000,placeholder:'예: A안은 혜택을 강조하고 B안은 친근한 인사로 작성해줘'});
  const status=el('p',{className:'small',role:'status'});
  let noticeTimer;
  function resetNotice(){
    clearTimeout(noticeTimer);
    status.className='small';status.textContent='';
  }
  function showSuccess(responseMode,cacheHit){
    resetNotice();status.className='small campaign-ai-success';
    status.textContent=`✓ ${cacheHit?'같은 설정의 이전 초안을 불러왔습니다.':'전체 초안을 입력했습니다.'} 검토 후 저장해주세요.${responseMode==='mock'?' (모의 응답)':''}`;
    noticeTimer=setTimeout(resetNotice,4000);
  }
  signal.addEventListener('abort',()=>clearTimeout(noticeTimer),{once:true});
  const guidance=el('p',{className:'small muted',text:'대상과 혜택을 지정하면 캠페인 설정부터 A/B 문안까지 메인 폼에 채웁니다.'});
  const generate=el('button',{className:'button',type:'button',text:'전체 초안 만들기'});
  const root=el('section',{className:'card campaign-ai','aria-label':'캠페인 AI 어시스턴트'},
    el('div',{className:'panel-heading'},el('h2',{text:'✦ 캠페인 어시스턴트'}),badge),
    guidance,
    setup.root,el('label',{},el('span',{text:'추가 요청 (선택)'}),prompt),generate,status,
    el('p',{className:'small muted',text:'생성된 문안은 직접 수정할 수 있습니다. 확인 후 메인 폼에서 저장해주세요.'}));
  request('/ai/status',{signal}).then(s=>{badge.textContent=s.mode==='mock'?'모의 응답':'실제 AI';if(!s.available)badge.textContent='연결 설정 필요';}).catch(()=>{if(!signal.aborted)badge.textContent='연결 확인 실패';});
  generate.addEventListener('click',async()=>{
    if(isBusy())return;
    resetNotice();
    let snapshot;
    try {snapshot={fingerprint:fingerprint(),setup:setup.read()};} catch(error){status.textContent=error.message;return;}
    setup.root.disabled=true;
    setBusy(true);generate.disabled=true;prompt.disabled=true;status.textContent='A/B 카피를 생성하고 있습니다…';
    try {
      const period=apiPeriod(route.from,route.to);
      const response=await request('/ai/campaign-plan',{method:'POST',signal,body:{dataset_id:route.dataset,...period,
        reference_at:period.to,prompt:prompt.value.trim()||'제공된 혜택을 유지하고 서로 다른 강조점으로 A/B 카피를 작성해주세요.',campaign_setup:snapshot.setup},
        validate:r=>(r?.result_type==='clarification'&&typeof r.message==='string')||(r?.result_type==='campaign_draft'&&Array.isArray(r.data?.variants)&&r.data.variants.length===2&&
          ['A','B'].every(n=>r.data.variants.filter(v=>v.variant_name===n&&['subject','body','hypothesis'].every(k=>typeof v[k]==='string')).length===1))});
      if(signal.aborted)return;
      if(response.result_type==='clarification'){status.textContent=response.message+' 요청에 답을 덧붙여 다시 생성해주세요.';return;}
      if(fingerprint()!==snapshot.fingerprint){status.textContent='입력 내용이 변경되어 자동 채우기를 취소했습니다. 다시 생성해주세요.';return;}
      applyFull(response.data,response.segment_name);
      showSuccess(response.mode,response.cache_hit);
    } catch(error){if(!signal.aborted)status.textContent=errorMessage(error);}
    finally {if(!signal.aborted){setBusy(false);generate.disabled=false;prompt.disabled=false;setup.root.disabled=false;}}
  },{signal});
  return root;
}
