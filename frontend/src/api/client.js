/** API requests are same-origin. Never render server text as HTML. */
export class ApiError extends Error {
  constructor(message, {status = 0, code = 'NETWORK_ERROR', request_id = null} = {}) {
    super(message); this.name = 'ApiError'; Object.assign(this, {status, code, request_id});
  }
}

/** @param {string} path @param {{signal?: AbortSignal, method?: string, body?: object, validate?: Function}} options */
export async function request(path, {signal, method = 'GET', body, validate} = {}) {
  if (!path.startsWith('/') || path.startsWith('//')) throw new TypeError('Relative API path required');
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {method, signal, headers: {
      Accept: 'application/json', ...(body === undefined ? {} : {'Content-Type': 'application/json'}),
    }, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('서버에 연결하지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해주세요.');
  }
  const request_id = response.headers.get('X-Request-ID');
  const metadata = {status: response.status, request_id};
  let result;
  try {
    if (!/^application\/(?:[\w.-]+\+)?json(?:;|$)/i.test(response.headers.get('Content-Type') || '')) throw new Error();
    result = await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('서버 응답 형식을 확인할 수 없습니다.', {...metadata, code: 'INVALID_RESPONSE'});
  }
  if (!response.ok) throw new ApiError(
    typeof result?.error?.message === 'string' ? result.error.message : '요청을 처리하지 못했습니다.',
    {...metadata, code: typeof result?.error?.code === 'string' ? result.error.code : 'HTTP_ERROR'},
  );
  if (validate && !validate(result)) throw new ApiError('서버 응답 데이터가 예상 형식과 다릅니다.', {...metadata, code: 'INVALID_RESPONSE'});
  return result;
}

export const isUUID = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const isTimestamp = value => typeof value === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
/** @typedef {{id:string,name:string,source:string,version:number,reference_at:string|null,created_at:string,updated_at:string}} Dataset */
/** @returns {boolean} */
export function isDataset(row) {
  return row !== null && typeof row === 'object' && isUUID(row.id) && typeof row.name === 'string'
    && ['DEMO', 'UPLOADED', 'SIMULATED'].includes(row.source) && Number.isInteger(row.version) && row.version > 0
    && isTimestamp(row.created_at) && isTimestamp(row.updated_at)
    && (row.reference_at === null || isTimestamp(row.reference_at));
}
export function isPage(itemValidator) {
  return page => page !== null && typeof page === 'object' && Array.isArray(page.items) && page.items.every(itemValidator)
    && Number.isInteger(page.total) && page.total >= page.items.length && Number.isInteger(page.page) && page.page > 0
    && Number.isInteger(page.page_size) && page.page_size >= 1 && page.page_size <= 100 && page.items.length <= page.page_size;
}
export const datasets = {
  list: (page, signal, page_size = 20) => request(`/datasets?page=${page}&page_size=${page_size}`, {signal, validate: isPage(isDataset)}),
  get: (id, signal) => request(`/datasets/${encodeURIComponent(id)}`, {signal, validate: isDataset}),
  create: (name, signal) => request('/datasets', {method: 'POST', body: {name}, signal, validate: isDataset}),
  rename: (row, name, signal) => request(`/datasets/${row.id}`, {method: 'PUT', body: {name, version: row.version}, signal, validate: isDataset}),
};
