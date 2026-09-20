import {el, errorMessage, formatTime} from '../../components/dom.js';
import {request, isUUID} from '../../api/client.js';
import {store} from '../../app/store.js';
import {apiPeriod, navigate} from '../../app/router.js';
import {renderPreview} from '../segments/preview.js';

const examples = ['활성 고객 수를 알려줘', '60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘'];
const labels = {total_customers:'전체 고객', active_customers:'활성 고객', new_customers:'신규 고객', dormant_customers:'휴면 고객', purchase_conversion_rate:'구매 전환율', repeat_purchase_rate:'재구매율'};
const ruleLabels = {WITHDRAWN:'탈퇴 고객',NO_CONSENT:'수신 미동의',INVALID_CONTACT:'연락처 오류',EXCLUDED_SEGMENT:'제외 세그먼트',DUPLICATE_CAMPAIGN:'같은 캠페인 기수신',DAILY_LIMIT:'일일 노출 초과',WEEKLY_LIMIT:'최근 7일 노출 초과'};

let previousScope = null;

export function renderAI(root, pageSignal) {
  const panel = el('section', {className:'ai-workspace'});
  root.replaceChildren(panel);
  const context = el('p', {className:'small muted', text:store.get().selectedDataset?.name || '상단에서 데이터셋을 선택해주세요.'});
  const badge = el('span', {className:'badge', text:'연결 확인 중'});
  const campaignSelect = el('select', {'aria-label':'검수할 캠페인'}, el('option',{value:'',text:'캠페인 검수 안 함'}));
  const campaignHint = el('p',{className:'small muted',text:'작성 중인 캠페인을 선택하면 AI가 단계 8과 같은 정책 검수를 실행합니다.'});
  const validationContext = el('div',{className:'ai-validation-context'},
    el('label',{},el('span',{text:'캠페인 검수'}),campaignSelect),campaignHint);
  const results = el('div', {className:'ai-messages', 'aria-live':'polite', role:'log'});
  const input = el('textarea', {id:'ai-input', rows:1, maxlength:2000, required:'', placeholder:'AI에게 요청하기'});
  const send = el('button', {className:'button', type:'submit', text:'전송', 'aria-label':'전송'});
  const form = el('form', {className:'ai-input-bar'}, el('label', {for:'ai-input', className:'sr-only', text:'AI에게 요청하기'}), input, send);
  const messages = [];
  const controllers = new Set();
  let controller, busy = false;
  const currentScope = () => {
    const {route} = store.get();
    return JSON.stringify([route?.dataset, route?.from, route?.to]);
  };
  let scope = currentScope();
  const scroll = () => requestAnimationFrame(() => {results.scrollTop = results.scrollHeight;});
  const addMessage = (role, content, node = null) => {
    const bubble = el('article', {className:`ai-message ai-message-${role}`},
      el('span', {className:'sr-only', text:role === 'user' ? '나의 메시지' : role === 'system' ? '시스템 안내' : 'AI 응답'}), node || el('p', {text:content}));
    messages.push({role, content, node:bubble}); results.append(bubble); scroll(); return bubble;
  };
  const welcome = () => {
    const intro = el('div', {}, el('h2', {text:'데이터에서 다음 행동까지'}),
      el('p', {text:'조회할 지표나 고객 조건을 알려주세요. 결과를 확인한 뒤 세그먼트로 저장할 수 있습니다.'}),
      ...examples.map(text => {
        const chip = el('button', {className:'button secondary ai-example', text, type:'button'});
        chip.onclick = () => {input.value = text; resize(); input.focus();}; return chip;
      }));
    results.append(el('article', {className:'ai-message ai-message-assistant ai-welcome-message'}, intro));
  };
  const resize = () => {input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight,150)}px`;};
  const setBusy = value => {
    busy = value; send.disabled = value; input.disabled = value;
    send.replaceChildren(value ? el('span', {className:'ai-spinner', 'aria-hidden':'true'}) : document.createTextNode('전송'));
    send.setAttribute('aria-label', value ? '응답 기다리는 중' : '전송');
  };
  panel.replaceChildren(el('header', {className:'ai-chat-header'},
    el('div', {className:'panel-heading'}, el('h1', {text:'AI 어시스턴트'}), badge), context, validationContext), results, form);
  if (previousScope && previousScope !== scope) addMessage('system', '데이터셋 또는 기간이 변경되어 대화를 새로 시작합니다.');
  else welcome();
  previousScope = scope;
  const sync = () => {
    if (scope !== currentScope()) {
      scope = currentScope(); previousScope = scope; controllers.forEach(c => c.abort()); controllers.clear();
      messages.length = 0; results.replaceChildren(); setBusy(false);
      addMessage('system', '데이터셋 또는 기간이 변경되어 대화를 새로 시작합니다.');
    }
  };
  const unsubscribe = store.subscribe(sync);
  pageSignal.addEventListener('abort', () => {controllers.forEach(c => c.abort()); unsubscribe();}, {once:true});
  input.addEventListener('input', resize);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {event.preventDefault(); form.requestSubmit();}
  });
  request('/ai/status', {signal:pageSignal}).then(status => {
    badge.textContent = status.mode === 'mock' ? '모의 응답' : '실제 AI';
    if (!status.available) {badge.textContent = '연결 설정 필요';}
  }).catch(() => {badge.textContent = '연결 확인 실패';});
  const campaigns = new Map();
  const loadCampaigns = async () => {
    const dataset = store.get().selectedDataset;
    if (!dataset) return;
    try {
      const page = await request(`/campaigns?dataset_id=${dataset.id}&page=1&page_size=100`,{signal:pageSignal});
      for (const row of page.items || []) if (row.status === 'DRAFT') {
        campaigns.set(row.id,row);
        campaignSelect.append(el('option',{value:row.id,text:`${row.name} · ${row.channel}`}));
      }
      if (!campaigns.size) campaignHint.textContent='검수할 작성 중 캠페인이 없습니다. Campaigns에서 초안을 먼저 저장해주세요.';
    } catch (error) {if (!pageSignal.aborted) campaignHint.textContent=errorMessage(error);}
  };
  loadCampaigns();
  campaignSelect.addEventListener('change',()=>{
    if (campaignSelect.value) {input.value='선택한 캠페인을 정책 검수해줘'; resize(); input.focus();}
  });
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const {route, selectedDataset, loading} = store.get();
    if (!selectedDataset || loading) {results.replaceChildren(el('p', {text:'데이터셋을 먼저 선택해주세요.'})); return;}
    const prompt = input.value.trim(); if (!prompt) return;
    sync(); controller = new AbortController(); controllers.add(controller); const signal = controller.signal;
    results.querySelector('.ai-welcome-message')?.remove();
    addMessage('user', prompt); input.value = ''; resize();
    const pending = addMessage('assistant', '응답을 준비하고 있습니다…');
    setBusy(true);
    try {
      const selectedCampaign=campaigns.get(campaignSelect.value);
      const response = await request('/ai/chat', {method:'POST', signal, body:{prompt, dataset_id:selectedDataset.id,
        ...apiPeriod(route.from, route.to), reference_at:selectedDataset.reference_at || apiPeriod(route.from, route.to).to,
        ...(selectedCampaign?{validation_campaign_id:selectedCampaign.id,validation_campaign_version:selectedCampaign.version}:{})},
        validate:r => ['metric','segment_preview','clarification','campaign_validation'].includes(r?.result_type) && typeof r.message === 'string' && r.data && isUUID(r.dataset_id)});
      if (signal.aborted) return;
      const data = response.data;
      const card = el('section', {className:'ai-result'}, el('p', {text:response.message}));
      if (response.result_type === 'metric') {
        for (const [key, metric] of Object.entries(data.metrics)) card.append(el('h3', {text:labels[key] || key}),
          el('strong', {text:metric.value === null ? '집계할 데이터가 없습니다' : `${metric.value.toLocaleString('ko-KR')}${metric.unit === 'percent' ? '%' : '명'}`}));
        card.append(el('p', {className:'small muted', text:`${route.from} ~ ${route.to}`}));
      }
      if (response.result_type === 'segment_preview') {
        if (data.name) card.append(el('h3', {text:data.name}));
        card.append(renderPreview(data));
        if (data.proposal_id) {
          const apply = el('button', {className:'button', type:'button', text:'확인 후 세그먼트 저장'});
          const notice = el('p', {role:'status', className:'small'});
          card.append(el('p', {className:'small muted', text:`제안 만료: ${formatTime(data.expires_at)}`}), apply, notice);
          apply.onclick = async () => {
            apply.disabled = true; notice.textContent = '저장 중…';
            try {
              const saved = await request(`/ai/actions/${data.proposal_id}/confirm`, {method:'POST', signal, body:{dataset_id:response.dataset_id}, validate:r => isUUID(r?.id)});
              if (signal.aborted) return;
              pending.classList.add('ai-message-saved'); notice.textContent = '세그먼트가 저장되었습니다.'; apply.textContent = '저장 완료'; scroll();
              const open = el('button', {className:'button secondary', text:'저장된 세그먼트 보기', type:'button'});
              open.onclick = () => navigate({view:'segments', resource:saved.id, dataset:response.dataset_id});
              card.append(open);
              // Refresh a visible segment list through its existing API rendering path.
              if (store.get().route.view === 'segments') window.dispatchEvent(new Event('hashchange'));
            } catch (error) {if (!signal.aborted) {notice.textContent = errorMessage(error); apply.disabled = false;}}
          };
        }
      }
      if (response.result_type === 'campaign_validation') {
        card.append(el('h3',{text:data.campaign_name}),el('div',{className:'review-counts'},
          el('div',{},el('strong',{text:data.initial_count.toLocaleString('ko-KR')}),el('span',{text:'최초 대상'})),
          el('div',{},el('strong',{text:data.excluded_count.toLocaleString('ko-KR')}),el('span',{text:'제외'})),
          el('div',{},el('strong',{text:data.eligible_count.toLocaleString('ko-KR')}),el('span',{text:'승인 대상'}))));
        const affected=(data.rules||[]).filter(row=>row.affected_count);
        if (affected.length) {
          const items=affected.map(row=>el('li',{},el('span',{text:ruleLabels[row.rule_code]||row.message}),
            el('strong',{text:`${row.affected_count.toLocaleString('ko-KR')}명`})));
          card.append(el('ul',{className:'review-rules'},...items));
        }
        for (const blocker of data.blockers||[]) card.append(el('p',{className:'review-blocker',text:blocker.message}));
        if (data.passed) card.append(el('p',{className:'review-approved',text:'✓ 검수를 통과했습니다. 캠페인 화면에서 승인 요청을 진행할 수 있습니다.'}));
        const open=el('button',{className:'button',type:'button',text:'캠페인 승인 화면 열기'});
        open.onclick=()=>navigate({view:'campaigns',resource:data.campaign_id,dataset:response.dataset_id});
        card.append(el('p',{className:'small muted',text:`검수 결과는 ${formatTime(data.expires_at)}까지 유효합니다.`}),open);
      }
      card.append(el('p', {className:'small muted', text:`${selectedDataset.name} · ${response.mode === 'mock' ? '모의 응답' : '실제 AI'}`}));
      card.append(el('small', {className:'muted', text:'조회 기준', title:`데이터셋 ${response.dataset_id} · 데이터 버전 ${response.data_version} · 기준 시점 ${response.reference_at}`}));
      pending.replaceChildren(el('span', {className:'sr-only', text:'AI 응답'}), card);
      Object.assign(messages.find(m => m.node === pending), {content:response.message, resultType:response.result_type, data:response.data}); scroll();
    } catch (error) {
      if (!signal.aborted) {pending.replaceChildren(el('p', {role:'alert', text:errorMessage(error)})); input.value = prompt; resize(); scroll();}
    } finally {if (!signal.aborted) {setBusy(false); input.focus({preventScroll:true});}}

  });

}
