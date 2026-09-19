import test from 'node:test';
import assert from 'node:assert/strict';
import {request, ApiError, isDataset, isPage} from '../src/api/client.js';

test('API writes encode JSON and preserve AbortSignal', async t => {
  const controller = new AbortController();
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/datasets'); assert.equal(options.signal, controller.signal);
    assert.deepEqual(JSON.parse(options.body), {name: '<script>'});
    return Response.json({ok: true});
  });
  assert.deepEqual(await request('/datasets', {method: 'POST', body: {name: '<script>'}, signal: controller.signal}), {ok: true});
});

test('HTTP conflicts keep server request IDs', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({error: {code: 'VERSION_CONFLICT', message: '최신 상태를 확인해주세요.'}}, {status: 409, headers: {'X-Request-ID': 'trace-123'}}));
  await assert.rejects(request('/datasets'), error => error instanceof ApiError && error.status === 409 && error.request_id === 'trace-123' && error.code === 'VERSION_CONFLICT');
});

test('non-JSON and malformed success responses are rejected', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => new Response('<html>error</html>', {headers: {'Content-Type': 'text/html'}}));
  await assert.rejects(request('/datasets'), {code: 'INVALID_RESPONSE'});
  mock.mock.mockImplementation(async () => Response.json({items: [], total: -1}));
  await assert.rejects(request('/datasets', {validate: isPage(isDataset)}), {code: 'INVALID_RESPONSE'});
});

test('request cancellation remains distinct from network failure', async t => {
  const mock = t.mock.method(globalThis, 'fetch', async () => {throw new DOMException('Aborted', 'AbortError');});
  await assert.rejects(request('/datasets'), {name: 'AbortError'});
  mock.mock.mockImplementation(async () => {throw new TypeError('offline');});
  await assert.rejects(request('/datasets'), {code: 'NETWORK_ERROR'});
});
