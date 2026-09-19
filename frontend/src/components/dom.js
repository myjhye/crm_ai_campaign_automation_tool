export function el(tag, {className, text, ...attributes} = {}, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attributes)) if (value !== undefined && value !== null) node.setAttribute(key, value);
  node.append(...children.filter(Boolean));
  return node;
}
export function button(text, callback, signal, className = 'button secondary') {
  const node = el('button', {className, text, type: 'button'});
  node.addEventListener('click', callback, {signal}); return node;
}
export function stateCard(title, message, action, error = false) {
  return el('section', {className: `state ${error ? 'error-box' : ''}`, role: error ? 'alert' : 'status'},
    el('h2', {text: title}), el('p', {text: message}), action);
}
export function loading() {
  return el('div', {className: 'state', role: 'status'}, el('span', {className: 'loading-mark', 'aria-hidden': 'true'}), el('p', {text: '데이터를 불러오고 있습니다…'}));
}
export function errorMessage(error) {
  return `${error.message || '요청에 실패했습니다.'}${error.request_id ? ` · 요청 ID: ${error.request_id}` : ''}`;
}
export function heading(title, description, action) {
  return el('div', {className: 'page-heading'}, el('div', {}, el('p', {className: 'eyebrow', text: 'YOUR GROWTH WORKSPACE'}),
    el('h1', {text: title}), el('p', {className: 'muted small', text: description})), action);
}
export function formatTime(value) {
  return value ? new Intl.DateTimeFormat('ko-KR', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Seoul'}).format(new Date(value)) : '아직 고정되지 않음';
}
