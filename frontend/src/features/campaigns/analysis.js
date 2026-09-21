import {el,button,errorMessage} from '../../components/dom.js';
import {navigate} from '../../app/router.js';
import {performanceAssistant,requestPerformanceAnalysis} from '../ai/performance.js';

// Page-session cache only. Dataset/period/campaign/version changes never reuse evidence.
const results=new Map();
const keyFor=(route,campaign)=>JSON.stringify([route.dataset,route.from,route.to,campaign.id,campaign.version]);
const remember=(key,result)=>{results.delete(key);results.set(key,result);if(results.size>30)results.delete(results.keys().next().value);};

export function campaignAnalysis({route,signal,campaign,view='campaigns',experiment=null}){
  const key=keyFor(route,campaign),cached=results.get(key);
  const panel=el('section',{className:'card campaign-analysis-panel','aria-label':'캠페인 AI 분석'});
  const pending=experiment&&!experiment.winner&&!experiment.reasons?.includes('NO_SIGNIFICANT_DIFFERENCE');
  const invitation=experiment?.winner?'AI가 분석하고 후속 캠페인 초안을 제안합니다':pending?'결과 해석이 어려우신가요? AI가 도와드립니다':experiment?.reasons?.includes('NO_SIGNIFICANT_DIFFERENCE')?'결과와 다음 실험 방향을 AI에게 물어보세요':'AI가 성과를 해석하고 다음 실험을 제안합니다';
  const entry=el('section',{className:`ai-performance${pending?' is-pending':''}`}),notice=el('p',{className:'small muted',role:'status'});
  const open=()=>navigate({view,resource:campaign.id,tab:'ai-analysis'});
  const entryButton=button(cached?'✦ AI 분석 결과 보기':'✦ AI 성과 분석 요청',async()=>{
    if(results.has(key)){open();return;}
    entryButton.disabled=true;notice.textContent='실제 지표를 분석하고 있습니다. 완료되면 AI 분석 탭으로 이동합니다.';
    try{
      const result=await requestPerformanceAnalysis({route,signal,campaignId:campaign.id});
      if(signal.aborted)return;
      remember(key,result);open();
    }catch(error){if(!signal.aborted){notice.setAttribute('role','alert');notice.textContent=errorMessage(error);}}
    finally{if(!signal.aborted)entryButton.disabled=false;}
  },signal,'button ai-performance-button');
  entry.append(el('div',{className:'ai-performance-cta'},el('div',{className:'ai-performance-intro'},
    el('strong',{text:invitation}),
    el('p',{className:'small muted',text:'실제 지표·가설·한계·다음 행동을 AI 분석 탭에서 확인하세요'})),entryButton),notice);
  panel.append(performanceAssistant({route,signal,campaignId:campaign.id,initialResult:cached||null,analysisLayout:true,
    onResult:result=>{remember(key,result);entryButton.textContent='✦ AI 분석 결과 보기';}}));
  return {entry,panel};
}
