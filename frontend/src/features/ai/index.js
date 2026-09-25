import {el,button,errorMessage} from '../../components/dom.js';
import {request,isUUID} from '../../api/client.js';
import {store} from '../../app/store.js';
import {apiPeriod} from '../../app/router.js';
import {examples} from './examples.js';
import {chatInput} from './input.js';
import {messageNode} from './conversation.js';
import {followups} from './followups.js';

// Memory only: navigation restores this scope; reload clears the conversation.
let memory=null,resetNotice=false;
const scopeOf=route=>JSON.stringify([route?.dataset,route?.from,route?.to]);
store.subscribe(()=>{const route=store.get().route;if(memory&&route&&scopeOf(route)!==memory.scope){memory=null;resetNotice=true;}});
export function renderAI(root,signal){
  const {route,selectedDataset}=store.get();
  if(!memory)memory={scope:scopeOf(route),id:crypto.randomUUID(),messages:[],hint:null,input:''};
  const state=memory;let busy=false;
  const panel=el('section',{className:'ai-workspace ai-workspace-redesign'});
  const badge=el('span',{className:'badge',text:'연결 확인 중'});
  const results=el('div',{className:'ai-messages','aria-live':'polite',role:'log','aria-label':'대화 내용'});
  const composer=chatInput({signal,submit,clearContext:()=>{state.hint=null;draw();},onInput:value=>{state.input=value;}});
  const welcome=el('section',{className:'ai-welcome-message'},
    el('div',{className:'ai-start-heading'},el('span',{className:'ai-start-symbol','aria-hidden':'true',text:'✦'}),
      el('h1',{text:'어떤 고객에게, 어떤 다음 행동을 할까요?'}),
      el('p',{className:'muted',text:'궁금한 질문을 클릭하거나, 아래에 직접 물어보세요.'})),
    ...(!route.dataset?[el('p',{text:'데이터셋을 먼저 선택해주세요.'})]:[]),examples(text=>composer.fill(text),signal));
  const header=el('header',{className:'ai-chat-header'},el('div',{className:'panel-heading'},el('strong',{text:'✦ AI 어시스턴트'}),badge),
    button('새 대화',()=>{if(busy)return;state.messages=[];state.hint=null;state.id=crypto.randomUUID();composer.context(null);composer.fill('');draw(true);},signal));
  panel.append(header,results,composer.node);root.replaceChildren(panel);
  if(resetNotice){state.messages.push({role:'system',content:'데이터셋 또는 기간이 변경되어 대화를 새로 시작합니다.'});resetNotice=false;}
  const options={route,signal,confirm,isBusy:()=>busy,fill:(text,hint)=>{if(busy)return;if(hint){state.hint=hint;composer.context(hint);}composer.fill(text);}};
  function draw(scroll=false){
    const nearBottom=results.scrollHeight-results.scrollTop-results.clientHeight<100;
    results.replaceChildren(...state.messages.map(m=>messageNode(m,options)));
    const started=state.messages.some(m=>m.role==='user');
    if(!started)results.append(welcome);
    composer.context(state.hint);
    const latest=state.messages.findLast(m=>m.role==='assistant');
    composer.suggestions(busy?[]:followups(latest,state.hint),text=>composer.fill(text));
    if(!started)results.scrollTop=0;
    else if(scroll||nearBottom)requestAnimationFrame(()=>{if(!signal.aborted)results.scrollTop=results.scrollHeight;});
  }
  composer.fill(state.input);draw();
  request('/ai/status',{signal}).then(status=>{if(!signal.aborted)badge.textContent=!status.available?'연결 설정 필요':status.mode==='mock'?'모의 응답':'실제 AI';}).catch(()=>{if(!signal.aborted)badge.textContent='연결 확인 실패';});
  signal.addEventListener('abort',()=>{for(const m of state.messages){if(m.pending){m.pending=false;m.content='요청이 중단되었습니다. 다시 요청해주세요.';state.input=m.prompt;}if(m.saving){m.saving=false;m.notice='저장 결과를 다시 확인해주세요. 재시도해도 중복 저장되지 않습니다.';}}},{once:true});
  async function submit(prompt){
    if(busy||signal.aborted)return;
    if(!selectedDataset){state.messages.push({role:'system',content:'데이터셋을 먼저 선택해주세요.'});draw();return;}
    busy=true;composer.busy(true);state.messages.push({role:'user',content:prompt});
    const message={role:'assistant',content:'응답을 준비하고 있습니다…',pending:true,prompt,at:new Date().toISOString()};state.messages.push(message);composer.fill('');draw(true);
    try{
      const period=apiPeriod(route.from,route.to);
      const response=await request('/ai/chat',{method:'POST',signal,body:{prompt,dataset_id:route.dataset,...period,reference_at:period.to,conversation_id:state.id,...(state.hint?{context_hint:state.hint}:{})},
        validate:r=>['metric','segment_preview','clarification','campaign_comparison','campaign_draft'].includes(r?.result_type)&&typeof r.message==='string'&&r.data&&isUUID(r.dataset_id)});
      if(signal.aborted)return;message.response=response;message.pending=false;if(Object.hasOwn(response,'context_hint'))state.hint=response.context_hint;
    }catch(error){if(!signal.aborted){message.pending=false;message.error=true;message.content=errorMessage(error);composer.fill(prompt);}}
    finally{if(!signal.aborted){busy=false;composer.busy(false);draw();composer.input.focus({preventScroll:true});}}
  }
  async function confirm(message){
    if(busy||message.saving||message.saved||signal.aborted)return;busy=true;composer.busy(true);message.saving=true;message.error=false;draw();
    try{
      const saved=await request(`/ai/actions/${message.response.data.proposal_id}/confirm`,{method:'POST',signal,body:{dataset_id:route.dataset},validate:r=>isUUID(r?.id)});
      if(signal.aborted)return;message.saved=saved;message.notice=message.response.result_type==='segment_preview'?'세그먼트가 저장되었습니다.':'캠페인 초안이 저장되었습니다.';if(saved.context_hint)state.hint=saved.context_hint;
    }catch(error){if(!signal.aborted){message.error=true;message.notice=errorMessage(error);}}
    finally{if(!signal.aborted){busy=false;composer.busy(false);message.saving=false;draw();}}
  }
}
