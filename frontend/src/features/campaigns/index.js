import {el, button, heading, errorMessage, stateCard} from '../../components/dom.js';
import {request, isUUID, isPage} from '../../api/client.js';
import {navigate} from '../../app/router.js';
import {campaignAssistant} from './ai.js';
import {campaignReview} from './review.js';

const validRow = r => isUUID(r?.id) && typeof r.name === 'string' && Number.isInteger(r.version);
const validDetail = r => validRow(r) && Array.isArray(r.variants) && r.variants.length === 2 && Array.isArray(r.exclusion_revision_ids);
const localTime = value => value ? new Date(Date.parse(value) + 9*3600000).toISOString().slice(0,16) : '';
const utcTime = value => value ? new Date(`${value}:00+09:00`).toISOString() : null;

export async function renderCampaigns(root, route, signal) {
  const [page, segments, policy, existing] = await Promise.all([
    request(`/campaigns?dataset_id=${route.dataset}&page=${route.page || 1}`, {signal,validate:isPage(validRow)}),
    request(`/segments?dataset_id=${route.dataset}&page_size=100`, {signal}),
    request('/campaigns/copy-policy', {signal}),
    route.resource ? request(`/campaigns/${route.resource}?dataset_id=${route.dataset}`, {signal,validate:validDetail}) : Promise.resolve(null),
  ]);
  if (signal.aborted) return;
  let current = existing, busy = false;
  const fields = {};
  fields.brand_tone = {value:'다정하고 편안하게'};
  const form = el('form', {className:'card campaign-form'});
  const notice = el('div', {role:'status', className:'campaign-notice'});
  const review = el('section', {className:'card campaign-save-review', hidden:'','aria-label':'저장 내용 확인'});
  function field(key, label, options = {}) {
    const input = el(options.tag || 'input', {name:key, 'aria-label':label, type:options.type || (options.tag ? null : 'text'),
      required:options.optional ? null : '', maxlength:options.max || 200, ...options.attrs});
    if (options.values) input.append(...options.values.map(([value,text]) => el('option', {value,text})));
    fields[key] = input;
    return el('label', {}, el('span', {text:label}), input);
  }
  fields.segment_revision_id = {value:''};
  const targetChecks = new Map();
  const targetStatus = el('p',{className:'small muted',role:'status'});
  const targetList = el('div',{className:'exclusion-options'});
  const targetGroup = el('fieldset',{className:'exclusion-group'},el('legend',{text:'대상 세그먼트'}),targetStatus,targetList);
  function updateTarget() {
    for (const [id,input] of targetChecks) input.checked = fields.segment_revision_id.value === id;
    targetStatus.textContent = fields.segment_revision_id.value ? '1개 선택됨 · 다른 항목을 체크하면 대상이 변경됩니다.' : '대상 없음 · 세그먼트 1개를 체크하세요.';
  }
  function addTarget(id,name) {
    if (targetChecks.has(id)) return;
    const input = el('input',{type:'checkbox',value:id});
    targetChecks.set(id,input);
    input.addEventListener('change',() => {fields.segment_revision_id.value = input.checked ? id : ''; updateTarget();},{signal});
    targetList.append(el('label',{className:'exclusion-option'},input,el('span',{text:name})));
  }
  segments.items.forEach(s => addTarget(s.revision_id,s.name));
  const exclusionChecks = new Map();
  const exclusionStatus = el('p',{className:'small muted',role:'status'});
  const exclusionList = el('div',{className:'exclusion-options'});
  const exclusionGroup = el('fieldset',{className:'exclusion-group'},el('legend',{text:'제외 세그먼트'}),exclusionStatus,exclusionList);
  const updateExclusions = () => {
    const count = [...exclusionChecks.values()].filter(input => input.checked).length;
    exclusionStatus.textContent = count ? `${count}개 선택됨 · 체크를 해제하면 제외 조건에서 빠집니다.` : '제외 없음 · 필요한 세그먼트만 체크하세요.';
  };
  function addExclusion(id, name) {
    if (exclusionChecks.has(id)) return;
    const input = el('input',{type:'checkbox',value:id});
    exclusionChecks.set(id,input);
    input.addEventListener('change',updateExclusions,{signal});
    exclusionList.append(el('label',{className:'exclusion-option'},input,el('span',{text:name})));
  }
  segments.items.forEach(s => addExclusion(s.revision_id,s.name));
  (current?.exclusion_revision_ids || []).forEach(id => {if (!exclusionChecks.has(id)) addExclusion(id,'저장된 제외 버전');});
  if (current) addTarget(current.segment_revision_id,'저장된 대상 버전 (유지)');
  const section = (title,...children) => el('fieldset', {className:'campaign-section'}, el('legend',{text:title}),...children);
  form.append(section('1. 목표', field('name','캠페인 이름'), field('objective','캠페인 목표',{max:500}),
    field('primary_kpi','주요 KPI',{tag:'select',values:[['conversion_rate','전환율 (%)'],['click_rate','클릭률 (%)'],['revenue','기여 매출 (원)']]}),
    field('target_value','KPI 목표값',{type:'number',attrs:{min:0,step:'0.01'}})));
  form.append(section('2. 대상', targetGroup,
    exclusionGroup,
    el('p',{className:'small muted',text:'대상은 선택한 세그먼트 버전으로 고정됩니다. 이후 조건 수정은 자동 적용되지 않습니다.'})));
  // Load remaining choices explicitly so large workspaces remain usable.
  if (segments.total > 100) {
    let next = 2;
    const more = button('세그먼트 더 불러오기', async () => {
      more.disabled = true;
      try {
        const rows = await request(`/segments?dataset_id=${route.dataset}&page_size=100&page=${next}`,{signal});
        for (const s of rows.items) {
          addTarget(s.revision_id,s.name);
          addExclusion(s.revision_id,s.name);
        }
        next++; more.hidden = (next-1)*100 >= rows.total;
      } catch(error) {notice.textContent = errorMessage(error);}
      finally {more.disabled = false;}
    },signal);
    form.append(more);
  }
  form.append(section('3. 채널과 혜택', field('channel','채널',{tag:'select',values:[['EMAIL','이메일'],['PUSH','앱 푸시'],['SMS','SMS']]}),
    field('benefit','혜택',{max:1000}),
    field('planned_at','발송 예정 정보 (한국 시간)',{type:'datetime-local',optional:true}),
    field('coupon_expires_at','쿠폰 만료 (한국 시간)',{type:'datetime-local',optional:true}),
    el('p',{className:'small muted',text:'예정 시각은 참고 정보입니다. 자동 예약 발송은 실행되지 않습니다.'})));
  const copy = section('4. A/B 카피');
  const cards = el('div',{className:'campaign-variants'});
  const resizeHypothesis=input=>{input.style.height='auto';input.style.height=`${input.scrollHeight+input.offsetHeight-input.clientHeight}px`;};
  for (const name of ['A','B']) {
    const hypothesis=field(`${name}_hypothesis`,`${name}안 가설`,{tag:'textarea',max:1000,attrs:{rows:2,className:'campaign-hypothesis'}});
    fields[`${name}_hypothesis`].addEventListener('input',event=>resizeHypothesis(event.currentTarget),{signal});
    cards.append(el('div',{className:'campaign-variant'},el('h3',{text:`${name}안`}),
      field(`${name}_subject`,`${name}안 제목`),field(`${name}_body`,`${name}안 본문`,{tag:'textarea',max:5000,attrs:{rows:5}}),hypothesis));
  }
  const limits = el('p',{className:'small muted'}); copy.append(limits,cards); form.append(copy);
  form.append(section('5. 실험 배분',field('A_ratio','A안 비율 (%)',{type:'number',attrs:{min:0.01,max:99.99,step:0.01}}),
    field('B_ratio','B안 비율 (%)',{type:'number',attrs:{min:0.01,max:99.99,step:0.01}})));
  const submit = el('button',{type:'submit',className:'button',text:'초안 저장 후 확인'});
  form.append(notice,submit);
  function channelChanged() {
    const rule = policy.channels[fields.channel.value];
    limits.textContent = `데모 카피 기준 · 제목 ${rule.subject_max}자 / 본문 ${rule.body_max}자 · 일반 텍스트만 지원`;
    for (const name of ['A','B']) {
      const subject = fields[`${name}_subject`];
      subject.disabled = fields.channel.value === 'SMS'; subject.required = !subject.disabled;
      subject.maxLength = rule.subject_max; fields[`${name}_body`].maxLength = rule.body_max;
    }
  }
  function populate(row) {
    if (row) addTarget(row.segment_revision_id,'저장된 대상 버전 (유지)');
    for (const key of ['name','objective','channel','benefit','brand_tone','primary_kpi','target_value','segment_revision_id']) fields[key].value = row?.[key] ?? ({channel:'EMAIL',primary_kpi:'conversion_rate',brand_tone:'다정하고 편안하게'}[key] || '');
    updateTarget();
    for (const key of ['planned_at','coupon_expires_at']) fields[key].value = localTime(row?.[key]);
    for (const id of row?.exclusion_revision_ids || []) if (!exclusionChecks.has(id)) addExclusion(id,'저장된 제외 버전');
    for (const [id,input] of exclusionChecks) input.checked = row?.exclusion_revision_ids.includes(id) || false;
    updateExclusions();
    for (const name of ['A','B']) {
      const variant = row?.variants.find(v => v.variant_name === name);
      for (const key of ['subject','body','hypothesis']) fields[`${name}_${key}`].value = variant?.[key] || '';
      requestAnimationFrame(()=>resizeHypothesis(fields[`${name}_hypothesis`]));
      fields[`${name}_ratio`].value = (variant?.allocation_bp ?? 5000)/100;
    }
    channelChanged();
  }
  fields.channel.addEventListener('change',channelChanged,{signal});
  populate(current);
  let updateTabs=()=>{};
  const reviewFlow=campaignReview({route,signal,getCampaign:()=>current,onCampaign:value=>{
    current=value; populate(current); form.inert=current.status!=='DRAFT'; submit.disabled=current.status!=='DRAFT';updateTabs();
  },onRun:()=>refreshList(),getSegmentName:id=>segments.items.find(row=>row.revision_id===id)?.name});
  if (current) {try {await reviewFlow.load();} catch {reviewFlow.draw();}}
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    if (!fields.segment_revision_id.value) {notice.textContent = '대상 세그먼트 1개를 체크해주세요.'; targetList.querySelector('input')?.focus(); return;}
    const variants = ['A','B'].map(name => ({variant_name:name,subject:fields.channel.value === 'SMS' ? '' : fields[`${name}_subject`].value,
      body:fields[`${name}_body`].value,hypothesis:fields[`${name}_hypothesis`].value,allocation_bp:Math.round(Number(fields[`${name}_ratio`].value)*100)}));
    if (variants.reduce((sum,v) => sum+v.allocation_bp,0) !== 10000) {notice.textContent = 'A/B 비율 합계를 100%로 맞춰주세요.'; return;}
    const rule = policy.channels[fields.channel.value];
    if (variants.some(v => !v.body.trim() || !v.hypothesis.trim() || (fields.channel.value !== 'SMS' && !v.subject.trim()))) {
      notice.textContent = 'A/B 제목·본문·가설을 모두 입력해주세요.'; return;
    }
    if (variants.some(v => /[{}]|<[^>]+>/.test(v.subject+'\n'+v.body))) {
      notice.textContent = '개인화 변수와 HTML은 지원하지 않습니다. 일반 텍스트로 작성해주세요.'; return;
    }
    if (variants.some(v => (rule.forbidden || []).some(word => (v.subject+'\n'+v.body).includes(word)))) {
      notice.textContent = '데모 정책의 금지 표현이 포함되어 있습니다.'; return;
    }
    const payload = {dataset_id:route.dataset,variants,exclusion_revision_ids:[...exclusionChecks].filter(([,input]) => input.checked).map(([id]) => id)};
    if (payload.exclusion_revision_ids.includes(fields.segment_revision_id.value)) {notice.textContent = '대상 세그먼트와 같은 세그먼트는 제외할 수 없습니다.'; return;}
    for (const key of ['name','objective','channel','benefit','brand_tone','primary_kpi','target_value','segment_revision_id']) payload[key] = fields[key].value;
    for (const key of ['planned_at','coupon_expires_at']) payload[key] = utcTime(fields[key].value);
    if (current) payload.version = current.version;
    busy = true; submit.disabled = true; form.inert = true; notice.textContent = '저장 중…';
    try {
      const saved = await request(current ? `/campaigns/${current.id}` : '/campaigns',{method:current?'PUT':'POST',body:payload,signal,validate:validDetail});
      current = saved;
      current = await request(`/campaigns/${saved.id}?dataset_id=${route.dataset}`,{signal,validate:validDetail});
      try {await reviewFlow.load();} catch {reviewFlow.draw();}
      notice.textContent = '캠페인 초안이 저장되었습니다.';
      review.hidden = false;
      const actions=el('div',{className:'campaign-save-actions'},
        button('저장된 캠페인 열기',() => navigate({view:'campaigns',resource:current.id}),signal,'button'),
        button('이 내용으로 새 캠페인 작성',() => {
        const copy = {...current,name:`${current.name} 복사본`};
        current = null; populate(copy); review.hidden = true; notice.textContent = '복사한 내용을 편집한 뒤 저장해주세요.';
      },signal));
      review.replaceChildren(
        el('div',{className:'campaign-save-heading'},el('span',{className:'campaign-save-check','aria-hidden':'true',text:'✓'}),
          el('div',{},el('p',{className:'small muted',text:'6. 저장 내용 확인'}),el('h2',{text:'초안 저장 완료'}))),
        el('h3',{className:'campaign-save-name',text:current.name}),
        el('div',{className:'campaign-save-meta'},
          el('span',{className:'badge',text:{EMAIL:'이메일',PUSH:'앱 푸시',SMS:'SMS'}[current.channel]||current.channel}),
          el('span',{className:'small',text:`A ${variants[0].allocation_bp/100}% · B ${variants[1].allocation_bp/100}%`})),
        el('p',{className:'campaign-save-note small muted',text:'대상자 정책 검수와 승인은 아직 진행하지 않았습니다.'}),actions);
      await refreshList();
    } catch(error) {
      if (signal.aborted) return;
      notice.replaceChildren(el('p',{text:errorMessage(error)}));
      if (error.status === 409) notice.append(button('최신 내용 불러오기',async () => {
        try {current = await request(`/campaigns/${current.id}?dataset_id=${route.dataset}`,{signal,validate:validDetail}); populate(current); notice.textContent = '최신 내용을 불러왔습니다.';}
        catch(e) {notice.textContent = errorMessage(e);}
      },signal));
    } finally {busy = false; submit.disabled = false; form.inert = false;}
  },{signal});
  const list = el('aside',{className:'card campaign-library','aria-label':'저장된 캠페인'});
  const listNotice=el('p',{className:'small campaign-notice',role:'status'});
  const announce=text=>{notice.textContent=text;listNotice.textContent=text;};
  async function deleteCampaign(row, control) {
    if (row.status === 'RUNNING') {announce('모의 발송 중인 캠페인은 삭제할 수 없습니다.'); return;}
    if (control.dataset.confirm !== 'true') {
      control.dataset.confirm='true'; control.textContent='삭제 확인'; announce(`${row.name} 캠페인을 삭제하려면 삭제 확인을 한 번 더 눌러주세요.`); return;
    }
    control.disabled=true;
    try {
      await request(`/campaigns/${row.id}`,{method:'DELETE',body:{dataset_id:route.dataset,version:row.version},signal});
      announce('캠페인이 삭제되었습니다.');
      if (current?.id===row.id) {
        current=null; populate(null); review.hidden=true; reviewFlow.draw();
        if (route.resource) {navigate({resource:'',page:1}); return;}
      }
      await refreshList();
    } catch(error) {announce(errorMessage(error)); control.disabled=false; control.dataset.confirm=''; control.textContent='삭제';}
  }
  async function loadCampaignIntoWorkspace(row) {
    current=await request(`/campaigns/${row.id}?dataset_id=${route.dataset}`,{signal,validate:validDetail});
    populate(current);
    await reviewFlow.load();
    return current;
  }
  async function simulateFromList(row,control) {
    if(row.status!=='APPROVED')return;
    control.disabled=true;
    notice.textContent=`${row.name} 캠페인의 모의 발송을 준비하고 있습니다.`;
    try {
      const campaign=await loadCampaignIntoWorkspace(row);
      const started=await reviewFlow.simulate(campaign);
      if(started) {
        notice.textContent='모의 발송을 요청했습니다. 오른쪽 패널에서 진행 상황을 확인하세요.';
        await refreshList();
        navigate({view:'campaigns',resource:campaign.id,tab:'results'});
      } else notice.textContent='모의 발송을 시작하지 못했습니다. 오른쪽 패널의 오류 내용을 확인해주세요.';
    } catch(error) {
      if(!signal.aborted)notice.textContent=errorMessage(error);
    } finally {control.disabled=false;}
  }
  async function resumeFromList(row,control) {
    control.disabled=true;
    try {
      const campaign=await loadCampaignIntoWorkspace(row);
      await reviewFlow.resumeEditing(campaign);
      notice.textContent='캠페인 편집을 다시 시작했습니다. 수정 후 정책 검수를 다시 실행해주세요.';
      await refreshList();
      navigate({view:'campaigns',resource:campaign.id,tab:'compose'});
    } catch(error) {
      if(!signal.aborted)notice.textContent=errorMessage(error);
    } finally {control.disabled=false;}
  }
  const campaignStatusLabel=status=>({DRAFT:'작성 중',REVIEW:'승인 검토 중',APPROVED:'승인 완료',RUNNING:'모의 발송 중',COMPLETED:'발송 완료',FAILED:'발송 실패'}[status]||status);
  function campaignActions(row) {
    const actions=el('div',{className:'row campaign-library-actions'});
    if(row.status==='APPROVED') {
      const send=button('모의 발송',()=>simulateFromList(row,send),signal,'button campaign-action-primary');
      const resume=button('편집 재개',()=>resumeFromList(row,resume),signal,'button secondary');
      actions.append(send,resume);
    } else if(row.status==='RUNNING') {
      actions.append(el('span',{className:'badge status-running',text:'발송 진행 중'}),button('진행 상황 보기',()=>navigate({view:'campaigns',resource:row.id,tab:'results'}),signal,'button secondary'));
    } else if(row.status==='COMPLETED') {
      actions.append(el('span',{className:'campaign-action-status status-completed',text:'✓ 발송 완료'}),button('결과 보기',()=>navigate({view:'campaigns',resource:row.id,tab:'results'}),signal,'button secondary'));
    } else {
      actions.append(button(row.status==='DRAFT'?'편집':'검토 열기',()=>navigate({view:'campaigns',resource:row.id,tab:row.status==='DRAFT'?'compose':'review'}),signal));
    }
    const control=button('삭제',()=>deleteCampaign(row,control),signal,'button secondary campaign-delete');
    control.disabled=row.status==='RUNNING';
    if(control.disabled)control.title='모의 발송이 끝난 뒤 삭제할 수 있습니다.';
    actions.append(control);
    return actions;
  }
  function drawList(rows) {
    list.replaceChildren(el('h2',{text:`캠페인 ${rows.total}개`}),listNotice, ...rows.items.map(row =>
      el('article',{className:`saved-segment campaign-library-item status-${row.status.toLowerCase()}`},el('h3',{text:row.name}),
        el('p',{className:'small muted',text:`${row.channel} · ${campaignStatusLabel(row.status)}`}),campaignActions(row))),
      button('이전',() => navigate({page:Math.max(1,(route.page||1)-1)}),signal),
      button('다음',() => {if ((route.page||1)*rows.page_size < rows.total) navigate({page:(route.page||1)+1});},signal));
  }
  async function refreshList() {drawList(await request(`/campaigns?dataset_id=${route.dataset}&page=${route.page||1}`,{signal,validate:isPage(validRow)}));}
  drawList(page);
  const fingerprint=()=>JSON.stringify([current?.id,...Object.values(fields).map(input=>input.value),...[...exclusionChecks].filter(([,input])=>input.checked).map(([id])=>id)]);
  const assistant = campaignAssistant({route,signal,isBusy:()=>busy,fingerprint,
    applyFull:(data,name)=>{
      addTarget(data.segment_revision_id,name);
      populate({...data,planned_at:utcTime(fields.planned_at.value),coupon_expires_at:utcTime(fields.coupon_expires_at.value),exclusion_revision_ids:[...exclusionChecks].filter(([,input])=>input.checked).map(([id])=>id)});
      review.hidden=true;
      notice.textContent='전체 초안이 입력되었습니다. 추천값을 검토한 뒤 저장해주세요.';
    },
    setBusy:value=>{busy=value;form.inert=value;submit.disabled=value;},
  });
  const defaultTab=current&&['APPROVED','RUNNING','COMPLETED'].includes(current.status)?'results':current?.status==='REVIEW'?'review':'compose';
  const requestedTab=route.tab||defaultTab;
  const selectedTab=requestedTab==='results'&&current&&!['APPROVED','RUNNING','COMPLETED'].includes(current.status)?'compose':requestedTab==='review'&&!current?'compose':requestedTab;
  const tabList=el('nav',{className:'campaign-tabs','aria-label':'캠페인 작업 단계'});
  const tabButtons=new Map();
  for(const [id,label] of [['compose','작성'],['review','검수·승인'],['results','발송·결과']]){
    const control=button(label,()=>navigate({view:'campaigns',resource:current?.id||'',tab:id}),signal,'button campaign-tab');
    control.setAttribute('aria-current',selectedTab===id?'page':'false');tabButtons.set(id,control);tabList.append(control);
  }
  updateTabs=()=>{
    tabButtons.get('review').disabled=!current;
    tabButtons.get('results').disabled=!current||!['APPROVED','RUNNING','COMPLETED'].includes(current.status);
  };updateTabs();
  const composePanel=el('div',{className:'campaign-compose-tab',hidden:selectedTab==='compose'?null:''},el('div',{className:'campaign-compose-layout'},el('div',{className:'stack'},form,review),assistant));
  reviewFlow.panel.hidden=selectedTab!=='review';reviewFlow.resultsPanel.hidden=selectedTab!=='results';
  const activePanel=el('div',{className:'campaign-active-panel'},composePanel,reviewFlow.panel,reviewFlow.resultsPanel);
  root.replaceChildren(heading('Campaigns','캠페인 작성부터 승인과 모의 발송 결과까지 관리하세요.',button('초기화',() => {
    if (route.resource) navigate({resource:''}); else {current = null; populate(null); notice.textContent = ''; review.hidden = true;}
  },signal)),tabList,el('div',{className:'campaign-tab-workspace'},activePanel,list));
  if (!segments.total && !current) {submit.disabled = true; notice.append(stateCard('세그먼트가 필요합니다','대상 조건을 먼저 저장해주세요.',button('세그먼트 만들기',() => navigate({view:'segments',resource:''}),signal)));}
}
