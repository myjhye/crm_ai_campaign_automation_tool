import {request, isUUID, isPage} from './client.js';
import {apiPeriod} from '../app/router.js';

const count = x => Number.isInteger(x) && x >= 0;
const money = x => typeof x === 'string' && /^\d+(\.\d+)?$/.test(x);
export const metadata = x => x && isUUID(x.dataset_id) && count(x.data_version) && typeof x.reference_at === 'string';
export const isCustomer = x => x && isUUID(x.id) && typeof x.external_id === 'string' && (x.name === null || typeof x.name === 'string')
  && (x.email === null || typeof x.email === 'string') && count(x.order_count) && money(x.total_purchase_amount)
  && ['ACTIVE', 'CHURN_RISK', 'DORMANT', 'WITHDRAWN'].includes(x.status);
export const isSummary = x => metadata(x) && x.metrics && ['total_customers', 'new_customers', 'active_customers', 'dormant_customers', 'purchase_conversion_rate', 'repeat_purchase_rate', 'crm_revenue'].every(key => {
  const m = x.metrics[key]; return m && (m.value === null || typeof m.value === 'number' && Number.isFinite(m.value)) && typeof m.unit === 'string';
});
export function queryFor(route, extra = {}) {
  return new URLSearchParams({dataset_id: route.dataset, ...apiPeriod(route.from, route.to), ...extra});
}
export const analytics = {
  overview: (route, signal) => request(`/dashboard/overview?${queryFor(route)}`, {signal, validate: isSummary}),
  funnel: (route, version, signal) => request(`/dashboard/funnel?${queryFor(route, {data_version: version})}`, {signal, validate: x => metadata(x) && Array.isArray(x.steps) && x.steps.length === 3 && x.steps.every(s => ['view', 'cart', 'purchase'].includes(s.name) && count(s.count))}),
  distribution: (route, version, signal) => request(`/dashboard/segments?${queryFor(route, {data_version: version})}`, {signal, validate: x => metadata(x) && Array.isArray(x.customer_statuses) && x.customer_statuses.every(s => count(s.count) && typeof s.status === 'string')}),
  customers: (route, signal) => {
    const filters = {page: route.page, q: route.q, sort: route.sort || 'signup_at', direction: route.direction || 'desc', cohort: route.cohort || 'all'};
    if (route.status) filters.status = route.status;
    if (route.signup_from) filters.signup_from = apiPeriod(route.signup_from, route.signup_from).from;
    if (route.signup_to) filters.signup_to = apiPeriod(route.signup_to, route.signup_to).to;
    return request(`/customers?${queryFor(route, filters)}`, {signal, validate: x => metadata(x) && isPage(isCustomer)(x)});
  },
  detail: (route, signal) => request(`/customers/${route.resource}?${queryFor(route)}`, {signal, validate: x => metadata(x) && isCustomer(x.customer) && Array.isArray(x.channels) && x.rfm && x.fatigue}),
  events: (route, version, signal) => request(`/customers/${route.resource}/events?${queryFor(route, {data_version: version, page: route.page})}`, {signal, validate: x => metadata(x) && isPage(e => isUUID(e.id) && typeof e.event_type === 'string' && typeof e.event_at === 'string')(x)}),
  history: (route, kind, version, signal) => request(`/customers/${route.resource}/${kind}?${queryFor(route, {data_version: version})}`, {signal, validate: x => metadata(x) && x.status === 'not_ready'}),
};
