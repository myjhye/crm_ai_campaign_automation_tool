import {test, expect} from '@playwright/test';
const id = '11111111-1111-4111-8111-111111111111';
const proposal = '22222222-2222-4222-8222-222222222222';
test('AI preview requires confirmation and renders a saved result', async ({page}) => {
  let confirmations = 0;
  const dataset = {id,name:'체험용 소형 샘플',source:'DEMO',purpose:'ANALYSIS',customer_count:100,order_count:300,event_count:2000,version:1,created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z',reference_at:'2026-09-19T00:00:00Z'};
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/status')) return route.fulfill({json:{mode:'mock',available:true}});
    if (path.endsWith('/datasets')) return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if (path.endsWith('/chat')) return route.fulfill({json:{message:'조건과 대상 고객을 확인해주세요.',mode:'mock',dataset_id:id,result_type:'segment_preview',data:{name:'휴면 VIP',proposal_id:proposal,expires_at:'2026-09-19T00:30:00Z',reference_at:dataset.reference_at,count:10,total:100,percentage:10,description:'누적 구매액 300,000원 이상',warnings:[],profile:{average_purchase_amount:'645000',email_open_customers_30d:0,categories:[]}}}});
    if (path.endsWith('/confirm')) {confirmations++; return route.fulfill({json:{id:proposal}});}
    return route.fulfill({status:404,json:{error:{message:'이 화면은 테스트 대상이 아닙니다.'}}});
  });
  await page.goto('/#/data');
  await expect(page.locator('#dataset-select')).toHaveValue(id);
  await page.locator('#ai-page-link').click();
  await page.getByRole('button',{name:'60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘',exact:true}).click();
  await page.getByRole('button',{name:'전송',exact:true}).click();
  await expect(page.getByRole('heading',{name:'대상 고객 10명'})).toBeVisible();
  expect(confirmations).toBe(0);
  await page.getByRole('button',{name:'확인 후 세그먼트 저장'}).click();
  await expect(page.getByText('세그먼트가 저장되었습니다.',{exact:true})).toBeVisible();
  expect(confirmations).toBe(1);
  await expect(page.getByRole('button',{name:'저장 완료',exact:true})).toBeDisabled();
  await expect(page.locator('.ai-welcome-message')).toHaveCount(0);
  await expect(page.locator('.ai-message-user')).toHaveCount(1);
  const input = page.getByLabel('AI에게 요청하기', {exact:true});
  await input.fill('추가 요청');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('추가 요청\n');
  await input.press('Enter');
  await expect(page.locator('.ai-message-user')).toHaveCount(2);
  await expect(page.locator('.ai-result')).toHaveCount(2);
  await expect(page.locator('.ai-message-saved')).toHaveCount(1);
  const bar = await page.locator('.ai-input-bar').boundingBox();
  expect(bar.y + bar.height).toBeLessThanOrEqual(901);
  await page.screenshot({path:'test-results/ai-panel.png',fullPage:true});
  await page.locator('#period-from').fill('2026-08-01');
  await page.getByRole('button', {name:'기간 적용'}).click();
  await expect(page.locator('.ai-message-system')).toContainText('대화를 새로 시작합니다');
  await expect(page.locator('.ai-message-user')).toHaveCount(0);
});

test('AI campaign comparison opens the scoped results screen without validation selectors', async ({page}) => {
  const campaign='33333333-3333-4333-8333-333333333333';
  const dataset={id,name:'체험용 확장 샘플',source:'DEMO',purpose:'ANALYSIS',customer_count:300,order_count:900,event_count:6000,version:1,created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z',reference_at:'2026-09-19T00:00:00Z'};
  let chatBody;
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/status'))return route.fulfill({json:{mode:'mock',available:true}});
    if(path.endsWith('/datasets'))return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/campaigns'))return route.fulfill({json:{items:[{id:campaign,dataset_id:id,name:'휴면 VIP 재활성화',channel:'EMAIL',status:'DRAFT',version:2}],total:1,page:1,page_size:100}});
    if(path.endsWith('/chat')){chatBody=route.request().postDataJSON();return route.fulfill({json:{message:'완료 캠페인을 비교했습니다.',mode:'mock',dataset_id:id,result_type:'campaign_comparison',data:{total_matched:1,campaigns:[{campaign_id:campaign,name:'휴면 VIP 재활성화',channel:'EMAIL',sent_count:30,conversion_rate:3.27,click_rate:null,revenue:'10000.00'}]}}});}
    return route.fulfill({status:404,json:{error:{message:'테스트 범위 밖'}}});
  });
  await page.goto('/#/data');
  await page.locator('#ai-page-link').click();
  await expect(page.getByLabel('검수할 캠페인')).toHaveCount(0);
  await page.getByRole('button',{name:'선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘',exact:true}).click();
  await page.getByRole('button',{name:'전송',exact:true}).click();
  await expect(page.getByRole('cell',{name:'3.27%',exact:true})).toBeVisible();
  expect(chatBody.validation_campaign_id).toBeUndefined();
  expect(chatBody.conversation_id).toMatch(/^[0-9a-f-]{36}$/);
  await page.getByRole('link',{name:'휴면 VIP 재활성화'}).click();
  await expect(page).toHaveURL(new RegExp(`#/campaigns/${campaign}`));
  await expect(page).toHaveURL(/tab=results/);
});
