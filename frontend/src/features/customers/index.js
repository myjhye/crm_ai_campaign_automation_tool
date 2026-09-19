import {analytics} from '../../api/analytics.js';
import {el, button, heading, formatTime, stateCard} from '../../components/dom.js';
import {navigate, routeHash} from '../../app/router.js';
import {statusNames, formatMoney} from '../dashboard/index.js';

function select(name, entries, value) {
  const node = el('select', {name}, ...entries.map(([id, label]) => el('option', {value: id, text: label}))); node.value = value; return node;
}
function pagination(route, total, pageSize, signal) {
  const previous = button('이전', () => navigate({page: route.page - 1}), signal);
  const next = button('다음', () => navigate({page: route.page + 1}), signal);
  previous.disabled = route.page <= 1; next.disabled = route.page * pageSize >= total;
  return el('nav', {className: 'pagination', 'aria-label': '고객 데이터 페이지'}, previous, el('span', {text: `${route.page} / ${Math.max(1, Math.ceil(total / pageSize))} 페이지`}), next);
}
export async function renderCustomers(root, route, signal) {
  if (route.resource) return renderDetail(root, route, signal);
  const result = await analytics.customers(route, signal); if (signal.aborted) return;
  const search = el('input', {name: 'q', type: 'search', value: route.q, maxlength: '200', placeholder: '이름·이메일·외부 ID'});
  const form = el('form', {className: 'toolbar'},
    el('label', {text: '고객 검색'}, search),
    el('label', {text: '고객 상태'}, select('status', [['', '모든 상태'], ...Object.entries(statusNames)], route.status || '')),
    el('label', {text: '기간 활동'}, select('cohort', [['all', '전체'], ['new', '신규 가입'], ['active', '활성 고객'], ['purchased', '구매 고객'], ['repeat', '재구매 고객'], ['view', '퍼널: 조회'], ['cart', '퍼널: 장바구니'], ['purchase', '퍼널: 구매']], route.cohort || 'all')),
    el('label', {text: '가입 시작일'}, el('input', {type: 'date', name: 'signup_from', value: route.signup_from || ''})),
    el('label', {text: '가입 종료일'}, el('input', {type: 'date', name: 'signup_to', value: route.signup_to || ''})),
    el('label', {text: '정렬 기준'}, select('sort', [['signup_at', '가입일'], ['name', '이름'], ['total_purchase_amount', '구매 합계'], ['order_count', '주문 수']], route.sort || 'signup_at')),
    el('label', {text: '정렬 방향'}, select('direction', [['desc', '내림차순'], ['asc', '오름차순']], route.direction || 'desc')),
    el('button', {className: 'button', type: 'submit', text: '고객 조회'}));
  form.addEventListener('submit', event => {event.preventDefault(); navigate({...Object.fromEntries(new FormData(form)), page: 1});}, {signal});
  const table = el('table', {}, el('thead', {}, el('tr', {}, ...['고객', '이메일', '상태', '구매 합계', '주문 수', '최근 구매'].map(text => el('th', {scope: 'col', text})))),
    el('tbody', {}, ...result.items.map(row => el('tr', {},
      el('td', {}, el('a', {href: routeHash({...route, resource: row.id, page: 1}), text: row.name || row.external_id})),
      el('td', {text: row.email || '없음'}), el('td', {text: statusNames[row.status]}),
      el('td', {text: formatMoney(row.total_purchase_amount)}), el('td', {text: row.order_count}), el('td', {text: row.last_purchase_at ? formatTime(row.last_purchase_at) : '미구매'})))));
  root.replaceChildren(heading('Customers', `조건에 맞는 고객 ${result.total.toLocaleString()}명 · 데이터 버전 ${result.data_version}`),
    el('section', {className: 'card stack'}, form, el('p', {className: 'small muted', text: '구매 합계·상태는 상단 종료일 기준입니다. 기간 활동과 가입일 필터는 별도로 적용됩니다.'}),
      result.items.length ? el('div', {className: 'table-scroll'}, table) : stateCard('조건에 맞는 고객이 없습니다', '검색어·상태·기간을 변경해보세요.'), pagination(route, result.total, result.page_size, signal)));
}
async function renderDetail(root, route, signal) {
  const result = await analytics.detail(route, signal);
  const [events, deliveries, segments] = await Promise.all([analytics.events(route, result.data_version, signal), analytics.history(route, 'deliveries', result.data_version, signal), analytics.history(route, 'segments', result.data_version, signal)]);
  if (signal.aborted) return;
  const c = result.customer;
  const rows = [['이메일', c.email || '없음'], ['상태', statusNames[c.status]], ['가입일', formatTime(c.signup_at)],
    ['구매 합계', formatMoney(c.total_purchase_amount)], ['주문 수', c.order_count],
    ['평균 주문액', c.average_order_amount === null ? '미구매' : formatMoney(c.average_order_amount)],
    ['최근 구매', c.last_purchase_at ? formatTime(c.last_purchase_at) : '미구매'], ['선호 카테고리', result.preferred_category || '집계 자료 없음'],
    ['RFM', `R ${result.rfm.recency} / F ${result.rfm.frequency} / M ${result.rfm.monetary} · ${result.rfm.version}`]];
  root.replaceChildren(heading(c.name || c.external_id, `고객 상세 · 데이터 버전 ${result.data_version}`, button('고객 목록으로', () => navigate({resource: '', page: 1}), signal)),
    el('div', {className: 'stack'}, el('section', {className: 'card'}, el('h2', {text: '고객 프로필'}), el('table', {}, el('tbody', {}, ...rows.map(([label, value]) => el('tr', {}, el('th', {scope: 'row', text: label}), el('td', {text: value})))))),
      el('section', {className: 'card'}, el('h2', {text: '채널 수신 상태'}), el('p', {className: 'metadata', text: '채널 동의는 현재 저장 상태입니다. 과거 시점의 동의 이력은 복원하지 않습니다.'}),
        ...result.channels.map(ch => el('p', {text: `${ch.channel}: ${ch.consent ? '동의' : '미동의'} · 연락처 ${ch.is_valid ? '유효' : '무효 또는 없음'} · hard bounce ${ch.hard_bounce ? '있음' : '없음'}`}))),
      el('section', {className: 'card'}, el('h2', {text: '선택 기간의 행동 타임라인'}),
        events.items.length ? el('ol', {className: 'workflow'}, ...events.items.map(e => el('li', {}, el('div', {}, el('strong', {text: e.event_type}), el('p', {text: formatTime(e.event_at)}))))) : el('p', {className: 'metadata', text: '기간 내 이벤트가 없습니다.'}), pagination(route, events.total, events.page_size, signal)),
      stateCard('발송 이력·피로도·세그먼트 소속 준비 중', '관련 업무 테이블이 추가되면 실제 이력을 연결합니다. 현재는 발송 0회나 소속 없음으로 판단하지 않습니다.')));
}
