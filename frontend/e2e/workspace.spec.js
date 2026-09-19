import {test, expect} from '@playwright/test';
import {analyticsFixture} from './analytics-fixture.js';

const id = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const row = {id, name: 'Seed demo', source: 'DEMO', purpose: 'ANALYSIS', customer_count: 100, order_count: 300, event_count: 2000, version: 1, reference_at: '2026-09-19T00:00:00Z', created_at: '2026-09-19T00:00:00Z', updated_at: '2026-09-19T00:00:00Z'};

async function mockAPI(page, {empty = false, conflict = false} = {}) {
  let rows = empty ? [] : [{...row}];
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const url = new URL(request.url());
    const analytics = analyticsFixture(url);
    if (analytics) return route.fulfill({json: analytics});
    if (request.method() === 'POST') {
      const saved = {...row, id: other, name: request.postDataJSON().name}; rows.unshift(saved);
      return route.fulfill({status: 201, json: saved});
    }
    if (request.method() === 'PUT') {
      if (conflict) return route.fulfill({status: 409, headers: {'X-Request-ID': 'conflict-trace'}, json: {error: {code: 'VERSION_CONFLICT', message: '다른 변경이 적용되었습니다.'}}});
      const saved = rows.find(item => url.pathname.endsWith(item.id)); saved.name = request.postDataJSON().name; saved.version++;
      return route.fulfill({json: saved});
    }
    if (url.pathname === '/api/v1/datasets') return route.fulfill({json: {items: rows, total: rows.length, page: Number(url.searchParams.get('page')), page_size: Number(url.searchParams.get('page_size'))}});
    const found = rows.find(item => url.pathname.endsWith(item.id));
    return route.fulfill(found ? {json: found} : {status: 404, json: {error: {code: 'NOT_FOUND', message: '데이터셋을 찾을 수 없습니다.'}}});
  });
}

test('navigation, dates, deep links and refresh restore the workspace', async ({page}) => {
  await mockAPI(page); await page.goto('/');
  await expect(page.getByRole('heading', {name: 'Seed demo', exact: true})).toBeVisible();
  await expect(page.locator('#dataset-select')).toHaveValue(id);
  await expect(page.getByRole('region', {name: '선택한 데이터셋'})).toContainText('고객 100명 · 주문 300건 · 이벤트 2,000건');
  await expect(page.getByRole('region', {name: '선택한 데이터셋'})).toContainText('공개 체험용 데이터');
  await page.locator('#period-from').fill('2026-09-01'); await page.locator('#period-to').fill('2026-09-19');
  await page.getByRole('button', {name: '기간 적용'}).click();
  await page.getByRole('link', {name: 'Customers', exact: true}).click();
  await expect(page).toHaveURL(/customers.*from=2026-09-01/);
  await page.reload(); await expect(page.locator('#period-from')).toHaveValue('2026-09-01');
  await page.getByRole('link', {name: 'Segments', exact: true}).click();
  await page.goBack(); await expect(page.getByRole('heading', {name: 'Customers', exact: true})).toBeVisible();
  await page.goForward(); await expect(page.getByRole('heading', {name: 'Segments', exact: true})).toBeVisible();
  await expect(page.locator('#ai-panel')).toBeHidden();
});

test('empty public workspace offers data preparation', async ({page}) => {
  await mockAPI(page, {empty: true}); await page.goto('/');
  await expect(page.getByRole('heading', {name: '체험용 샘플을 만드시겠어요?'})).toBeVisible();
  await expect(page.locator('#dataset-select option')).not.toContainText(['Worker diagnostic']);
});

test('unknown or system URL is not silently replaced', async ({page}) => {
  await mockAPI(page); await page.goto(`/#/overview?dataset=${other}`);
  await expect(page.getByRole('button', {name: '데이터셋 다시 선택'})).toBeVisible();
  await expect(page).toHaveURL(new RegExp(other));
  await expect(page.getByRole('region', {name: '선택한 데이터셋'})).toHaveCount(0);
});

test('public creation and rename safely render user text', async ({page}) => {
  await mockAPI(page, {empty: true}); await page.goto('/#/data');
  await expect(page.getByText('첫 데이터셋을 만들어보세요', {exact: true})).toBeVisible();
  const name = '<img src=x onerror=alert(1)>';
  await page.getByLabel('새 공개 데이터셋 이름').fill(name);
  await page.getByRole('button', {name: '데이터셋 만들기', exact: true}).click();
  await expect(page.getByRole('heading', {name, exact: true})).toBeVisible();
  expect(await page.locator('#content img').count()).toBe(0);
  await page.getByLabel('데이터셋 이름 변경').fill('Updated demo');
  await page.getByRole('button', {name: '이름 저장'}).click();
  await expect(page.getByRole('heading', {name: 'Updated demo', exact: true})).toBeVisible();
  await page.getByLabel('현재 페이지에서 검색').fill('not-found');
  await page.getByRole('button', {name: '검색', exact: true}).click();
  await expect(page.getByText('표시할 데이터셋이 없습니다', {exact: true})).toBeVisible();
  await page.reload(); await expect(page.getByLabel('현재 페이지에서 검색')).toHaveValue('not-found');
});

test('save conflicts preserve draft and offer an explicit reload', async ({page}) => {
  await mockAPI(page, {conflict: true}); await page.goto(`/#/data?dataset=${id}`);
  await page.getByLabel('데이터셋 이름 변경').fill('Unsaved draft');
  await page.getByRole('button', {name: '이름 저장'}).click();
  await expect(page.getByText(/conflict-trace/)).toBeVisible();
  await expect(page.getByLabel('데이터셋 이름 변경')).toHaveValue('Unsaved draft');
  await page.getByRole('button', {name: '최신 데이터 불러오기'}).click();
  await expect(page.getByLabel('데이터셋 이름 변경')).toHaveValue('Seed demo');
});

test('connection errors recover and the panel does not overlap content at 1280px', async ({page}) => {
  await page.route('**/api/v1/**', route => route.fulfill({status: 503, json: {error: {message: 'DB 연결을 확인해주세요.'}}}));
  await page.goto('/'); await expect(page.getByRole('button', {name: '다시 시도'})).toBeVisible();
  await page.unroute('**/api/v1/**'); await mockAPI(page);
  await page.getByRole('button', {name: '다시 시도'}).click();
  await expect(page.getByRole('heading', {name: 'Seed demo', exact: true})).toBeVisible();
  await expect(page.locator('#ai-panel')).toBeHidden();
  await page.locator('#ai-toggle').click();
  const main = await page.locator('#content').boundingBox(); const panel = await page.locator('#ai-panel').boundingBox();
  expect(main.x + main.width).toBeLessThanOrEqual(panel.x + 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: 'test-results/overview-1280.png', fullPage: true});
  await page.getByRole('button', {name: 'AI 어시스턴트'}).click();
  await expect(page.locator('#ai-panel')).toBeHidden();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: 'test-results/overview-mobile.png', fullPage: true});
});

test('dashboard drilldown and customer profile preserve filters on reload', async ({page}) => {
  await mockAPI(page); await page.goto('/');
  await page.getByRole('button', {name: '휴면', exact: true}).click();
  await expect(page).toHaveURL(/status=DORMANT/);
  await expect(page.getByRole('combobox', {name: '고객 상태', exact: true})).toHaveValue('DORMANT');
  await page.getByLabel('고객 검색').fill('alice');
  await page.getByRole('button', {name: '고객 조회', exact: true}).click();
  await page.reload(); await expect(page.getByLabel('고객 검색')).toHaveValue('alice');
  await page.getByRole('link', {name: 'Demo customer', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Demo customer', exact: true})).toBeVisible();
  await expect(page.getByText('a***@example.invalid', {exact: true})).toBeVisible();
  await expect(page.getByRole('heading', {name: '선택 기간의 행동 타임라인'})).toBeVisible();
  await page.reload(); await expect(page.getByRole('heading', {name: '고객 프로필'})).toBeVisible();
  await page.getByRole('button', {name: '고객 목록으로'}).click();
  await expect(page.getByLabel('고객 검색')).toHaveValue('alice');
});
test('Overview renders four KPIs and proportional bars, including zero', async ({page}) => {
  await mockAPI(page);
  await page.route('**/api/v1/dashboard/segments?**', route => route.fulfill({json: {
    dataset_id: id, reference_at: row.reference_at, data_version: 1,
    period: {from: row.reference_at, to: row.reference_at},
    customer_statuses: ['ACTIVE', 'CHURN_RISK', 'DORMANT', 'WITHDRAWN'].map((status, i) => ({status, count: [100, 0, 50, 25][i]})),
  }}));
  await page.goto('/');
  await expect(page.locator('.kpi-card')).toHaveCount(4);
  await expect(page.locator('#ai-panel')).toBeHidden();
  const chart = page.getByRole('region', {name: '고객 상태 분포', exact: true});
  await expect(chart.locator('tr')).toHaveCount(4);
  const widths = await chart.locator('.data-bar').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
  expect(widths[0]).toBeGreaterThan(0);
  expect(widths[1]).toBe(0);
  expect(widths[2] / widths[0]).toBeCloseTo(0.5, 2);
  expect(widths[3] / widths[0]).toBeCloseTo(0.25, 2);
  await expect(chart.locator('.bar-number')).toHaveText(['100', '0', '50', '25']);
});
test('customer identity, status and sorting controls are clear', async ({page}) => {
  await mockAPI(page); await page.goto('/#/customers');
  await expect(page.locator('.customer-name')).toHaveText('Demo customer');
  await expect(page.locator('.customer-external')).toHaveCount(0);
  await expect(page.locator('.customers-table')).not.toContainText('customer-1');
  await expect(page.locator('.customer-status.status-ACTIVE')).toHaveText('활성');
  await expect(page.locator('#content')).not.toContainText('데이터 버전');
  await page.getByLabel('정렬 방향').selectOption('asc');
  const request = page.waitForRequest(request => request.url().includes('/customers?') && request.url().includes('direction=asc'));
  await page.getByRole('button', {name: '고객 조회', exact: true}).click();
  expect((await request).url()).toContain('sort=signup_at');
});
