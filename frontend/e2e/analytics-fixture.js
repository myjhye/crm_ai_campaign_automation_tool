export function analyticsFixture(url) {
  const dataset_id = url.searchParams.get('dataset_id');
  const meta = {dataset_id, reference_at: '2026-09-19T00:00:00Z', data_version: 1};
  const period = {from: '2026-09-01T00:00:00Z', to: meta.reference_at};
  if (url.pathname === '/api/v1/dashboard/overview') {
    const metrics = {};
    for (const key of ['total_customers', 'new_customers', 'active_customers', 'dormant_customers', 'purchase_conversion_rate', 'repeat_purchase_rate', 'crm_revenue']) {
      metrics[key] = {value: key === 'crm_revenue' ? null : 1, reason: key === 'crm_revenue' ? 'not_ready' : null,
        unit: key.endsWith('rate') ? 'percent' : 'customers', difference_unit: 'customers', previous_value: 0, difference: 1, relative_change: null};
    }
    return {...meta, source: 'DEMO', period, previous_period: period, metrics};
  }
  if (url.pathname === '/api/v1/dashboard/funnel') return {...meta, period, steps: ['view', 'cart', 'purchase'].map(name => ({name, count: 1}))};
  if (url.pathname === '/api/v1/dashboard/segments') return {...meta, period, customer_statuses: ['ACTIVE', 'CHURN_RISK', 'DORMANT', 'WITHDRAWN'].map(status => ({status, count: 1}))};
  if (url.pathname.startsWith('/api/v1/customers')) {
    const customer = {id: '33333333-3333-4333-8333-333333333333', name: 'Demo customer', external_id: 'customer-1', email: 'a***@example.invalid', status: url.searchParams.get('status') || 'ACTIVE',
      signup_at: '2026-01-01T00:00:00Z', order_count: 2, total_purchase_amount: '300000.00', average_order_amount: '150000.00', last_purchase_at: '2026-09-09T00:00:00Z', days_since_last_purchase: 10};
    const page = {...meta, total: 1, page: Number(url.searchParams.get('page') || 1), page_size: 20};
    if (url.pathname === '/api/v1/customers') return {...page, items: [customer]};
    if (url.pathname.endsWith('/events')) return {...page, items: [{id: customer.id, event_type: 'VIEW', event_at: '2026-09-08T00:00:00Z'}]};
    if (url.pathname.endsWith('/deliveries') || url.pathname.endsWith('/segments')) return {...meta, status: 'not_ready', items: [], total: null};
    return {...meta, customer, channels: [{channel: 'EMAIL', consent: true, is_valid: true, hard_bounce: false}], rfm: {version: 'rfm-fixed-v1', recency: 4, frequency: 2, monetary: 4}, preferred_category: 'home', fatigue: {status: 'not_ready'}};
  }
  return null;
}
