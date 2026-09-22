import {el, button} from '../../components/dom.js';
export function examples(fill, signal) {
  const groups=[['데이터 조회',['활성 고객 수를 알려줘','신규 고객 수를 알려줘']],
    ['세그먼트 만들기',['60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘']],
    ['캠페인 비교',['선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘']]];
  return el('div',{className:'ai-example-groups'},...groups.map(([title,prompts])=>el('section',{},
    el('h3',{text:title}),...prompts.map(prompt=>button(prompt,()=>fill(prompt),signal,'ai-example')))));
}
