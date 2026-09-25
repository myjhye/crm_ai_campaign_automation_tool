import test from 'node:test';
import assert from 'node:assert/strict';
import {recentTurns} from '../src/features/ai/history.js';
test('history is bounded and carries conditions without profile or customer metrics',()=>{
  const rows=Array.from({length:10},()=>({role:'user',content:'질문'}));
  rows.push({role:'assistant',response:{result_type:'segment_preview',message:'조회 완료',data:{description:'장바구니 미구매',count:500,profile:{email:'private'}}}});
  const turns=recentTurns(rows);
  assert.equal(turns.length,6);
  assert.match(turns.at(-1).content,/장바구니 미구매/);
  assert.doesNotMatch(JSON.stringify(turns),/500|private/);
  assert.deepEqual(recentTurns([{role:'assistant',pending:true,content:'대기'}]),[]);
});
