import {isUUID} from '../api/client.js';

export const pages = [
  ['overview', 'Overview', '◫'], ['customers', 'Customers', '♧'], ['segments', 'Segments', '◇'],
  ['campaigns', 'Campaigns', '↗'], ['experiments', 'Experiments', '⚗'], ['reports', 'Reports', '▤'],
  ['data', 'Data & Integrations', '▦'], ['settings', 'Settings', '⚙'],
];
export function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '1900-01-01' || value > '9998-12-31') return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
export function defaultPeriod(now = new Date()) {
  const to = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'}).format(now);
  const from = new Date(`${to}T00:00:00Z`); from.setUTCDate(from.getUTCDate() - 29);
  return {from: from.toISOString().slice(0, 10), to};
}
/** Inclusive Seoul dates -> UTC [from,to). */
export function apiPeriod(from, to) {
  if (!validDate(from) || !validDate(to) || from > to) throw new RangeError('올바른 조회 기간을 선택해주세요.');
  return {from: new Date(`${from}T00:00:00+09:00`).toISOString(), to: new Date(Date.parse(`${to}T00:00:00+09:00`) + 86400000).toISOString()};
}
/** URL is the source of truth for all shareable view state. */
export function parseRoute(hash, now) {
  const [path, query = ''] = hash.replace(/^#/, '').split('?');
  const parts = (path || '/overview').split('/').filter(Boolean);
  const params = new URLSearchParams(query);
  const defaults = defaultPeriod(now);
  const route = {view: parts[0] || 'overview', resource: parts[1] || '', dataset: params.get('dataset') || '',
    from: params.get('from') || defaults.from, to: params.get('to') || defaults.to,
    page: Number(params.get('page') || 1), q: params.get('q') || '', issues: []};
  if (!pages.some(([id]) => id === route.view) || parts.length > 2) route.issues.push('존재하지 않는 화면입니다.');
  if ((route.dataset && !isUUID(route.dataset)) || (route.resource && !isUUID(route.resource))) route.issues.push('주소의 데이터 식별자가 올바르지 않습니다.');
  if (!Number.isSafeInteger(route.page) || route.page < 1 || route.page > 1000000) route.issues.push('페이지 번호가 올바르지 않습니다.');
  if (route.q.length > 200) route.issues.push('검색어는 200자 이하로 입력해주세요.');
  try { apiPeriod(route.from, route.to); } catch { route.issues.push('조회 기간이 올바르지 않습니다.'); }
  return route;
}
export function routeHash(route) {
  const params = new URLSearchParams();
  for (const key of ['dataset', 'from', 'to', 'q']) if (route[key]) params.set(key, route[key]);
  if (route.page > 1) params.set('page', route.page);
  return `#/${route.view}${route.resource ? `/${route.resource}` : ''}${params.size ? `?${params}` : ''}`;
}
export function navigate(patch, {replace = false} = {}) {
  const next = routeHash({...parseRoute(location.hash), ...patch});
  if (replace) { history.replaceState(null, '', next); window.dispatchEvent(new Event('hashchange')); }
  else if (location.hash !== next) location.hash = next;
}
export function startRouter(listener) {
  const change = () => listener(parseRoute(location.hash));
  window.addEventListener('hashchange', change);
  change();
  return () => window.removeEventListener('hashchange', change);
}
