import {el} from '../../components/dom.js';
import {formatMoney} from '../dashboard/index.js';
const categories = {fashion: '패션', home: '홈·리빙', sports: '스포츠', beauty: '뷰티', electronics: '전자제품', food: '식품'};
export function formatReferenceLabel(value) {
  const date = new Date(value);
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(date).map(part => [part.type, part.value]));
  const time = parts.hour === '00' && parts.minute === '00' && parts.second === '00'
    ? '자정' : `${parts.hour}:${parts.minute}${parts.second === '00' ? '' : `:${parts.second}`}`;
  return `${parts.year}년 ${Number(parts.month)}월 ${Number(parts.day)}일 ${time} 기준`;
}
export function renderPreview(preview) {
  const metric = (label, value, note) => el('div', {className: 'preview-metric'}, el('dt', {text: label}),
    el('dd', {}, el('span', {text: value}), note ? el('p', {className: 'preview-metric-note', text: note}) : null));
  return el('section', {className: 'segment-preview', 'aria-label': '세그먼트 미리보기'},
    el('header', {className: 'preview-heading'}, el('h3', {text: `대상 고객 ${preview.count.toLocaleString('ko-KR')}명`}),
      el('p', {className: 'small muted', text: preview.percentage === null ? '전체 고객이 없어 비중을 계산할 수 없습니다.' : `전체 ${preview.total.toLocaleString('ko-KR')}명 중 ${preview.percentage}%`})),
    el('dl', {className: 'preview-metrics'},
      metric('평균 누적 구매액', preview.profile.average_purchase_amount === null ? '자료 없음' : formatMoney(preview.profile.average_purchase_amount)),
      metric('최근 30일 이메일을 연 고객', `${preview.profile.email_open_customers_30d.toLocaleString('ko-KR')}명`,
        preview.profile.email_open_customers_30d === 0 ? '선택한 고객의 최근 30일 이메일 오픈 기록이 없습니다. 실제 발송·수신 여부와는 별개입니다.' : null)),
    el('div', {className: 'preview-categories'}, el('h4', {text: '선호 카테고리'}),
      preview.profile.categories.length ? el('ul', {}, ...preview.profile.categories.map(row => el('li', {},
        el('span', {text: categories[row.category] || row.category, title: row.category}),
        el('strong', {text: `${row.count.toLocaleString('ko-KR')}명`})
      ))) : el('p', {className: 'small muted', text: '구매 카테고리 자료가 없습니다.'})),
    el('section', {className: 'preview-condition'}, el('h4', {text: '적용된 조건'}), el('p', {text: preview.description})),
    ...preview.warnings.map(warning => el('p', {className: 'notice', text: warning === 'EMPTY_SEGMENT' ? '대상자가 없습니다. 조건은 저장할 수 있습니다.' : '전체 고객의 80%를 넘습니다. 조건을 확인해주세요.'})),
    el('p', {className: 'metadata', text: `${formatReferenceLabel(preview.reference_at)} · 발송 적격 검수 전`, title: '한국 시간 기준입니다. 이메일 동의는 현재 저장 상태를 사용합니다.'}));
}
