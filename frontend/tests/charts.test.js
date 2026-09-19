import test from 'node:test';
import assert from 'node:assert/strict';
import {barPercentages} from '../src/components/chart.js';
import {comparison} from '../src/features/dashboard/index.js';

test('bar scale preserves proportions including empty and zero series', () => {
  assert.deepEqual(barPercentages([{count: 100}, {count: 50}, {count: 0}, {count: 25}]), [100, 50, 0, 25]);
  assert.deepEqual(barPercentages([{count: 0}, {count: 0}]), [0, 0]);
  assert.deepEqual(barPercentages([]), []);
});
test('KPI comparison hides missing values and condenses changes', () => {
  const metric = {value: 90, previous_value: 0, difference: 90, unit: 'customers'};
  assert.equal(comparison(metric), '이전 기간보다 +90명 (0 → 90)');
  assert.equal(comparison({...metric, value: 40, previous_value: 90, difference: -50}), '이전 기간보다 -50명 (90 → 40)');
  assert.equal(comparison({...metric, difference: 0}), '이전 기간과 동일');
  assert.equal(comparison({...metric, previous_value: null}), '');
  assert.equal(comparison({...metric, value: null}), '');
});
