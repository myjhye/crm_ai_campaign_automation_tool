import {test,expect} from '@playwright/test';
const did='11111111-1111-4111-8111-111111111111',sid='22222222-2222-4222-8222-222222222222',rid='33333333-3333-4333-8333-333333333333',cid='44444444-4444-4444-8444-444444444444';
const dataset={id:did,name:'체험용 중형 샘플',source:'DEMO',purpose:'ANALYSIS',customer_count:5000,order_count:15000,event_count:100000,version:1,created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z',reference_at:'2026-09-19T00:00:00Z'};
const hint={kind:'segment',id:sid,revision_id:rid,name:'휴면 VIP',label:'휴면 VIP 세그먼트 기준으로'};
const candidate='60일 미구매, 누적 30만원 이상 고객을 저장할 초안으로 만들어줘';
async function setup(page,handler){
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/datasets'))return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/status'))return route.fulfill({json:{mode:'mock',available:true}});
    if(path.endsWith('/insights'))return route.fulfill({json:{dataset_id:did,cards:[
      {title:'활성 고객 비율',primary_value:'2,000명',secondary_value:'전체의 40%',cta:{label:'활성 고객 수 확인',prefill_prompt:'활성 고객 수를 알려줘'}},
      {title:'캠페인 대상 후보',primary_value:'500명',secondary_value:'60일 이상 미구매',cta:{label:'이 조건으로 세그먼트 만들기',prefill_prompt:candidate}},
      {title:'최근 완료 캠페인',primary_value:'VIP',secondary_value:'전환율 5%',cta:{label:'성과 분석하기',action:'navigate',campaign_id:cid}}]}});
    if(await handler(route,path))return;
    return route.fulfill({status:404,json:{error:{message:'테스트 범위 밖'}}});
  });
}
const response=(result_type,data,context_hint=null)=>({message:'결과를 확인해주세요.',result_type,data,context_hint,dataset_id:did,mode:'mock'});
test('insight to saved segment to campaign proposal with retained scope and confirmation',async({page})=>{
  const requests=[];let saves=0;
  await setup(page,async(route,path)=>{
    if(path.endsWith('/chat')){
      const body=route.request().postDataJSON();requests.push(body);
      const data=requests.length===1?response('segment_preview',{name:'휴면 VIP',proposal_id:sid,expires_at:'2099-09-20T00:00:00Z',reference_at:dataset.reference_at,count:500,total:5000,percentage:10,description:'누적 구매액 300,000원 이상',warnings:[],profile:{average_purchase_amount:'645000',email_open_customers_30d:0,categories:[]}}):
        requests.length===2?response('clarification',{},hint):response('campaign_draft',{proposal_id:cid,expires_at:'2099-09-20T00:00:00Z',name:'휴면 VIP · 재구매 유도',channel:'EMAIL',benefit:'15% 할인 쿠폰',target_value:'5.00',variants:[{variant_name:'A',subject:'쿠폰 안내',body:'15% 할인 쿠폰',hypothesis:'혜택'},{variant_name:'B',subject:'안녕하세요',body:'15% 할인 쿠폰',hypothesis:'관계'}]},hint);
      await route.fulfill({json:data});return true;
    }
    if(path.endsWith('/confirm')){saves++;await route.fulfill({json:saves===1?{id:sid,context_hint:hint}:{id:cid}});return true;}
  });
  await page.goto(`/#/ai?dataset=${did}&from=2026-08-22&to=2026-09-20`);
  await expect(page.locator('.ai-insight-card')).toHaveCount(3);
  await expect(page.locator('.ai-messages')).toHaveJSProperty('scrollTop',0);
  await page.getByRole('button',{name:'이 조건으로 세그먼트 만들기'}).click();
  const input=page.getByLabel('AI에게 요청하기',{exact:true});
  await expect(input).toHaveValue(candidate);expect(requests).toHaveLength(0);
  await input.press('Enter');await expect(page.getByRole('heading',{name:'대상 고객 500명'})).toBeVisible();
  await expect(page.locator('.ai-insights')).toHaveCount(0);expect(saves).toBe(0);
  await page.getByRole('button',{name:'확인 후 세그먼트 저장'}).click();
  await expect(page.locator('.ai-context-chip')).toContainText('휴면 VIP 세그먼트 기준으로');
  await page.getByRole('button',{name:'이 세그먼트로 캠페인 초안 만들어'}).click();await input.press('Enter');
  await expect(page.locator('.ai-message-user')).toHaveCount(2);
  expect(requests[1].context_hint).toEqual(hint);expect(requests[1].conversation_id).toBe(requests[0].conversation_id);
  await page.getByRole('link',{name:'Segments',exact:true}).click();
  await page.locator('#ai-page-link').click();
  await expect(page.locator('.ai-message-user')).toHaveCount(2);
  await expect(page.locator('.ai-context-chip')).toContainText('휴면 VIP');
  await input.fill('이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘');await input.press('Enter');
  await expect(page.locator('.ai-draft-variants section')).toHaveCount(2);expect(saves).toBe(1);
  await page.getByRole('button',{name:'확인 후 캠페인 저장'}).click();await expect(page.getByText('캠페인 초안이 저장되었습니다.')).toBeVisible();
  expect(saves).toBe(2);
  await page.getByRole('button',{name:'문맥 제거'}).click();await expect(page.locator('.ai-context-chip')).toBeHidden();
  await page.screenshot({path:'test-results/ai-workspace-conversation.png',fullPage:true});
});

test('scope reset, IME, insight errors and interrupted request remain usable on mobile',async({page})=>{
  let bodies=[];
  await setup(page,async(route,path)=>{
    if(path.endsWith('/chat')){bodies.push(route.request().postDataJSON());await route.fulfill({json:response('metric',{metrics:{active_customers:{value:100,unit:'count'}}})});return true;}
  });
  await page.setViewportSize({width:390,height:844});
  await page.goto(`/#/ai?dataset=${did}&from=2026-08-22&to=2026-09-20`);
  await expect(page.locator('.ai-insight-card')).toHaveCount(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const composer=await page.locator('.ai-composer').boundingBox();
  expect(composer.y+composer.height).toBeLessThanOrEqual(844);
  await page.screenshot({path:'test-results/ai-workspace-mobile.png',fullPage:true});
  const input=page.getByLabel('AI에게 요청하기',{exact:true});await input.fill('한글');
  await input.dispatchEvent('compositionstart');await input.press('Enter');expect(bodies).toHaveLength(0);
  await input.dispatchEvent('compositionend');await input.press('Enter');await expect(page.locator('.ai-metric-value')).toHaveText('100명');
  await page.route('**/api/v1/ai/insights?*',route=>route.fulfill({status:503,json:{error:{message:'잠시 후 다시'}}}));
  await page.locator('#period-from').fill('2026-08-01');await page.getByRole('button',{name:'기간 적용'}).click();
  await expect(page.locator('.ai-message-system')).toContainText('대화를 새로 시작합니다');
  await expect(page.locator('.ai-message-user')).toHaveCount(0);
  await expect(page.locator('.ai-insight-error')).toContainText('대화는 계속 사용할 수 있습니다');
  await input.fill('활성 고객 수를 알려줘');await input.press('Enter');await expect(page.locator('.ai-metric-value')).toHaveText('100명');
  expect(bodies[1].conversation_id).not.toBe(bodies[0].conversation_id);expect(bodies[1].context_hint).toBeUndefined();
  let release;const wait=new Promise(resolve=>{release=resolve;});
  await page.route('**/api/v1/ai/chat',async route=>{await wait;await route.fulfill({json:response('clarification',{})}).catch(()=>{});});
  await input.fill('중단되는 요청');await input.press('Enter');await expect(input).toBeDisabled();
  await page.getByRole('link',{name:'Segments',exact:true}).click();release();await page.locator('#ai-page-link').click();
  await expect(input).toBeEnabled();await expect(input).toHaveValue('중단되는 요청');
  await expect(page.getByText('요청이 중단되었습니다. 다시 요청해주세요.')).toBeVisible();
});
