/** Request state is ephemeral; dataset/period/search/page live in the URL. */
let state = {route: null, selectedDataset: null, loading: false, error: null};
const listeners = new Set();
export const store = {
  get: () => state,
  set: patch => { state = {...state, ...patch}; listeners.forEach(fn => fn(state)); return state; },
  subscribe: callback => {listeners.add(callback); return () => listeners.delete(callback);},
};
