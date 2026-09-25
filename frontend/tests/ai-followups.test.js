import test from 'node:test';
import assert from 'node:assert/strict';
import {followups} from '../src/features/ai/followups.js';
const answer=(type,data={})=>({response:{result_type:type,data}});
test('suggestions respect pending, empty results and explicit comparison scope',()=>{
  assert.deepEqual(followups({pending:true}),[]);
  const empty=followups(answer('campaign_comparison',{campaigns:[]}));
  assert.match(empty[0].prompt,/전체 캠페인/);
  const result=answer('campaign_comparison',{campaigns:[{id:'one'}],channel:'EMAIL'});
  assert.match(followups(result,{kind:'campaign_list'})[0].prompt,/위 캠페인/);
  assert.match(followups(result,null)[0].prompt,/전체 캠페인/);
  assert.match(followups(result,null)[2].prompt,/푸시/);
});
test('campaign suggestions require a saved segment and its current context',()=>{
  const message=answer('segment_preview',{description:'누적 구매액 300,000원 이상'});
  assert.match(followups(message)[0].prompt,/누적 구매액 300,000원 이상/);
  message.saved={id:'segment'};
  assert.match(followups(message,{kind:'segment',id:'segment'})[0].prompt,/이메일 캠페인/);
  assert.doesNotMatch(followups(message,null)[0].prompt,/이 세그먼트로/);
});
test('suggestion labels stay concise without discarding the underlying target condition',()=>{
  const message=answer('segment_preview',{description:'장바구니 이벤트 수 0건 초과 · 구매 이벤트 수 0건 일치'});
  const [suggestion]=followups(message);
  assert.ok(suggestion.label.length<=25);
  assert.match(suggestion.prompt,/장바구니 이벤트/);
  for(const suggestion of followups(answer('campaign_comparison',{campaigns:[{id:'one'}]}),{kind:'campaign_list'})){
    assert.ok(suggestion.label.length<=25);
    assert.ok(!suggestion.label.includes('\n'));
  }
});
