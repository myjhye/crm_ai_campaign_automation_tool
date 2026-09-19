import {test, expect} from '@playwright/test';

const id = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const row = {id, name: 'Seed demo', source: 'DEMO', version: 1, reference_at: '2026-09-19T00:00:00Z', created_at: '2026-09-19T00:00:00Z', updated_at: '2026-09-19T00:00:00Z'};

async function mockAPI(page, {empty = false, conflict = false} = {}) {
  let rows = empty ? [] : [{...row}];
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const url = new URL(request.url());
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
  await expect(page.getByRole('heading', {name: 'Overview', exact: true})).toBeVisible();
  await expect(page.locator('#dataset-select')).toHaveValue(id);
  await page.locator('#period-from').fill('2026-09-01'); await page.locator('#period-to').fill('2026-09-19');
  await page.getByRole('button', {name: '기간 적용'}).click();
  await page.getByRole('link', {name: 'Customers', exact: true}).click();
  await expect(page).toHaveURL(/customers.*from=2026-09-01/);
  await page.reload(); await expect(page.locator('#period-from')).toHaveValue('2026-09-01');
  await page.getByRole('link', {name: 'Segments', exact: true}).click();
  await page.goBack(); await expect(page.getByRole('heading', {name: 'Customers', exact: true})).toBeVisible();
  await page.goForward(); await expect(page.getByRole('heading', {name: 'Segments', exact: true})).toBeVisible();
  await expect(page.locator('#ai-input')).toBeDisabled();
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
  await expect(page.getByRole('heading', {name: 'Overview', exact: true})).toBeVisible();
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
