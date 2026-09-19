import test from 'node:test';
import assert from 'node:assert/strict';
import {toSeoulInput, fromSeoulInput} from '../src/features/segments/reference.js';

test('Seoul picker converts UTC dates and preserves milliseconds', () => {
  assert.equal(toSeoulInput('2026-09-19T15:00:00Z'), '2026-09-20T00:00:00');
  assert.equal(fromSeoulInput('2026-09-20T00:00'), '2026-09-19T15:00:00.000Z');
  assert.equal(fromSeoulInput('2026-01-01T00:00'), '2025-12-31T15:00:00.000Z');
  const instant = '2026-09-19T12:34:56.123Z';
  assert.equal(fromSeoulInput(toSeoulInput(instant)), instant);
  for (const value of ['', '2026-02-30T12:00', '2026-01-01T24:00', '2026-01-01T12:60']) {
    assert.throws(() => fromSeoulInput(value), RangeError);
  }
});
import {formatReferenceLabel} from '../src/features/segments/preview.js';
test('preview reference distinguishes midnight from a selected clock time', () => {
  assert.match(formatReferenceLabel('2026-09-19T15:00:00Z'), /2026.*9.*20.*자정/);
  assert.match(formatReferenceLabel('2026-09-19T05:30:00Z'), /14:30/);
});
