import test from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute, routeHash, apiPeriod, validDate, defaultPeriod} from '../src/app/router.js';

test('Korean calendar dates produce an inclusive end date with exclusive UTC upper bound', () => {
  assert.deepEqual(apiPeriod('2026-09-19', '2026-09-19'), {from: '2026-09-18T15:00:00.000Z', to: '2026-09-19T15:00:00.000Z'});
  assert.deepEqual(defaultPeriod(new Date('2026-09-18T16:00:00Z')), {from: '2026-08-21', to: '2026-09-19'});
  assert.throws(() => apiPeriod('2026-09-20', '2026-09-19'));
  assert.equal(validDate('2026-02-30'), false);
  assert.equal(validDate('2026-02-32'), false);
  assert.equal(validDate('2024-02-29'), true);
});

test('shareable route preserves dataset, resource, dates, page and special search text', () => {
  const id = '11111111-1111-4111-8111-111111111111';
  const route = {view: 'customers', resource: id, dataset: id, from: '2026-09-01', to: '2026-09-19', page: 2, q: 'VIP & <script>?'};
  assert.deepEqual(parseRoute(routeHash(route)), {...route, issues: []});
});

test('invalid deep links are reported instead of silently selecting a different dataset', () => {
  for (const hash of ['#/missing', '#/data?dataset=bad', '#/data?page=-1', '#/data?page=Infinity', '#/data?from=2026-02-31', '#/customers/bad']) {
    assert.ok(parseRoute(hash).issues.length, hash);
  }
});
