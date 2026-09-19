import {el} from './dom.js';
/** Render actual counts with an equivalent accessible table; no invented series. */
export function sourceChart(items) {
  const values = ['DEMO', 'UPLOADED', 'SIMULATED'].map(name => ({name, count: items.filter(item => item.source === name).length}));
  const figure = el('figure', {className: 'card', style: 'margin:0'}, el('figcaption', {text: '현재 페이지 데이터셋의 원천 구분'}));
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 250 100'); svg.setAttribute('aria-hidden', 'true');
  const max = Math.max(1, ...values.map(v => v.count));
  values.forEach((value, index) => {
    const rect = document.createElementNS(svg.namespaceURI, 'rect');
    for (const [key, val] of Object.entries({x: 0, y: 10 + index * 30, width: value.count / max * 240, height: 18, rx: 4, fill: ['#247b5c', '#78ad82', '#bdd3b2'][index]})) rect.setAttribute(key, val);
    svg.append(rect);
  });
  const table = el('table', {}, el('caption', {className: 'sr-only', text: '그래프와 동일한 원천별 데이터셋 수'}),
    el('thead', {}, el('tr', {}, el('th', {text: '원천', scope: 'col'}), el('th', {text: '건수', scope: 'col'}))),
    el('tbody', {}, ...values.map(v => el('tr', {}, el('th', {text: v.name, scope: 'row'}), el('td', {text: v.count})))));
  figure.append(el('div', {className: 'chart-layout'}, svg, table)); return figure;
}
