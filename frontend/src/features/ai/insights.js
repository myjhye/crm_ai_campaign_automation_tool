import {el, button, errorMessage} from '../../components/dom.js';
import {request, isUUID} from '../../api/client.js';
import {apiPeriod, routeHash} from '../../app/router.js';
export function insights(route, fill, signal) {
  const root=el('section',{className:'ai-insights','aria-label':'현재 데이터 인사이트'},el('p',{role:'status',text:'데이터를 살펴보고 있습니다…'}));
  async function load(){
    try{
      const params=new URLSearchParams({dataset_id:route.dataset,...apiPeriod(route.from,route.to)});
      const response=await request(`/ai/insights?${params}`,{signal,validate:r=>Array.isArray(r?.cards)});
      if(signal.aborted)return;
      root.replaceChildren(...response.cards.map(card=>{
        const cta=card.cta;
        const action=cta?.action==='navigate'&&isUUID(cta.campaign_id)?el('a',{className:'ai-insight-link',text:cta.label,
          href:routeHash({view:'campaigns',resource:cta.campaign_id,dataset:route.dataset,from:route.from,to:route.to,tab:'ai-analysis'})}):
          typeof cta?.prefill_prompt==='string'?button(cta.label,()=>fill(cta.prefill_prompt),signal,'ai-insight-link'):null;
        return el('article',{className:'ai-insight-card'},el('h3',{text:card.title}),el('strong',{text:card.primary_value}),
          el('p',{className:'small muted',text:card.secondary_value}),action);
      }));
      if(!response.cards.length)root.append(el('p',{className:'small muted',text:'이 기간에는 요약할 데이터가 없습니다. 아래에서 직접 질문할 수 있습니다.'}));
    }catch(error){if(!signal.aborted)root.replaceChildren(el('div',{className:'ai-insight-error'},
      el('p',{className:'small muted',text:`인사이트를 불러오지 못했습니다. 대화는 계속 사용할 수 있습니다. ${errorMessage(error)}`}),button('다시 불러오기',load,signal)));}
  }
  load();return root;
}
