import {test,expect} from '@playwright/test';
const id='11111111-1111-4111-8111-111111111111', revision='22222222-2222-4222-8222-222222222222', campaign='33333333-3333-4333-8333-333333333333';
test('campaign copy editor saves A/B, switches SMS and recovers conflict',async ({page}) => {
  let saved=null, conflict=false, validation=null;
  const dataset={id,name:'체험용 샘플',purpose:'ANALYSIS',source:'DEMO',customer_count:100,order_count:300,event_count:2000,version:1,reference_at:'2026-09-19T00:00:00Z',created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z'};
  await page.route('**/api/v1/**',route => {
    const url=new URL(route.request().url()), method=route.request().method(), path=url.pathname;
    if(path.endsWith('/datasets')) return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/segments')) return route.fulfill({json:{items:[{id:revision,revision_id:revision,name:'휴면 VIP'}],total:1,page:1,page_size:100}});
    if(path.endsWith('/copy-policy')) return route.fulfill({json:{version:1,channels:{EMAIL:{subject_max:120,body_max:5000},PUSH:{subject_max:60,body_max:300},SMS:{subject_max:0,body_max:500}}}});
    if(path.endsWith('/review')) return route.fulfill({json:{campaign:saved,validation,approval:null}});
    if(path.endsWith('/validate')&&method==='POST') {
      validation={id:revision,campaign_id:campaign,campaign_version:saved.version,initial_count:30,excluded_count:0,eligible_count:30,passed:true,
        expires_at:'2099-09-20T05:33:00Z',blockers:[],rules:['WITHDRAWN','NO_CONSENT','INVALID_CONTACT','EXCLUDED_SEGMENT','DUPLICATE_CAMPAIGN','DAILY_LIMIT','WEEKLY_LIMIT'].map(rule_code=>({rule_code,affected_count:0,primary_count:0,message:rule_code}))};
      return route.fulfill({status:201,json:validation});
    }
    if(method==='DELETE') {saved=null; return route.fulfill({json:{id:campaign,archived:true,version:3}});}
    if(method==='POST'||method==='PUT') {
      if(conflict) return route.fulfill({status:409,json:{error:{message:'다른 방문자가 수정했습니다.'}}});
      saved={...route.request().postDataJSON(),id:campaign,version:(saved?.version||0)+1,status:'DRAFT'};
      return route.fulfill({status:method==='POST'?201:200,json:saved});
    }
    return route.fulfill({json:path.endsWith(campaign)?saved:{items:saved?[saved]:[],total:saved?1:0,page:1,page_size:20}});
  });
  await page.goto('/#/campaigns');
  await expect(page.getByLabel('브랜드 톤',{exact:true})).toHaveCount(0);
  await expect(page.getByText('제외 없음 · 필요한 세그먼트만 체크하세요.')).toBeVisible();
  const exclusion = page.getByRole('group',{name:'제외 세그먼트',exact:true}).getByRole('checkbox',{name:'휴면 VIP',exact:true});
  await exclusion.click();
  await expect(exclusion).toBeChecked();
  await expect(page.getByText('1개 선택됨 · 체크를 해제하면 제외 조건에서 빠집니다.')).toBeVisible();
  await exclusion.click();
  await expect(exclusion).not.toBeChecked();
  for(const [label,value] of [['캠페인 이름','재구매 캠페인'],['캠페인 목표','재구매 증가'],['KPI 목표값','5'],['혜택','10% 쿠폰'],['A안 제목','다시 만나요'],['B안 제목','쿠폰을 확인하세요'],['A안 본문','새로운 상품을 만나보세요'],['B안 본문','쿠폰으로 쇼핑하세요'],['A안 가설','신상품 강조'],['B안 가설','혜택 강조']]) await page.getByLabel(label,{exact:true}).fill(value);
  const target = page.getByRole('group',{name:'대상 세그먼트',exact:true}).getByRole('checkbox',{name:'휴면 VIP',exact:true});
  await target.click();
  await expect(target).toBeChecked();
  await target.click();
  await expect(target).not.toBeChecked();
  await target.click();
  await page.getByLabel('A안 비율 (%)',{exact:true}).fill('40');
  await page.getByRole('button',{name:'초안 저장 후 확인'}).click();
  await expect(page.getByText('A/B 비율 합계를 100%로 맞춰주세요.')).toBeVisible();
  await page.getByLabel('A안 비율 (%)',{exact:true}).fill('50');
  await page.getByRole('button',{name:'초안 저장 후 확인'}).click();
  await expect(page.getByText('캠페인 초안이 저장되었습니다.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'검수·승인',exact:true}).click();
  await expect(page.getByText('아직 검수하지 않았습니다. 저장 후 검수를 실행해주세요.')).toBeVisible();
  await page.getByRole('button',{name:'정책 검수 실행'}).click();
  await expect(page.locator('.review-overview-cards')).toContainText('최초 대상30명');
  await expect(page.locator('.review-reason-list li')).toHaveCount(7);
  await expect(page.locator('.review-reason-list')).toContainText('채널 미동의0명');
  await expect(page.locator('.review-overview-cards')).toContainText('승인 대상30명');
  await expect(page.getByText('2099. 9. 20. 오후 2:33까지 승인 요청에 사용할 수 있습니다.')).toBeVisible();
  await expect(page.getByRole('button',{name:'승인 요청'})).toBeEnabled();
  expect(saved.variants[0].allocation_bp).toBe(5000);
  expect(saved.brand_tone).toBe('다정하고 편안하게');
  expect(saved.exclusion_revision_ids).toEqual([]);
  await page.getByRole('button',{name:'작성',exact:true}).click();
  await page.getByLabel('채널',{exact:true}).selectOption('SMS');
  await expect(page.getByLabel('A안 제목',{exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'초안 저장 후 확인'}).click();
  await expect.poll(() => saved.channel).toBe('SMS');
  await expect(page.locator('form.campaign-form')).not.toHaveAttribute('inert','');
  expect(saved.variants[0].subject).toBe('');
  conflict=true;
  await page.getByLabel('캠페인 이름',{exact:true}).fill('충돌 시 입력 유지');
  await page.getByRole('button',{name:'초안 저장 후 확인'}).click();
  await expect(page.getByRole('button',{name:'최신 내용 불러오기'})).toBeVisible();
  await expect(page.getByLabel('캠페인 이름',{exact:true})).toHaveValue('충돌 시 입력 유지');
  await page.getByRole('button',{name:'최신 내용 불러오기'}).click();
  await expect(page.getByLabel('캠페인 이름',{exact:true})).toHaveValue('재구매 캠페인');
  conflict=false;
  await page.getByRole('button',{name:'삭제',exact:true}).click();
  await expect(page.getByRole('button',{name:'삭제 확인',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'삭제 확인',exact:true}).click();
  await expect(page.getByText('캠페인 0개',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/campaigns.png',fullPage:true});
});

test('approved campaign starts one simulated run and shows completion',async ({page})=>{
  const runId='44444444-4444-4444-8444-444444444444',jobId='55555555-5555-4555-8555-555555555555';
  const dataset={id,name:'체험용 샘플',purpose:'ANALYSIS',source:'DEMO',customer_count:300,order_count:900,event_count:6000,version:1,reference_at:'2026-09-19T00:00:00Z',created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z'};
  const variants=['A','B'].map((variant_name,index)=>({id:index?runId:revision,variant_name,subject:variant_name,body:'15% 할인 쿠폰',hypothesis:variant_name,allocation_bp:5000}));
  let status='APPROVED',version=3,run=null,key=null;
  const detail=()=>({id:campaign,dataset_id:id,name:'승인 캠페인',objective:'재구매',channel:'EMAIL',benefit:'15% 할인 쿠폰',brand_tone:'다정하게',primary_kpi:'conversion_rate',target_value:'5.00',segment_revision_id:revision,exclusion_revision_ids:[],planned_at:null,coupon_expires_at:null,status,version,variants});
  await page.route('**/api/v1/**',route=>{
    const url=new URL(route.request().url()),path=url.pathname,method=route.request().method();
    if(path.endsWith('/datasets'))return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/segments'))return route.fulfill({json:{items:[{id:revision,revision_id:revision,name:'휴면 VIP'}],total:1,page:1,page_size:100}});
    if(path.endsWith('/copy-policy'))return route.fulfill({json:{version:1,channels:{EMAIL:{subject_max:120,body_max:5000},PUSH:{subject_max:60,body_max:300},SMS:{subject_max:0,body_max:500}}}});
    if(path.endsWith('/review'))return route.fulfill({json:{campaign:detail(),validation:{id:revision,passed:true,expires_at:'2099-09-20T00:00:00Z',campaign_version:1,initial_count:30,excluded_count:0,eligible_count:30,rules:[],blockers:[]},approval:{id:revision,status:'APPROVED'}}});
    if(path.endsWith('/simulate-send')&&method==='POST'){
      key=route.request().headers()['idempotency-key'];status='RUNNING';version=4;
      run={id:runId,campaign_id:campaign,job_id:jobId,status:'PENDING',reserved_count:30,excluded_count:0,sent_count:0,failed_count:0};
      return route.fulfill({status:202,json:run});
    }
    if(path.endsWith(`/runs/${runId}`)){status='COMPLETED';version=5;run={...run,status:'COMPLETED',sent_count:29,failed_count:1,
      failure_summary:{SYSTEM_ERROR:1},variant_summary:[{variant_name:'A',sent:14,failed:1,total:15},{variant_name:'B',sent:15,failed:0,total:15}],
      event_summary:{DELIVERED:29,OPEN:17,CLICK:8,CONVERSION:3,UNSUBSCRIBE:1}};return route.fulfill({json:run});}
    if(path.endsWith('/runs'))return route.fulfill({json:{run}});
    if(path.endsWith(campaign))return route.fulfill({json:detail()});
    if(path.endsWith('/campaigns'))return route.fulfill({json:{items:[detail()],total:1,page:1,page_size:20}});
    return route.fulfill({status:404,json:{error:{message:'테스트 범위 밖'}}});
  });
  await page.goto(`/#/campaigns?dataset=${id}`);
  await expect(page.getByText('승인 캠페인',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'모의 발송',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'삭제',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'모의 발송',exact:true}).click();
  await expect.poll(()=>key).toBeTruthy();
  await expect(page.getByRole('button',{name:'발송·결과',exact:true})).toHaveAttribute('aria-current','page');
  await expect(page.locator('.run-metrics')).toContainText('발송 성공29명');
  await expect(page.locator('.run-metrics')).toContainText('발송 실패1명');
  await expect(page.locator('.run-breakdown')).toContainText('시뮬레이터 전송 실패1명');
  await expect(page.locator('.campaign-results').getByText('A안',{exact:true})).toBeVisible();
  await expect(page.locator('.campaign-results').getByText('전환',{exact:true})).toBeVisible();
  await expect(page.getByText('✓ 발송 완료',{exact:true})).toBeVisible();
});
