import {test,expect} from '@playwright/test';
const id='11111111-1111-4111-8111-111111111111';
test('campaign sidebar only offers full draft and fills without saving',async({page})=>{
  let writes=0,saved=null,fail=false;
  const dataset={id,name:'샘플',source:'DEMO',purpose:'ANALYSIS',customer_count:100,order_count:300,event_count:2000,version:1,created_at:'2026-09-19T00:00:00Z',updated_at:'2026-09-19T00:00:00Z',reference_at:'2026-09-19T00:00:00Z'};
  await page.route('**/api/v1/**',route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/datasets'))return route.fulfill({json:{items:[dataset],total:1,page:1,page_size:100}});
    if(path.endsWith('/segments'))return route.fulfill({json:{items:[{id,revision_id:id,name:'VIP'}],total:1,page:1,page_size:100}});
    if(path.endsWith('/status'))return route.fulfill({json:{mode:'mock',available:true}});
    if(path.endsWith('/copy-policy'))return route.fulfill({json:{version:1,channels:{EMAIL:{subject_max:120,body_max:5000},PUSH:{subject_max:60,body_max:300},SMS:{subject_max:0,body_max:500}}}});
    if(path.endsWith('/campaign-draft'))return fail?route.fulfill({status:502,json:{error:{message:'생성 실패'}}}):route.fulfill({json:{mode:'mock',result_type:'campaign_draft',data:{variants:['A','B'].map(n=>({variant_name:n,subject:n+' 혜택 안내',body:'10% 할인',hypothesis:'반응 비교'}))}}});
    if(route.request().method()==='POST'){writes++;saved={...route.request().postDataJSON(),id,version:1,status:'DRAFT'};return route.fulfill({json:saved});}
    return route.fulfill({json:path.endsWith('/'+id)?saved:{items:[],total:0,page:1,page_size:20}});
  });
  await page.goto('/#/campaigns');
  const setupPanel=page.locator('.campaign-setup');
  await expect(setupPanel).toHaveCSS('overflow-y','visible');
  await page.getByRole('button',{name:'전체 초안 만들기',exact:true}).scrollIntoViewIfNeeded();
  await expect(page.getByRole('button',{name:'전체 초안 만들기',exact:true})).toBeVisible();
  await expect(page.getByRole('checkbox',{name:'카피만 수정',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'AI로 A/B 카피 채우기'})).toHaveCount(0);
  let generations=0;
  const expected={segment_revision_id:id,benefit:'15% 할인 쿠폰',brand_tone:'다정하고 편안하게',a_focus:'혜택 강조',b_focus:'관계 강조',target_value:'5'};
  await page.route('**/ai/campaign-plan',route=>{
    const setup=route.request().postDataJSON().campaign_setup;
    expect(setup).toMatchObject(expected);generations++;
    return route.fulfill({json:{cache_hit:generations>1,result_type:'campaign_draft',segment_name:'VIP',notice:'추천값을 확인해주세요.',data:{name:'AI 전체 초안',objective:setup.objective,channel:'EMAIL',benefit:setup.benefit,brand_tone:setup.brand_tone,primary_kpi:'conversion_rate',target_value:'5',segment_revision_id:id,variants:['A','B'].map(n=>({variant_name:n,subject:n,body:'Copy',hypothesis:'Test',allocation_bp:5000}))}}});
  });
  await expect(page.getByRole('button',{name:'초기화',exact:true})).toBeVisible();
  await page.getByLabel('AI 카피 요청').fill('');
  await page.getByRole('button',{name:'전체 초안 만들기',exact:true}).click();
  await expect(page.getByText('초안 대상을 선택해주세요.',{exact:true})).toBeVisible();
  await page.getByRole('group',{name:'초안 대상',exact:true}).getByRole('checkbox',{name:'VIP',exact:true}).check();
  await page.getByLabel('전체 초안 혜택',{exact:true}).fill('15% 할인 쿠폰');
  await page.getByRole('button',{name:'전체 초안 만들기',exact:true}).click();
  await expect(page.getByLabel('캠페인 이름',{exact:true})).toHaveValue('AI 전체 초안');
  await expect(page.getByRole('button',{name:'확인 후 메인 폼에 적용'})).toHaveCount(0);
  const toast=page.locator('.campaign-ai-success');
  await expect(toast).toBeVisible();
  await expect(toast).toHaveCount(0,{timeout:6000});
  expect(writes).toBe(0);
  for(const [title,key,value] of [['목표','objective','감사 인사 전하기'],['공통 말투','brand_tone','담백한 편지처럼'],['A안 강조점','a_focus','감사 중심'],['B안 강조점','b_focus','탐색 중심']]){
    const group=page.getByRole('group',{name:title,exact:true});
    await group.getByRole('checkbox',{name:'기타 (직접 입력)',exact:true}).check();
    await page.getByRole('button',{name:'전체 초안 만들기',exact:true}).click();
    await expect(page.getByText(`${title}의 기타 내용을 입력해주세요.`,{exact:true})).toBeVisible();
    await page.getByLabel(`${title} 기타 입력`,{exact:true}).fill(value);
    expected[key]=value;
  }
  expect(generations).toBe(1);
  await page.getByRole('button',{name:'전체 초안 만들기',exact:true}).click();
  await expect(toast).toContainText('같은 설정의 이전 초안을 불러왔습니다.');
  await expect(page.getByLabel('캠페인 목표',{exact:true})).toHaveValue('감사 인사 전하기');
  await page.getByRole('group',{name:'공통 말투',exact:true}).getByRole('checkbox',{name:'다정하고 편안하게',exact:true}).check();
  await expect(page.getByLabel('공통 말투 기타 입력',{exact:true})).toBeHidden();
  await page.getByRole('group',{name:'공통 말투',exact:true}).getByRole('checkbox',{name:'기타 (직접 입력)',exact:true}).check();
  await expect(page.getByLabel('공통 말투 기타 입력',{exact:true})).toHaveValue('담백한 편지처럼');
  await page.screenshot({path:'test-results/ai-campaigns.png',fullPage:true});
  await page.goto('/#/ai');
  await expect(page.getByText('캠페인 생성·카피 변경 설정',{exact:true})).toHaveCount(0);
});
