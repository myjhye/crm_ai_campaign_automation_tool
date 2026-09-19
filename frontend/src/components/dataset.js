import {el} from './dom.js';

export const sourceNames = {DEMO: '공개 체험용 데이터', UPLOADED: '직접 업로드한 데이터', SIMULATED: '모의 발송으로 생성된 데이터'};
export function datasetSummary(dataset) {
  const counts = [dataset.customer_count, dataset.order_count, dataset.event_count];
  if (counts.every(x => x === 0)) return '빈 데이터셋 · CSV 업로드나 샘플 생성이 필요합니다';
  return `고객 ${counts[0].toLocaleString('ko-KR')}명 · 주문 ${counts[1].toLocaleString('ko-KR')}건 · 이벤트 ${counts[2].toLocaleString('ko-KR')}건`;
}
export function datasetCard(dataset) {
  return el('section', {className: 'card', 'aria-label': '선택한 데이터셋'},
    el('h2', {text: '선택한 데이터셋'}), el('strong', {text: dataset.name}),
    el('p', {text: datasetSummary(dataset)}),
    el('p', {className: 'metadata', text: `${sourceNames[dataset.source]} · 전체 적재 건수 (기간 필터와 별개)`}));
}
