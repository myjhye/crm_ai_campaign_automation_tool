import test from 'node:test';
import assert from 'node:assert/strict';
import {parseValue, vipTemplate} from '../src/features/segments/condition.js';
test('segment builder preserves money strings, typed values and null operators', () => {
  assert.equal(parseValue('300000', 'money', 'GTE'), '300000');
  assert.deepEqual(parseValue('1, 3', 'integer', 'BETWEEN'), [1,3]);
  assert.equal(parseValue('false', 'boolean', 'EQ'), false);
  assert.equal(parseValue('', 'integer', 'IS_NULL'), undefined);
  assert.throws(() => parseValue('1.5', 'integer', 'EQ'));
  const a = vipTemplate(); a.conditions.pop(); assert.equal(vipTemplate().conditions.length, 3);
});
import {segmentTemplates, templateCondition} from '../src/features/segments/condition.js';
test('six templates are independent editable conditions', () => {
  assert.equal(segmentTemplates.length, 6);
  for (const template of segmentTemplates) {
    const original = JSON.stringify(template.condition);
    const copy = templateCondition(template.id);
    copy.conditions[0].value = 'edited';
    assert.equal(JSON.stringify(template.condition), original);
    assert.ok(template.condition.conditions.some(row => row.field === 'email_consent' && row.value === true));
  }
  assert.throws(() => templateCondition('missing'));
});
