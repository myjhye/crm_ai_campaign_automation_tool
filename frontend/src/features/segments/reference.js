import {validDate} from '../../app/router.js';

/** datetime-local values are explicitly Seoul time, independent of browser timezone. */
export function toSeoulInput(instant) {
  const value = new Date(Date.parse(instant) + 9 * 60 * 60 * 1000);
  if (!Number.isFinite(value.getTime())) throw new RangeError('올바른 기준 시점을 선택해주세요.');
  return value.toISOString().slice(0, -1).replace(/\.000$/, '');
}

export function fromSeoulInput(value) {
  const parts = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(value);
  if (!parts || !validDate(parts[1]) || Number(parts[2]) > 23 || Number(parts[3]) > 59 || Number(parts[4] || 0) > 59) {
    throw new RangeError('올바른 날짜와 시간을 선택해주세요.');
  }
  return new Date(`${value}+09:00`).toISOString();
}
