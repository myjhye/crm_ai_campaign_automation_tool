import {analytics} from '../../api/analytics.js';
import {el, heading, formatTime} from '../../components/dom.js';
import {navigate} from '../../app/router.js';
import {datasetSummary, sourceNames} from '../../components/dataset.js';
import {barChart} from '../../components/chart.js';

export const statusNames = {ACTIVE: '활성', CHURN_RISK: '이탈 위험', DORMANT: '휴면', WITHDRAWN: '탈퇴'};
export const formatNumber = x => new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 2}).format(x);
export function formatMoney(value) {
  const [integer, fraction = ''] = value.split('.');
  const suffix = fraction.replace(/0+$/, '');
  return `${new Intl.NumberFormat('ko-KR').format(BigInt(integer))}${suffix ? `.${suffix}` : ''}원`;
}
export function comparison(metric) {
  if (metric.value === null || metric.previous_value === null || metric.difference === null) return '';
  if (metric.difference === 0) return '이전 기간과 동일';
  const unit = metric.unit === 'percent' ? '%p' : '명';
  return `이전 기간보다 ${metric.difference > 0 ? '+' : ''}${formatNumber(metric.difference)}${unit} (${formatNumber(metric.previous_value)} → ${formatNumber(metric.value)})`;
}
export async function renderDashboard(root, route, selected, signal) {
  const summary = await analytics.overview(route, signal);
  const [funnel, distribution] = await Promise.all([analytics.funnel(route, summary.data_version, signal), analytics.distribution(route, summary.data_version, signal)]);
  if (signal.aborted) return;
  const definitions = [
    ['total_customers', '전체 고객', '종료 시점 이전 가입 고객 · 탈퇴 포함'],
    ['active_customers', '활성 고객', '기간 내 VIEW·CART·PURCHASE 행동이 있는 고객'],
    ['new_customers', '신규 고객', '선택 기간에 가입한 고객'],
    ['repeat_purchase_rate', '재구매율', '기간 내 완료 주문 2건 이상 고객 / 완료 주문 고객'],
  ];
  const cards = definitions.map(([key, title, rule]) => {
    const metric = summary.metrics[key];
    const note = comparison(metric);
    return el('article', {className: 'card kpi-card', title: rule},
      el('h2', {className: 'metric-label', text: title, tabindex: '0', title: rule}),
      el('strong', {className: 'metric-value', text: metric.value === null ? '—' : `${formatNumber(metric.value)}${metric.unit === 'percent' ? '%' : '명'}`, title: metric.value === null ? '해당 기간에 계산할 구매 데이터가 없습니다.' : rule}),
      note ? el('p', {className: 'metric-note', text: note}) : null);
  });
  const drill = patch => navigate({view: 'customers', resource: '', page: 1, q: '', status: '', cohort: 'all', signup_from: '', signup_to: '', ...patch});
  root.replaceChildren(
    el('header', {className: 'overview-intro', role: 'region', 'aria-label': '선택한 데이터셋'},
      heading(selected.name, datasetSummary(selected), el('span', {className: 'badge', text: sourceNames[selected.source]}))),
    el('section', {className: 'grid overview-kpis', 'aria-label': '고객 핵심 지표'}, ...cards),
    el('div', {className: 'overview-charts'},
      barChart('고객 상태 분포', Object.entries(statusNames).map(([status, label]) => ({status, label, count: distribution.customer_statuses.find(row => row.status === status)?.count ?? 0})), signal, row => drill({status: row.status})),
      barChart('행동 퍼널', funnel.steps.map(row => ({...row, label: {view: '조회', cart: '장바구니', purchase: '구매'}[row.name]})), signal, row => drill({cohort: row.name}))),
    el('footer', {className: 'overview-footer'},
      el('p', {text: `${route.from} ~ ${route.to} · 기준 ${formatTime(summary.reference_at)} (한국 시간)`}),
      el('p', {text: 'CRM 기여 매출과 저장 세그먼트 분포는 아직 제공하지 않습니다.'})));
}
