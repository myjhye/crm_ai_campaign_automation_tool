import {request, isUUID, isPage} from './client.js';
const isSegment = row => row && isUUID(row.id) && isUUID(row.revision_id) && typeof row.name === 'string' && Number.isInteger(row.version) && row.condition && typeof row.description === 'string' && typeof row.reference_at === 'string';
export const segments = {
  fields: signal => request('/segments/fields', {signal, validate: row => Array.isArray(row.items) && row.items.every(field => typeof field.name === 'string' && Array.isArray(field.comparisons))}),
  list: (dataset, page, signal) => request(`/segments?dataset_id=${dataset}&page=${page}`, {signal, validate: isPage(isSegment)}),
  get: (dataset, id, signal) => request(`/segments/${id}?dataset_id=${dataset}`, {signal, validate: isSegment}),
  preview: (body, signal) => request('/segments/preview', {method: 'POST', body, signal, validate: row => Number.isInteger(row.count) && Number.isInteger(row.total) && typeof row.condition_hash === 'string' && typeof row.description === 'string' && row.profile && Array.isArray(row.warnings)}),
  save: (id, body, signal) => request(id ? `/segments/${id}` : '/segments', {method: id ? 'PUT' : 'POST', body, signal, validate: isSegment}),
  archive: (row, signal) => request(`/segments/${row.id}`, {method: 'DELETE', body: {dataset_id: row.dataset_id, version: row.version}, signal, validate: isSegment}),
};
