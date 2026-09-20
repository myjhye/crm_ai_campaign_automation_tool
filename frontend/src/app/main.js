import {renderSegments} from '../features/segments/index.js';
import {renderCampaigns} from '../features/campaigns/index.js';
import {renderAI} from '../features/ai/index.js';
import {renderDashboard} from '../features/dashboard/index.js';
import {renderCustomers} from '../features/customers/index.js';
import {datasets} from '../api/client.js';
import {pages, startRouter, navigate, routeHash, apiPeriod, defaultPeriod} from './router.js';
import {store} from './store.js';
import {el, button, heading, loading, stateCard, errorMessage, formatTime} from '../components/dom.js';
import {renderData} from '../features/data/index.js';
import {renderOverview} from '../features/overview/index.js';
import {renderSettings} from '../features/settings/index.js';
import {renderReports} from '../features/reports/index.js';
import {renderExperiments} from '../features/experiments/index.js';

const content = document.getElementById('content');
const selector = document.getElementById('dataset-select');
const fromInput = document.getElementById('period-from');
const toInput = document.getElementById('period-to');
const filterMessage = document.getElementById('filter-message');
let currentRequest;
let firstRender = true;
let hasRenderedContent = false;
let displayedView = null;

function refresh(dataset) {
  const route = store.get().route;
  if (dataset !== route.dataset) navigate({dataset, page: 1, q: ''});
  else window.dispatchEvent(new Event('hashchange'));
}

async function render(route) {
  content.classList.toggle('ai-page', route.view === 'ai');
  currentRequest?.abort();
  currentRequest = new AbortController();
  const {signal} = currentRequest;
  store.set({route, loading: true, selectedDataset: null, error: null});
  if (!hasRenderedContent) content.replaceChildren(loading());
  content.setAttribute('aria-busy', 'true');
  // Keep the previous view visible until the next renderer has its data.
  // Its listeners were aborted above, so prevent interaction with stale controls.
  content.inert = true;
  if (!hasRenderedContent) selector.disabled = true;
  fromInput.value = route.from; toInput.value = route.to;
  fromInput.setCustomValidity(''); toInput.setCustomValidity('');
  filterMessage.textContent = 'Asia/Seoul · 종료일 포함';
  const title = pages.find(([id]) => id === route.view)?.[1] || '페이지 없음';
  document.title = `${title} · GrowthPilot`;
  document.getElementById('breadcrumb').textContent = title;
  document.getElementById('navigation').replaceChildren(...pages.map(([id, label, icon]) =>
    el('a', {id: id === 'ai' ? 'ai-page-link' : null, className: 'nav-link', href: routeHash({...route, view: id, resource: '', page: 1, q: ''}), 'aria-current': route.view === id ? 'page' : null},
      el('span', {className: 'nav-icon', 'aria-hidden': 'true', text: icon}), el('span', {text: label}))));
  try {
    if (route.issues.length) {
      content.replaceChildren(stateCard('주소를 확인해주세요', route.issues.join(' '), button('첫 화면으로', () => navigate({view: 'overview', dataset: '', resource: '', page: 1, q: '', ...defaultPeriod()}, {replace: true}), signal), true));
      hasRenderedContent = true;
      return;
    }
    if (location.hash !== routeHash(route)) { navigate({}, {replace: true}); return; }
    const page = await datasets.list(1, signal, 100);
    if (signal.aborted) return;
    let selected = page.items.find(row => row.id === route.dataset) || null;
    selector.replaceChildren(el('option', {value: '', text: page.total ? '데이터셋 선택' : '등록된 데이터셋 없음'}),
      ...page.items.map(row => el('option', {value: row.id, text: row.name})));
    selector.disabled = false;
    if (route.dataset && !selected) selected = await datasets.get(route.dataset, signal);
    if (signal.aborted) return;
    if (!route.dataset && page.items.length) {navigate({dataset: page.items[0].id}, {replace: true}); return;}
    if (selected && !page.items.some(row => row.id === selected.id)) selector.append(el('option', {value: selected.id, text: selected.name}));
    selector.value = selected?.id || '';
    store.set({selectedDataset: selected});
    if (page.total > 100) filterMessage.textContent += ' · 선택 목록은 첫 100개, 전체는 Data 메뉴에서 확인';
    if (route.view === 'ai') renderAI(content, signal);
    else if (route.view === 'customers' && selected) await renderCustomers(content, route, signal);
    else if (route.view === 'segments' && selected) await renderSegments(content, route, signal);
    else if (route.view === 'campaigns' && selected) await renderCampaigns(content, route, signal);
    else if (route.view === 'settings' && selected) await renderSettings(content, route, signal);
    else if (route.view === 'reports' && selected) await renderReports(content, route, signal);
    else if (route.view === 'experiments' && selected) await renderExperiments(content, route, signal);
    else if (route.resource) content.replaceChildren(heading(title, `리소스 ${route.resource}`), stateCard('상세 화면 준비 중', '주소의 리소스 ID는 유지됩니다. 이 업무의 상세 조회 API가 연결되면 내용을 표시합니다.', button('목록으로', () => navigate({resource: ''}), signal)));
    else if (route.view === 'overview' && selected) await renderDashboard(content, route, selected, signal);
    else if (route.view === 'overview') renderOverview(content, selected, page.total, signal);
    else if (route.view === 'data') await renderData(content, route, selected, signal, refresh);
    else {
      const descriptions = {
        customers: '고객 목록·상세 프로필·구매 지표를 연결할 예정입니다.',
        segments: '조건 빌더와 대상자 미리보기를 연결할 예정입니다.',
        campaigns: '캠페인 초안·카피 편집·검수·승인 흐름을 연결할 예정입니다.',
        experiments: 'A/B 배정과 실제 모의 발송 결과를 연결할 예정입니다.',
        reports: '성과 집계와 보고서 내보내기를 연결할 예정입니다.',
        settings: '채널별 검수 정책과 브랜드 가이드 편집을 연결할 예정입니다.',
      };
      content.replaceChildren(heading(title, descriptions[route.view]),
        stateCard('업무 기능 연결 준비 중', '현재 공통 화면과 데이터셋 관리를 사용할 수 있습니다. 아직 없는 지표나 실행 결과는 표시하지 않습니다.', button('데이터셋 관리로 이동', () => navigate({view: 'data', page: 1, q: ''}), signal)),
        el('p', {className: 'metadata', text: `선택 데이터: ${selected?.name || '없음'} · 기준 시점: ${formatTime(selected?.reference_at)}`}));
    }
    if (!signal.aborted) hasRenderedContent = true;
  } catch (error) {
    if (error.name === 'AbortError' || signal.aborted) return;
    store.set({error});
    content.replaceChildren(stateCard('데이터를 불러오지 못했습니다', errorMessage(error),
      el('div', {className: 'row', style: 'justify-content:center'}, button('다시 시도', () => refresh(route.dataset), signal),
        error.status === 404 ? button('데이터셋 다시 선택', () => navigate({dataset: '', resource: ''}, {replace: true}), signal) : null), true));
    hasRenderedContent = true;
  } finally {
    if (!signal.aborted) {
      store.set({loading: false}); content.removeAttribute('aria-busy'); content.inert = false;
      if (!firstRender && displayedView !== route.view) content.focus({preventScroll: true});
      if (hasRenderedContent) displayedView = route.view;
      firstRender = false;
    }
  }
}

selector.addEventListener('change', () => {if (selector.value) navigate({dataset: selector.value, page: 1, q: '', resource: ''});});
document.getElementById('period-form').addEventListener('submit', event => {
  event.preventDefault(); toInput.setCustomValidity('');
  try {apiPeriod(fromInput.value, toInput.value);}
  catch (error) {toInput.setCustomValidity(error.message); toInput.reportValidity(); return;}
  navigate({from: fromInput.value, to: toInput.value, page: 1});
});
for (const input of [fromInput, toInput]) input.addEventListener('input', () => toInput.setCustomValidity(''));
startRouter(render);
window.addEventListener('pagehide', () => {currentRequest?.abort();});
window.addEventListener('pageshow', event => {if (event.persisted) window.dispatchEvent(new Event('hashchange'));});
