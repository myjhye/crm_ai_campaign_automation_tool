import {request} from '../../api/client.js';
import {apiPeriod,navigate} from '../../app/router.js';
import {el,button,errorMessage,formatTime} from '../../components/dom.js';

export function requestPerformanceAnalysis({route,signal,campaignId}) {
  return request('/ai/performance-analysis',{method:'POST',signal,
    body:{dataset_id:route.dataset,campaign_id:campaignId,...apiPeriod(route.from,route.to)},
    validate:value=>value?.result_type==='performance_analysis'&&Array.isArray(value.data?.facts)&&Array.isArray(value.data?.limitations)});
}

function factSummary(data,campaignId,signal){
  const refs=data.metric_refs||Object.fromEntries(data.facts.map(f=>[f.metric_id,f]));
  const value=id=>refs[id]?`${Number(refs[id].value).toLocaleString('ko-KR')}${refs[id].unit}`:'—';
  return el('section',{className:'analysis-section analysis-facts','aria-label':'성과 요약'},el('h4',{text:'성과 요약'}),
    ...['A','B'].map(arm=>el('p',{className:'analysis-arm-summary',text:`${arm}안 ${value(`${arm}.delivered_customers`)} 전달 · ${value(`${arm}.conversion_rate`)} 전환`})),
    el('p',{className:'small muted',text:`p=${value('experiment.p_value')} · B−A ${value('experiment.absolute_difference_pp')}`}),
    button('발송·결과 탭에서 자세히 보기',()=>navigate({view:'campaigns',resource:campaignId,tab:'results'}),signal,'button secondary'));
}

export function performanceAssistant({route,signal,campaignId,initialResult=null,experiment=null,secondaryAction=null,analysisLayout=false,onResult=()=>{}}) {
  const verdict=experiment||initialResult?.data?.experiment;
  const uncertain=verdict?.reasons?.includes('NO_SIGNIFICANT_DIFFERENCE');
  const pending=verdict&&!verdict.winner&&!uncertain;
  const invitation=verdict?.winner?'AI가 분석하고 후속 캠페인 초안을 제안합니다':uncertain?'결과와 다음 실험 방향을 AI에게 물어보세요':pending?'결과 해석이 어려우신가요? AI가 도와드립니다':'AI가 이 결과를 해석해드릴 수 있습니다';
  const panel=el('section',{className:`ai-performance${pending?' is-pending':''}`,'aria-label':'AI 성과 분석'});
  const output=el('div',{className:'ai-performance-output',id:`ai-analysis-${crypto.randomUUID()}`,'aria-live':'polite',hidden:true});
  let busy=false;
  const generate=button('✦ AI 성과 분석 요청',async()=>{
    if(busy)return;busy=true;generate.disabled=true;
    output.hidden=false;generate.setAttribute('aria-expanded','true');output.setAttribute('aria-busy','true');
    output.replaceChildren(el('p',{className:'small muted',text:'실제 지표와 실험 결과를 분석하고 있습니다…'}));
    try {
      const result=initialResult||await requestPerformanceAnalysis({route,signal,campaignId});
      if(signal.aborted)return;
      initialResult=null;
      onResult(result);
      const data=result.data;
      const list=(title,items)=>el('section',{},el('h4',{text:title}),el('ul',{},...items.map(text=>el('li',{text}))));
      output.replaceChildren(el('div',{className:'panel-heading'},el('h3',{text:'성과 분석과 다음 실험'}),el('span',{className:'badge',text:result.mode==='mock'?'모의 응답':'실제 AI'})),
        el('p',{className:'notice',text:data.conclusion||(data.experiment.winner?`${data.experiment.winner}안 우세 · 기존 통계 검정 결과입니다.`:'승자 확정 불가 · 수치상 차이가 있어도 실험 판정 조건과 한계를 먼저 확인하세요.')}),
        el('p',{className:'small muted',text:`${route.from} ~ ${route.to} 발송 기준 · ${formatTime(data.reference_at)} 분석`}),
        list('확인된 사실',data.facts.map(f=>`${f.label}: ${Number(f.value).toLocaleString('ko-KR')}${f.unit}`)),
        list('검증이 필요한 가설',data.hypotheses.length?data.hypotheses:['원인을 단정할 수 있는 추가 근거가 없습니다.']),
        list('해석의 한계',data.limitations),list('다음 행동',data.recommended_actions.map(a=>a.text)));
      if(analysisLayout){
        output.firstElementChild.querySelector('h3').textContent='AI 분석 결과';
        const sections=[...output.children].slice(3);
        sections.forEach(section=>section.remove());
        const interpretation=el('section',{className:'analysis-section analysis-interpretation'},el('h3',{text:'💡 AI 해석'}),
          list('검증이 필요한 가설',data.hypotheses.length?data.hypotheses:['원인을 단정할 추가 근거가 없습니다.']),
          list('다음 행동',data.recommended_actions.map(a=>a.text)));
        const conclusion=output.querySelector('.notice').textContent;
        const limits=data.limitations.filter(text=>text.trim()!==conclusion.trim()&&text.trim()!==data.conclusion?.trim());
        const disclosure=el('details',{className:'analysis-section analysis-limits'},el('summary',{text:'이 분석의 한계'}),
          el('ul',{},...limits.map(text=>el('li',{text}))));
        output.append(interpretation,el('div',{className:'analysis-grid'},factSummary(data,campaignId,signal),disclosure));generate.textContent='다시 분석';
      }
      const proposal=data.proposal;
      if(proposal){
        const draft=proposal.draft;
        const notice=el('p',{role:'status',className:'small muted'});
        const confirm=button('확인 후 후속 초안 저장',async()=>{
          if(confirm.disabled)return;confirm.disabled=true;generate.disabled=true;
          try{
            const saved=await request(`/ai/actions/${proposal.proposal_id}/confirm`,{method:'POST',signal,body:{dataset_id:route.dataset},validate:v=>!!v?.id&&v.status==='DRAFT'});
            if(signal.aborted)return;
            confirm.remove();notice.className='notice';notice.textContent='✓ 후속 캠페인 초안을 저장했습니다. 검수와 승인은 아직 진행하지 않았습니다.';
            preview.append(button('저장된 초안 열기',()=>navigate({view:'campaigns',resource:saved.id,tab:'compose'}),signal));
            result.saved_campaign_id=saved.id;
          }catch(error){if(!signal.aborted){notice.className='error-text';notice.textContent=errorMessage(error);confirm.disabled=false;}}
          finally{if(!signal.aborted)generate.disabled=false;}
        },signal);
        const preview=el('section',{className:'ai-followup-preview'},el('h4',{text:'동일 조건 재실험 초안'}),
          el('strong',{text:analysisLayout?'후속 실험':draft.name}),el('p',{text:`${draft.channel} · 대상 ${proposal.segment_name||'원본 대상 세그먼트'}`}),
          el('p',{className:'small',text:`혜택 ${draft.benefit} · 쿠폰 만료 ${draft.coupon_expires_at?formatTime(draft.coupon_expires_at):'미지정'}`}),
          el('div',{className:'analysis-copy-grid'},...draft.variants.map(v=>el('section',{className:'analysis-copy-variant'},
            el('h5',{text:`${v.variant_name}안 (${v.allocation_bp/100}%)`}),
            v.subject?el('div',{},el('span',{className:'small muted',text:'제목'}),el('p',{text:v.subject})):null,
            el('span',{className:'small muted',text:'본문'}),el('p',{className:'ai-followup-copy',text:v.body})))),
          el('p',{className:'small muted',text:'대상·제외 조건·혜택·A/B 문안·배분은 원본을 유지합니다. 저장 후 예정 시각과 쿠폰 만료를 확인하세요.'}),
          el('p',{className:'small muted',text:`${formatTime(proposal.expires_at)}까지 저장 가능`}),confirm,notice);
        output.append(preview);
        if(analysisLayout){preview.classList.add('analysis-followup');preview.querySelector('h4').textContent='🔁 동일 조건 재실험 초안';confirm.classList.add('analysis-save');}
        if(result.saved_campaign_id){
          confirm.remove();notice.textContent='✓ 후속 캠페인 초안을 저장했습니다.';
          preview.append(button('저장된 초안 열기',()=>navigate({view:'campaigns',resource:result.saved_campaign_id,tab:'compose'}),signal));
        }
      }
    }catch(error){if(!signal.aborted)output.replaceChildren(el('p',{className:'error-text',role:'alert',text:errorMessage(error)}));}
    finally{busy=false;output.setAttribute('aria-busy','false');if(!signal.aborted)generate.disabled=false;}
  },signal,'button ai-performance-button');
  generate.setAttribute('aria-controls',output.id);generate.setAttribute('aria-expanded','false');
  panel.append(el('div',{className:'ai-performance-cta'},
    el('div',{className:'ai-performance-intro'},el('strong',{text:invitation}),el('p',{className:'small muted',text:'실제 지표·가설·한계·다음 행동을 정리해드립니다'})),
    el('div',{className:'ai-performance-actions'},generate,secondaryAction)),output);
  if(analysisLayout){panel.classList.add('is-analysis-tab');panel.querySelector('.ai-performance-intro strong').textContent='성과 분석과 다음 실험';}
  if(initialResult)generate.click();
  return panel;
}
