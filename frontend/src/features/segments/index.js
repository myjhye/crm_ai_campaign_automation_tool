import {renderPreview} from './preview.js';
import {segments} from '../../api/segments.js';
import {el, button, heading, stateCard, errorMessage, formatTime} from '../../components/dom.js';
import {navigate, apiPeriod} from '../../app/router.js';
import {vipTemplate, parseValue, segmentTemplates, templateCondition} from './condition.js';
import {toSeoulInput, fromSeoulInput} from './reference.js';

let pendingNotice = null;
const emptyCondition = () => ({operator: 'AND', conditions: [{field: 'order_count', comparison: 'GTE', value: 0}]});

const comparisons = {EQ: '같음', NEQ: '다름', GT: '초과', GTE: '이상', LT: '미만', LTE: '이하', BETWEEN: '범위', IN: '중 하나', NOT_IN: '제외', IS_NULL: '값 없음', IS_NOT_NULL: '값 있음'};
function choose(options, selected, label) {
  const node = el('select', {'aria-label': label}, ...options.map(([value, text]) => el('option', {value, text})));
  node.value = selected; return node;
}
export async function renderSegments(root, route, signal) {
  const [{items: fields}, page, saved] = await Promise.all([
    segments.fields(signal), segments.list(route.dataset, route.page, signal), route.resource ? segments.get(route.dataset, route.resource, signal) : Promise.resolve(null),
  ]);
  if (signal.aborted) return;
  let condition = saved ? structuredClone(saved.condition) : emptyCondition();
  if (!condition.operator) condition = {operator: 'AND', conditions: [condition]};
  let preview = null, busy = false;
  const name = el('input', {value: saved?.name || '', maxlength: 200, required: '', placeholder: '예: 휴면 VIP', 'aria-label': '세그먼트 이름'});
  const reference = el('input', {type: 'datetime-local', step: 'any', min: '1900-01-01T00:00', max: '9998-12-31T23:59:59', value: toSeoulInput(saved?.reference_at || apiPeriod(route.from, route.to).to), required: '', 'aria-label': '기준 시점 (한국 시간)'});
  const editor = el('div', {className: 'condition-editor'}), result = el('div'), message = el('p', {className: 'inline-message', role: 'status'});
  const save = button('세그먼트 저장', saveAction, signal); save.disabled = true;
  const previewButton = button('대상 미리보기', previewAction, signal);
  const controls = el('fieldset', {className: 'segment-controls'});
  function invalidate() {
    preview = null; save.disabled = true; result.replaceChildren();
    controls.querySelectorAll('.segment-template-button').forEach(node => node.setAttribute('aria-pressed', 'false'));
  }
  reference.addEventListener('input', invalidate, {signal});
  function leafCount(node) {return node.operator ? node.conditions.reduce((n, child) => n + leafCount(child), 0) : 1;}
  function draw(node, depth = 1) {
    if (node.operator) {
      const operator = choose([['AND', '모든 조건 만족 (AND)'], ['OR', '하나 이상 만족 (OR)']], node.operator, '조건 결합');
      operator.addEventListener('change', () => {node.operator = operator.value; invalidate();}, {signal});
      const add = button('조건 추가', () => {if (leafCount(condition) >= 20) return; node.conditions.push({field: fields[0].name, comparison: 'GTE', value: 0}); redraw();}, signal);
      const group = button('그룹 추가', () => {if (leafCount(condition) >= 20) return; node.conditions.push({operator: 'OR', conditions: [{field: 'order_count', comparison: 'GTE', value: 1}]}); redraw();}, signal);
      group.disabled = depth >= 3 || leafCount(condition) >= 20; add.disabled = leafCount(condition) >= 20;
      return el('fieldset', {className: 'condition-group'}, el('legend', {text: depth === 1 ? '대상 조건' : '조건 그룹'}), operator,
        ...node.conditions.map((child, index) => el('div', {className: 'condition-entry'}, draw(child, depth + (child.operator ? 1 : 0)), button('삭제', () => {if (node.conditions.length > 1) {node.conditions.splice(index, 1); redraw();}}, signal))),
        el('div', {className: 'row'}, add, group));
    }
    const field = fields.find(spec => spec.name === node.field);
    const fieldSelect = choose(fields.map(spec => [spec.name, spec.label]), node.field, '조건 필드');
    const comparison = choose(field.comparisons.map(value => [value, comparisons[value]]), node.comparison, '비교 연산자');
    let input;
    if (field.type === 'boolean') input = choose([['true', '동의'], ['false', '미동의']], String(node.value), '조건 값');
    else if (field.type === 'status' && ['EQ', 'NEQ'].includes(node.comparison)) input = choose([['ACTIVE', '활성'], ['CHURN_RISK', '이탈 위험'], ['DORMANT', '휴면'], ['WITHDRAWN', '탈퇴']], node.value, '조건 값');
    else input = el('input', {'aria-label': '조건 값', value: Array.isArray(node.value) ? node.value.join(', ') : node.value ?? '', placeholder: '범위·목록은 쉼표로 구분'});
    input.disabled = ['IS_NULL', 'IS_NOT_NULL'].includes(node.comparison);
    input.addEventListener('input', () => {invalidate(); try {node.value = parseValue(input.value, field.type, node.comparison); input.setCustomValidity('');} catch (error) {input.setCustomValidity(error.message);}}, {signal});
    fieldSelect.addEventListener('change', () => {
      const next = fields.find(spec => spec.name === fieldSelect.value);
      Object.assign(node, {field: next.name, comparison: next.comparisons[0], value: next.type === 'boolean' ? true : next.type === 'status' ? 'ACTIVE' : next.type === 'integer' ? 0 : next.type === 'money' ? '0' : ''}); redraw();
    }, {signal});
    comparison.addEventListener('change', () => {
      node.comparison = comparison.value;
      if (['IS_NULL', 'IS_NOT_NULL'].includes(node.comparison)) delete node.value;
      else {
        const fallback = field.type === 'integer' ? 0 : field.type === 'money' ? '0' : field.type === 'status' ? 'ACTIVE' : '';
        const current = Array.isArray(node.value) ? node.value[0] : node.value ?? fallback;
        node.value = ['IN', 'NOT_IN', 'BETWEEN'].includes(node.comparison) ? (node.comparison === 'BETWEEN' ? [current, current] : [current]) : current;
      }
      redraw();
    }, {signal});
    return el('div', {className: 'condition-row'}, fieldSelect, comparison, input);
  }
  function redraw() {invalidate(); editor.replaceChildren(draw(condition));}
  function body() {return {dataset_id: route.dataset, condition, reference_at: fromSeoulInput(reference.value)};}
  async function run(action) {
    if (busy) return;
    busy = true; controls.disabled = true; message.textContent = '';
    try {await action();} catch (error) {if (!signal.aborted) {message.textContent = errorMessage(error); if (error.status === 409) {invalidate(); result.replaceChildren(button('최신 내용 불러오기', () => window.dispatchEvent(new Event('hashchange')), signal));}}}
    finally {busy = false; if (!signal.aborted) controls.disabled = Boolean(saved?.archived_at);}
  }
  async function previewAction() {
    if (!reference.reportValidity() || ![...editor.querySelectorAll('input')].every(input => input.reportValidity())) return;
    await run(async () => {
      preview = await segments.preview(body(), signal); if (signal.aborted) return;
      save.disabled = false;
      result.replaceChildren(renderPreview(preview));    });
  }
  async function saveAction() {
    if (!preview || !name.reportValidity()) return;
    await run(async () => {
      const row = await segments.save(saved?.id, {...body(), name: name.value, data_version: preview.data_version, ...(saved ? {version: saved.version} : {})}, signal);
      if (!signal.aborted) {
        pendingNotice = {dataset: route.dataset, text: `세그먼트 ‘${row.name}’이 저장되었습니다.`};
        if (route.resource === row.id) window.dispatchEvent(new Event('hashchange')); else navigate({view: 'segments', resource: row.id, page: 1});
      }
    });
  }
  redraw();
  const templateStatus = el('p', {className: 'small muted', role: 'status'});
  const templateButtons = segmentTemplates.map(selected => {
    const node = button(selected.label, () => {
      condition = templateCondition(selected.id);
      name.value = selected.label;
      redraw();
      for (const item of templateButtons) item.setAttribute('aria-pressed', String(item === node));
      templateStatus.textContent = `${selected.label} 이름과 조건을 입력했습니다. 대상 미리보기로 고객 수를 확인하세요.`;
      message.textContent = '';
    }, signal, 'segment-template-button');
    node.setAttribute('aria-pressed', 'false');
    node.setAttribute('aria-label', selected.label);
    node.setAttribute('title', selected.description);
    node.replaceChildren(el('strong', {text: selected.label}));
    return node;
  });
  async function deleteSegment(row) {
    await run(async () => {
      await segments.archive(row, signal);
      if (signal.aborted) return;
      pendingNotice = {dataset: route.dataset, text: `세그먼트 ‘${row.name}’이 삭제되었습니다. 기존 이력은 보존됩니다.`};
      if (route.resource === row.id || route.page !== 1) navigate({resource: route.resource === row.id ? '' : route.resource, page: 1});
      else window.dispatchEvent(new Event('hashchange'));
    });
  }
  const recommendations = el('details', {className: 'segment-recommendations'},
    el('summary', {text: '추천 고객 유형'}),
    el('section', {'aria-label': '추천 고객 유형'},
      el('p', {className: 'small muted', text: '클릭하면 이름·조건이 채워집니다.'}),
      el('div', {className: 'segment-template-list'}, ...templateButtons)));
  recommendations.open = window.matchMedia('(min-width: 1101px)').matches;
  function setReference(instant) {reference.value = toSeoulInput(instant); invalidate();}
  controls.append(
    el('div', {className: 'segment-meta'}, el('label', {text: '세그먼트 이름'}, name),
      el('div', {}, el('label', {text: '기준 시점 (한국 시간)'}, reference),
        el('div', {className: 'reference-shortcuts'},
          button('현재 시각', () => setReference(new Date().toISOString()), signal, 'button ghost'),
          button('선택 기간 종료', () => setReference(apiPeriod(route.from, route.to).to), signal, 'button ghost')),
        el('p', {className: 'small muted', text: '선택한 시각 이전 데이터를 계산합니다. 기간 종료는 종료일 다음 날 00:00입니다.'}))),
    el('div', {className: 'segment-editor-layout'}, recommendations, editor),
    el('div', {className: 'row'}, previewButton, save), templateStatus);
  controls.disabled = Boolean(saved?.archived_at);
  const previous = button('이전', () => navigate({page: route.page - 1}), signal); previous.disabled = route.page <= 1;
  const next = button('다음', () => navigate({page: route.page + 1}), signal); next.disabled = route.page * page.page_size >= page.total;
  function reset() {
    if (busy) return;
    pendingNotice = null;
    if (route.resource) {navigate({resource: '', page: 1}); return;}
    condition = emptyCondition(); name.value = '';
    reference.value = toSeoulInput(apiPeriod(route.from, route.to).to);
    message.textContent = ''; templateStatus.textContent = ''; redraw();
    root.querySelector('.segment-success')?.remove();
    name.focus();
  }
  const success = pendingNotice?.dataset === route.dataset ? el('div', {className: 'segment-success', role: 'status'},
    el('strong', {text: '완료'}), el('span', {text: pendingNotice.text})) : document.createTextNode('');
  pendingNotice = null;
  root.replaceChildren(heading('Segments', '조건으로 고객을 찾고 캠페인 대상을 저장하세요.', button('초기화', reset, signal)), success,
    saved?.archived_at ? stateCard('보관된 세그먼트', '기존 조건은 이력으로 유지됩니다.') : document.createTextNode(''),
    el('div', {className: 'segments-workspace'},
      el('section', {className: 'card stack segment-compose', 'aria-label': '세그먼트 편집'}, controls, message, result),
      el('section', {className: 'card stack segment-library', 'aria-label': '저장된 세그먼트'}, el('h2', {text: `저장된 세그먼트 ${page.total}개`}),
        ...page.items.map(row => el('article', {className: `saved-segment ${route.resource === row.id ? 'is-selected' : ''}`},
          el('h3', {text: row.name}),
          el('p', {className: 'saved-segment-description', text: row.description}),
          el('p', {className: 'metadata', text: `${formatTime(row.reference_at)} 기준`}),
          el('div', {className: 'row'}, button('불러오기', () => navigate({resource: row.id}), signal),
            button('삭제', () => deleteSegment(row), signal, 'button segment-delete')))),
        page.total === 0 ? el('p', {className: 'small muted', text: '저장된 세그먼트가 없습니다. 왼쪽에서 조건을 만들고 저장하세요.'}) : null,
        el('div', {className: 'row'}, previous, next))));
}
