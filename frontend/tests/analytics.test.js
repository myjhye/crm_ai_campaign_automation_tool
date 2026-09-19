import test from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute, routeHash} from '../src/app/router.js';
import {isSummary, queryFor, isCustomer} from '../src/api/analytics.js';
import {formatMoney} from '../src/features/dashboard/index.js';

test('customer drilldown filters round-trip with date bounds and ordering', () => {
  const hash = '#/customers?dataset=11111111-1111-4111-8111-111111111111&from=2026-09-01&to=2026-09-19&status=DORMANT&cohort=cart&sort=order_count&direction=asc&signup_from=2026-01-01';
  const route = parseRoute(hash);
  assert.deepEqual(parseRoute(routeHash(route)), route);
  assert.equal(queryFor(route).get('to'), '2026-09-19T15:00:00.000Z');
  assert.equal(parseRoute('#/customers?sort=unsafe').issues.length, 1);
});

test('malformed aggregate and customer responses do not become displayed zeroes', () => {
  assert.equal(Boolean(isSummary({metrics: {}})), false);
  assert.equal(Boolean(isCustomer({id: 'not-a-uuid', total_purchase_amount: 0})), false);
  assert.equal(formatMoney('9999999999999999.12'), '9,999,999,999,999,999.12원');
});
