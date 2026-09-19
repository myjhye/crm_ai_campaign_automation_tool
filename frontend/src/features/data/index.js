import {datasets} from '../../api/client.js';
import {navigate} from '../../app/router.js';
import {el, button, heading, stateCard, errorMessage, formatTime} from '../../components/dom.js';
import {sourceChart} from '../../components/chart.js';

function nameForm({row, signal, refresh}) {
  const input = el('input', {type: 'text', required: '', maxlength: '200', value: row?.name || '', placeholder: '예: 가을 캠페인 실험'});
  const submit = el('button', {className: row ? 'button secondary' : 'button', type: 'submit', text: row ? '이름 저장' : '데이터셋 만들기'});
  const status = el('div', {className: 'inline-message', role: 'status'});
  const recovery = el('div');
  const form = el('form', {}, el('div', {className: 'form-row'}, el('label', {text: row ? '데이터셋 이름 변경' : '새 공개 데이터셋 이름'}, input), submit), status, recovery);
  input.addEventListener('input', () => input.setCustomValidity(''), {signal});
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const name = input.value.trim();
    input.setCustomValidity(name ? '' : '이름을 입력해주세요.');
    if (!form.reportValidity()) return;
    submit.disabled = true; submit.textContent = '저장 중…'; status.textContent = '변경 내용을 저장하고 있습니다.'; recovery.replaceChildren();
    try {
      const saved = row ? await datasets.rename(row, name, signal) : await datasets.create(name, signal);
      if (signal.aborted) return;
      document.getElementById('announcement').textContent = '데이터셋을 저장했습니다.';
      refresh(saved.id);
    } catch (error) {
      if (error.name === 'AbortError') return;
      status.textContent = errorMessage(error); status.classList.add('error');
      if (error.status === 409) recovery.append(button('최신 데이터 불러오기', () => refresh(row.id), signal));
    } finally {
      submit.disabled = false; submit.textContent = row ? '이름 저장' : '데이터셋 만들기';
    }
  }, {signal});
  return form;
}

export async function renderData(root, route, selected, signal, refresh) {
  const page = await datasets.list(route.page, signal);
  if (signal.aborted) return;
  const query = route.q.trim().toLocaleLowerCase();
  const items = page.items.filter(row => row.name.toLocaleLowerCase().includes(query));
  const search = el('input', {type: 'search', maxlength: '200', value: route.q, placeholder: '데이터셋 이름'});
  const searchForm = el('form', {className: 'toolbar'}, el('label', {text: '현재 페이지에서 검색'}, search), el('button', {className: 'button secondary', text: '검색', type: 'submit'}));
  searchForm.addEventListener('submit', event => {event.preventDefault(); navigate({q: search.value});}, {signal});
  root.replaceChildren(heading('Data & Integrations', '공개 데이터셋을 선택하고 체험할 데이터를 준비하세요.'),
    el('div', {className: 'stack'},
      el('p', {className: 'notice', text: '이 공간의 데이터는 다른 방문자와 공유됩니다. 합성 데이터만 사용해주세요. 새 데이터셋은 빈 상태로 생성됩니다.'}),
      el('section', {className: 'card'}, el('h2', {className: 'card-header', text: '새로운 실험 공간'}), nameForm({signal, refresh})),
      el('section', {className: 'card'}, el('div', {className: 'row spread card-header'}, el('h2', {text: `데이터셋 · ${page.total.toLocaleString()}개`}), el('span', {className: 'badge', text: '실제 API 연결'})), searchForm),
    ));
  const stack = root.querySelector('.stack');
  if (!items.length) stack.append(stateCard(page.total ? '표시할 데이터셋이 없습니다' : '첫 데이터셋을 만들어보세요',
    page.total ? '검색어를 지우거나 이전 페이지로 이동해보세요.' : '위 입력창에서 빈 데이터셋을 생성할 수 있습니다.'));
  for (const row of items) {
    stack.append(el('article', {className: 'card'},
      el('div', {className: 'row spread'}, el('h2', {className: 'dataset-name', text: row.name}), el('span', {className: 'badge', text: row.id === selected?.id ? '선택됨' : row.source})),
      el('p', {className: 'metadata', text: `ID ${row.id} · 이름 버전 ${row.version}`}),
      el('p', {className: 'metadata', text: `데이터 기준 시점: ${formatTime(row.reference_at)}`}),
      button('이 데이터셋 선택', () => navigate({dataset: row.id}), signal, 'button ghost'),
      el('div', {style: 'margin-top:18px'}, nameForm({row, signal, refresh})),
    ));
  }
  if (items.length) stack.append(sourceChart(items));
  const lastPage = Math.max(1, Math.ceil(page.total / page.page_size));
  const prev = button('이전', () => navigate({page: Math.max(1, route.page - 1)}), signal);
  const next = button('다음', () => navigate({page: route.page + 1}), signal);
  prev.disabled = route.page <= 1; next.disabled = route.page >= lastPage;
  stack.append(el('nav', {className: 'pagination', 'aria-label': '데이터셋 페이지'}, prev, el('span', {className: 'small', text: `${route.page} / ${lastPage} 페이지`}), next),
    stateCard('CSV 업로드 화면은 준비 중입니다', 'CSV 미리보기·확정 적재 API는 구현되어 있습니다. 화면 연결 전에는 API 문서에서 계약을 확인할 수 있습니다.', el('a', {className: 'button secondary', href: '/docs', text: 'API 문서 열기'})));
}
