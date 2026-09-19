import {test, expect} from '@playwright/test';
const id = '11111111-1111-4111-8111-111111111111';
const segmentId = '22222222-2222-4222-8222-222222222222';
const revisionId = '33333333-3333-4333-8333-333333333333';
const dataset = {id, name:'체험용 소형 샘플', source:'DEMO',purpose:'ANALYSIS',customer_count:100,order_count:300,event_count:2000,version:1,created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z',reference_at:'2026-09-19T00:00:00Z'};
test('build, preview, save, reload, conflict and archive a segment', async ({page}) => {
  let saved = null, conflict = false;
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), method = route.request().method();
    if (url.pathname === '/api/v1/datasets') return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if (url.pathname.endsWith('/fields')) return route.fulfill({json:{items:[
      {name:'days_since_last_purchase',label:'구매 경과일',type:'integer',comparisons:['GTE','LT','BETWEEN','IS_NULL']},
      {name:'total_purchase_amount',label:'구매 합계',type:'money',comparisons:['GTE']},
      {name:'email_consent',label:'이메일 동의',type:'boolean',comparisons:['EQ']},
      {name:'order_count',label:'주문 수',type:'integer',comparisons:['GTE','EQ']},
      {name:'status',label:'고객 상태',type:'status',comparisons:['EQ','NEQ']},
      {name:'email_opens_30d',label:'이메일 오픈 수',type:'integer',comparisons:['GTE']},
    ]}});
    if (url.pathname.endsWith('/preview')) return route.fulfill({json:{...route.request().postDataJSON(),count:10,total:100,percentage:10,data_version:1,condition_hash:'hash',description:'휴면 VIP 조건',warnings:[],profile:{average_purchase_amount:'645000.00',email_open_customers_30d:0,categories:[{category:'fashion',count:4},{category:'home',count:3},{category:'sports',count:3}]}}});
    if (method === 'POST' || method === 'PUT') {
      if (conflict) return route.fulfill({status:409,json:{error:{message:'다른 방문자가 변경했습니다.'}}});
      saved = {...route.request().postDataJSON(),id:segmentId,revision_id:revisionId,version:1,description:'휴면 VIP 조건'};
      return route.fulfill({status:method==='POST'?201:200,json:saved});
    }
    if (method === 'DELETE') {const result={...saved,archived_at:dataset.reference_at}; saved=null; return route.fulfill({json:result});}
    return route.fulfill({json:url.pathname.endsWith(segmentId)?saved:{items:saved?[saved]:[],total:saved?1:0,page:1,page_size:20}});
  });
  await page.goto('/#/segments');
  await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
  await page.getByLabel('세그먼트 이름').fill('휴면 VIP');
  const reference = page.getByLabel('기준 시점 (한국 시간)', {exact: true});
  await expect(reference).toHaveAttribute('type', 'datetime-local');
  await reference.fill('2026-09-19T14:30');
  const previewRequest = page.waitForRequest(request => request.url().endsWith('/segments/preview'));
  await page.getByRole('button',{name:'대상 미리보기',exact:true}).click();
  expect((await previewRequest).postDataJSON().reference_at).toBe('2026-09-19T05:30:00.000Z');
  await expect(page.getByRole('heading',{name:'대상 고객 10명'})).toBeVisible();
  const previewPanel = page.getByRole('region', {name: '세그먼트 미리보기'});
  await expect(previewPanel).toContainText('645,000원');
  await expect(previewPanel).toContainText('패션');
  await expect(previewPanel).toContainText('홈·리빙');
  await expect(previewPanel).toContainText('전체 100명 중 10%');
  await expect(previewPanel.getByRole('heading', {name: '적용된 조건', exact: true})).toBeVisible();
  await expect(previewPanel).toContainText('휴면 VIP 조건');
  await page.screenshot({path: 'test-results/segments-1280.png', fullPage: true});
  await page.getByRole('button',{name:'세그먼트 저장',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(segmentId));
  await expect(page.locator('.segment-success')).toContainText('저장되었습니다');
  await page.reload(); await expect(page.getByLabel('세그먼트 이름')).toHaveValue('휴면 VIP');
  await expect(reference).toHaveValue('2026-09-19T14:30');
  await page.getByRole('button', {name: '현재 시각', exact: true}).click();
  await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
  await page.getByRole('button', {name: '선택 기간 종료', exact: true}).click();
  expect(await reference.inputValue()).toMatch(/T00:00/);
  await page.getByRole('button',{name:'대상 미리보기',exact:true}).click();
  await page.getByLabel('조건 값').first().fill('90');
  await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
  const templates = page.getByRole('region', {name: '추천 고객 유형'});
  for (const name of ['첫 구매 유도', '재구매 유도', '이탈 위험', '충성 고객', '이메일 반응 고객', '휴면 VIP']) {
    await templates.getByRole('button',{name,exact:true}).click();
    await expect(page.getByLabel('세그먼트 이름')).toHaveValue(name);
    await expect(templates.getByRole('button',{name,exact:true})).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
    await page.getByRole('button',{name:'대상 미리보기',exact:true}).click();
    await expect(page.getByRole('heading',{name:'대상 고객 10명'})).toBeVisible();
  }
  await templates.getByRole('button',{name:'휴면 VIP',exact:true}).click();
  await expect(page.getByLabel('조건 값').first()).toHaveValue('60');
  await expect(page.getByText('휴면 VIP 이름과 조건을 입력했습니다. 대상 미리보기로 고객 수를 확인하세요.')).toBeVisible();
  await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'대상 미리보기',exact:true}).click(); conflict=true;
  await page.getByRole('button',{name:'세그먼트 저장',exact:true}).click();
  await expect(page.getByRole('button',{name:'최신 내용 불러오기'})).toBeVisible();
  conflict=false; await page.getByRole('button',{name:'최신 내용 불러오기'}).click();
  const library = page.getByRole('region', {name:'저장된 세그먼트', exact:true});
  const composeBounds = await page.getByRole('region', {name:'세그먼트 편집'}).boundingBox();
  const libraryBounds = await library.boundingBox();
  expect(composeBounds.x + composeBounds.width).toBeLessThanOrEqual(libraryBounds.x);
  await page.getByRole('button',{name:'초기화',exact:true}).click();
  await expect(page.getByLabel('세그먼트 이름')).toHaveValue('');
  await expect(page.getByRole('button',{name:'세그먼트 저장',exact:true})).toBeDisabled();
  await library.getByRole('button',{name:'불러오기',exact:true}).click();
  await expect(page.getByLabel('세그먼트 이름')).toHaveValue('휴면 VIP');
  await library.getByRole('button',{name:'삭제',exact:true}).click();
  await expect(page.getByRole('heading',{name:'저장된 세그먼트 0개'})).toBeVisible();
  await expect(page.locator('.segment-success')).toContainText('삭제되었습니다');
});
