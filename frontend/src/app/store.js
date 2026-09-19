/** Request state is ephemeral; dataset/period/search/page live in the URL. */
let state = {route: null, selectedDataset: null, loading: false, error: null};
export const store = {
  get: () => state,
  set: patch => { state = {...state, ...patch}; return state; },
};
