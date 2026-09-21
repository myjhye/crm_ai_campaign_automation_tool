import {test,expect} from '@playwright/test';
const datasetId='11111111-1111-4111-8111-111111111111',campaignId='33333333-3333-4333-8333-333333333333';
const dataset={id:datasetId,name:'체험용 샘플',purpose:'ANALYSIS',source:'DEMO',customer_count:300,order_count:900,event_count:6000,version:1,reference_at:'2026-09-20T00:00:00Z',created_at:'2026-09-20T00:00:00Z',updated_at:'2026-09-20T00:00:00Z'};
const experiment={status:'HOLD',winner:null,reasons:['OBSERVATION_OPEN','INSUFFICIENT_SAMPLE'],minimum_sample_per_variant:30,power_sample_per_variant:1200,primary_kpi:'conversion_rate',absolute_difference_pp:2.5,relative_uplift_percent:50,p_value:.42,a_confidence_interval:{low:1,high:8},b_confidence_interval:{low:2,high:11}};
const item={campaign:{id:campaignId,name:'휴면 VIP 재활성화',channel:'EMAIL',status:'COMPLETED',primary_kpi:'conversion_rate'},totals:{delivered_customers:100,open_customers:55,click_customers:20,conversion_customers:7,revenue:'210000.00',click_rate:{value:20},conversion_rate:{value:7}},
  variants:[{name:'A',delivered_customers:50,conversion_customers:2,conversion_rate:{value:4}},{name:'B',delivered_customers:50,conversion_customers:4,conversion_rate:{value:8}}],experiment,observation:{complete:false},contains_simulated_data:true};
test.beforeEach(async({page})=>{
  await page.route('**/api/v1/**',route=>{const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/datasets'))return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/reports/summary'))return route.fulfill({json:{campaign_count:1,delivered_customers:100,conversion_customers:7,conversion_rate:7,attributed_revenue:'210000.00',contains_simulated_data:true,incremental_metrics:{status:'not_available'}}});
    if(path.endsWith('/reports/campaigns'))return route.fulfill({json:{items:[item],total:1,page:1,page_size:20}});
    return route.fulfill({status:404,json:{error:{message:'테스트 범위 밖'}}});});
});
test('reports show common campaign metrics and a safe export link',async({page})=>{
  await page.goto(`/#/reports?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await expect(page.locator('.report-kpis').getByText('기여 매출',{exact:true})).toBeVisible();await expect(page.locator('.report-kpis').getByText('210,000원',{exact:true})).toBeVisible();
  await expect(page.getByText('휴면 VIP 재활성화')).toBeVisible();
  await expect(page.getByRole('link',{name:'CSV 다운로드'})).toHaveAttribute('href',/\/api\/v1\/reports\/export/);
});
test('experiments explain why an A/B winner is on hold',async({page})=>{
  await page.goto(`/#/experiments?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await expect(page.getByText('결론: 판단 보류')).toBeVisible();await expect(page.getByText('캠페인 결과 열기',{exact:true})).toBeVisible();
  await expect(page.getByText(/관찰 기간 진행 중 · 표본 부족/)).toBeVisible();
  await expect(page.getByRole('table',{name:'실험 통계 상세'})).toBeVisible();
  await expect(page.locator('.experiment-card .ai-performance')).toHaveClass(/is-pending/);
  await expect(page.getByText('결과 해석이 어려우신가요? AI가 도와드립니다')).toBeVisible();
});
test('experiments emphasize a statistically significant winner and its basis',async({page})=>{
  await page.route('**/api/v1/reports/campaigns?*',route=>route.fulfill({json:{items:[{...item,experiment:{...experiment,status:'WINNER',winner:'A',reasons:[],absolute_difference_pp:-12.5,p_value:.0123}}],total:1,page:1,page_size:20}}));
  await page.goto(`/#/experiments?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await expect(page.getByText('결론: A안 우세')).toBeVisible();
  await expect(page.getByText('A안이 B안보다 전환율 12.50%p 높습니다 · 95% 유의수준 기준 유의')).toBeVisible();
  await expect(page.locator('.experiment-bar').last()).toHaveClass(/is-leader/);
  await expect(page.getByText('AI가 분석하고 후속 캠페인 초안을 제안합니다')).toBeVisible();
});
test('experiments render no significant difference as a neutral verdict and collapse duplicate names',async({page})=>{
  const noDifference={...experiment,status:'HOLD',winner:null,reasons:['NO_SIGNIFICANT_DIFFERENCE'],absolute_difference_pp:-1.13,p_value:.27};
  await page.route('**/api/v1/reports/campaigns?*',route=>route.fulfill({json:{items:[{...item,campaign:{...item.campaign,name:'첫 구매 유도 · 첫 구매 유도'},variants:[{...item.variants[0],conversion_rate:{value:3.27}},{...item.variants[1],conversion_rate:{value:2.15}}],experiment:noDifference}],total:1,page:1,page_size:20}}));
  await page.goto(`/#/experiments?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await expect(page.getByRole('heading',{name:'첫 구매 유도',exact:true})).toBeVisible();
  await expect(page.locator('.experiment-conclusion')).toHaveClass(/is-uncertain/);
  await expect(page.getByText(/A안이 수치상 우세하지만.*통계적으로 유의한 차이는 확인되지 않았습니다/)).toBeVisible();
  await expect(page.locator('.experiment-bar.is-leader')).toHaveCount(1);
  await expect(page.getByText(/권장: 표본을 늘려 재검증하세요/)).toBeVisible();
  const widths=await page.locator('.experiment-bar').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().width));
  expect(widths[1]/widths[0]).toBeCloseTo(2.15/3.27,2);
  expect(await page.locator('.experiment-bar').first().evaluate(n=>n.getBoundingClientRect().width/n.parentElement.getBoundingClientRect().width)).toBeCloseTo(3.27/5,2);
  await expect(page.getByText('자세히 보기',{exact:true})).toHaveCount(0);
  await expect(page.getByText(/A안 95% CI/)).toBeVisible();
  await expect(page.getByText('0.27',{exact:true})).toBeVisible();
  await expect(page.getByText('결과와 다음 실험 방향을 AI에게 물어보세요')).toBeVisible();
  await page.screenshot({path:'test-results/experiments-conclusion.png',fullPage:true});
});

test('AI analysis separates evidence and hypotheses and saves only after confirmation',async({page})=>{
  let analyses=0,saves=0;
  await page.route('**/api/v1/ai/performance-analysis',async route=>{
    analyses++;const body=route.request().postDataJSON();
    expect(body.campaign_id).toBe(campaignId);expect(body.dataset_id).toBe(datasetId);
    await route.fulfill({json:{result_type:'performance_analysis',mode:'mock',data:{campaign_id:campaignId,
      reference_at:'2026-09-20T00:00:00Z',experiment,
      facts:[{metric_id:'A.conversion_rate',label:'A안 전환율',value:'4',unit:'%'}],
      hypotheses:['문안 차이의 영향은 검증 전 가설입니다.'],limitations:['모의 성과이며 실제 사업 성과가 아닙니다.'],
      recommended_actions:[{code:'RETEST',text:'표본을 늘려 재검증하세요.'}],
      proposal:{proposal_id:'55555555-5555-4555-8555-555555555555',expires_at:'2099-09-20T00:30:00Z',draft:{name:'후속 실험',channel:'EMAIL',benefit:'15% 할인 쿠폰',variants:[{variant_name:'A',allocation_bp:5000,subject:'A 제목',body:'기존 혜택 문안'},{variant_name:'B',allocation_bp:5000,subject:'B 제목',body:'기존 관계 문안'}]}}}}});
  });
  await page.route('**/api/v1/ai/actions/*/confirm',async route=>{
    saves++;expect(route.request().postDataJSON()).toEqual({dataset_id:datasetId});
    await route.fulfill({json:{id:'66666666-6666-4666-8666-666666666666',status:'DRAFT'}});
  });
  await page.goto(`/#/experiments?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  const cta=page.locator('.experiment-card .ai-performance');
  const requestButton=cta.getByRole('button',{name:'✦ AI 성과 분석 요청',exact:true});
  await expect(cta.locator('.ai-performance-output')).toBeHidden();
  await expect(page.getByRole('button',{name:'캠페인 결과 열기'})).toBeVisible();
  await requestButton.click();
  await expect(page).toHaveURL(new RegExp(`/experiments/${campaignId}.*tab=ai-analysis`));
  await expect(page.getByRole('heading',{name:'💡 AI 해석'})).toBeVisible();
  await expect(page.getByRole('region',{name:'성과 요약'})).toContainText('4%');
  await expect(page.locator('.analysis-limits')).not.toHaveAttribute('open','');
  await expect(page.locator('.analysis-copy-variant')).toHaveCount(2);
  await expect(page.locator('.experiment-card')).toHaveCount(0);
  await expect(page.getByText('기존 혜택 문안')).toBeVisible();
  expect(analyses).toBe(1);expect(saves).toBe(0);
  await page.getByRole('button',{name:'확인 후 후속 초안 저장'}).click();
  await expect(page.getByText(/후속 캠페인 초안을 저장했습니다/)).toBeVisible();
  await expect(page.getByRole('button',{name:'저장된 초안 열기'})).toBeVisible();
  await expect(page.getByRole('button',{name:'확인 후 후속 초안 저장'})).toHaveCount(0);
  expect(saves).toBe(1);
  await page.getByRole('button',{name:'실험 결과',exact:true}).click();
  await page.getByRole('button',{name:'✦ AI 분석 결과 보기',exact:true}).click();
  await expect(page.getByRole('button',{name:'저장된 초안 열기'})).toBeVisible();
  expect(analyses).toBe(1);
  await page.getByRole('button',{name:'다시 분석',exact:true}).click();
  await expect(page.getByRole('button',{name:'확인 후 후속 초안 저장'})).toBeVisible();
  expect(analyses).toBe(2);
  await page.screenshot({path:'test-results/ai-performance.png',fullPage:true});
});

test('failed AI analysis leaves manual statistics visible and allows retry',async({page})=>{
  await page.route('**/api/v1/ai/performance-analysis',route=>route.fulfill({status:502,json:{error:{message:'분석을 검증하지 못했습니다.'}}}));
  await page.goto(`/#/experiments?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await page.getByRole('button',{name:'✦ AI 성과 분석 요청',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('분석을 검증하지 못했습니다.');
  await expect(page.getByRole('table',{name:'실험 통계 상세'})).toBeVisible();
  await expect(page.getByRole('button',{name:'✦ AI 성과 분석 요청',exact:true})).toBeEnabled();
});

test('chat uses the selected completed campaign without issuing a second analysis',async({page})=>{
  let analysisCalls=0;
  await page.route('**/api/v1/ai/status',route=>route.fulfill({json:{mode:'mock',available:true}}));
  await page.route('**/api/v1/campaigns?*',route=>route.fulfill({json:{items:[{...item.campaign,version:5}],total:1,page:1,page_size:100}}));
  await page.route('**/api/v1/ai/performance-analysis',route=>{analysisCalls++;return route.fulfill({status:500});});
  await page.route('**/api/v1/ai/chat',route=>{
    const body=route.request().postDataJSON();expect(body.analysis_campaign_id).toBe(campaignId);expect(body.validation_campaign_id).toBeUndefined();
    return route.fulfill({json:{message:'성과의 근거를 확인해주세요.',dataset_id:datasetId,mode:'mock',result_type:'performance_analysis',reference_at:dataset.reference_at,data_version:1,
      data:{campaign_id:campaignId,reference_at:dataset.reference_at,experiment,facts:[{label:'전체 전달 고객',value:'100',unit:'명'}],hypotheses:[],limitations:['합성 데이터입니다.'],recommended_actions:[{code:'REVIEW_COPY',text:'문안을 검토하세요.'}],proposal:null}}});
  });
  await page.goto(`/#/ai?dataset=${datasetId}&from=2026-09-01&to=2026-09-20`);
  await page.getByLabel('성과 분석할 캠페인').selectOption(campaignId);
  await page.getByRole('button',{name:'전송',exact:true}).click();
  await expect(page.getByText('전체 전달 고객: 100명')).toBeVisible();
  expect(analysisCalls).toBe(0);
});
