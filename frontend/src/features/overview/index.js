import {el, button, heading, formatTime} from '../../components/dom.js';
import {navigate} from '../../app/router.js';
import {datasetSummary, sourceNames} from '../../components/dataset.js';

export function renderOverview(root, selected, total, signal) {
  root.replaceChildren(heading('Overview', '고객을 이해하고, 다음 캠페인을 준비하세요.', el('span', {className: 'badge', text: '공개 데모'})),
    el('section', {className: 'hero'}, el('span', {className: 'eyebrow', text: 'FROM DATA TO ACTION'}),
      el('h2', {text: selected ? '성장을 만드는 다음 한 걸음.' : '체험용 샘플을 만드시겠어요?'}), el('p', {text: '준비된 분석용 데이터가 없다면 데이터 관리에서 데이터셋을 만들 수 있습니다. CSV 적재 또는 샘플 생성이 완료되면 여기에서 고객과 주문을 살펴볼 수 있습니다.'}),
      button('데이터셋 살펴보기 →', () => navigate({view: 'data', resource: '', page: 1, q: ''}), signal, 'button')),
    el('section', {className: 'grid metric-grid', 'aria-label': '현재 연결 상태'},
      metric('공개 데이터셋', total.toLocaleString(), '현재 서버에 등록된 데이터셋'),
      metric('선택한 데이터셋', selected?.name || '선택 없음', selected ? `${sourceNames[selected.source]} · ${datasetSummary(selected)}` : '데이터셋을 만들어 시작하세요.'),
      metric('고객·구매 지표', '집계 연결 예정', '고객·대시보드 단계에서 제공', true),
      metric('캠페인 성과', '아직 제공되지 않음', '모의 발송·성과 집계 연결 후 제공', true)),
    el('section', {className: 'card'}, el('div', {className: 'row spread'}, el('h2', {text: '데이터에서 캠페인까지'}), el('span', {className: 'badge', text: '구현 예정 흐름'})),
      el('ol', {className: 'workflow'},
        step('데이터 준비', '공개 데이터셋 선택·생성·이름 변경을 지금 사용할 수 있습니다.'),
        step('고객 이해와 타깃 설정', '고객 지표를 확인하고 조건에 맞는 세그먼트를 만듭니다.'),
        step('AI와 함께 초안 작성', '자연어로 조회하고 캠페인 카피를 제안받습니다.'),
        step('검수, 승인, 그리고 실험', '방문자가 검토한 뒤 모의 발송하고 성과를 비교합니다.'))),
    el('p', {className: 'metadata', text: `선택 데이터의 기준 시점: ${formatTime(selected?.reference_at)} · 기간은 한국 시간 기준입니다. 현재 조회 조건은 URL에 보존됩니다.`}));
}
function metric(label, value, note, unavailable = false) {
  return el('article', {className: 'card'}, el('p', {className: 'metric-label', text: label}),
    el('strong', {className: `metric-value ${unavailable ? 'unavailable' : ''}`, text: value}), el('p', {className: 'metric-note', text: note}));
}
function step(title, description) {return el('li', {}, el('div', {}, el('h3', {text: title}), el('p', {text: description})));}
