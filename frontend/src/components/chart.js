import {el, button} from './dom.js';
import {sourceNames} from './dataset.js';
export function barPercentages(rows) {
  const maximum = Math.max(0, ...rows.map(row => row.count));
  return rows.map(row => maximum === 0 ? 0 : row.count / maximum * 100);
}
export function barChart(title, rows, signal, onClick) {
  const widths = barPercentages(rows);
  return el('section', {className: 'card bar-chart', 'aria-label': title},
    el('h2', {className: 'card-header', text: title}),
    el('table', {}, el('caption', {className: 'sr-only', text: title}),
      el('tbody', {}, ...rows.map((row, index) => el('tr', {'data-count': row.count},
        el('th', {scope: 'row'}, onClick ? button(row.label, () => onClick(row), signal, 'chart-label') : el('span', {text: row.label})),
        el('td', {className: 'bar-cell', 'aria-hidden': 'true'}, el('div', {className: 'bar-track'},
          el('span', {className: 'data-bar', style: `width:${widths[index]}%`}))),
        el('td', {className: 'bar-number', text: row.count.toLocaleString('ko-KR')}))))));
}
export function sourceChart(items) {
  return barChart('현재 페이지 데이터셋의 원천 구분', ['DEMO', 'UPLOADED', 'SIMULATED'].map(source => ({
    label: sourceNames[source], count: items.filter(item => item.source === source).length,
  })));
}
