import {el, button} from '../../components/dom.js';
export function examples(fill, signal) {
  const groups=[
    ['고객 현황','지표가 실제 데이터와 연결되는지 확인해보세요.',[
      '전체 고객 수를 알려줘','활성 고객 수를 알려줘','신규 고객 수를 알려줘','휴면 고객 수를 알려줘','선택 기간의 재구매율을 알려줘']],
    ['타깃 탐색','조건을 바꿔 대상 규모와 특성을 살펴보세요.',[
      '60일 이상 구매하지 않고 누적 구매액이 30만원 이상인 고객을 찾아줘',
      '가입 후 30일 이내이고 구매 이력이 없는 고객을 찾아줘',
      '장바구니 이벤트는 있지만 구매 이벤트는 없는 고객을 찾아줘',
      '완료 주문이 3건 이상인 반복 구매자를 찾아줘',
      '모바일 랜딩 방문은 있지만 구매 이벤트가 없는 고객을 찾아줘']],
    ['세그먼트 저장 준비','초안을 검토하고 확인 버튼으로 저장합니다.',[
      '60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘',
      '가입 후 30일 이내인 미구매 고객을 신규 미구매라는 세그먼트로 저장할 초안으로 만들어줘',
      '완료 주문 3건 이상이고 이메일에 동의한 고객을 충성 고객 세그먼트 초안으로 만들어줘',
      '장바구니 이벤트가 있고 구매 이벤트가 없는 고객의 세그먼트 초안을 만들어줘']],
    ['채널별 캠페인 비교','선택한 발송 기간의 완료 캠페인을 비교합니다.',[
      '이메일로 발송한 캠페인들만 비교해줘','푸시로 발송한 캠페인들만 비교해줘',
      'SMS로 발송한 캠페인들만 비교해줘','선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘']],
    ['성과 순위 탐색','같은 기간에서 정렬 기준을 바꿔보세요.',[
      '선택 기간의 완료 캠페인 중 전환율 상위 3개를 보여줘',
      '선택 기간의 완료 캠페인 중 클릭률 상위 3개를 보여줘',
      '선택 기간의 완료 캠페인을 기여 매출이 높은 순으로 비교해줘',
      '선택 기간의 완료 캠페인을 발송 고객 수가 많은 순으로 비교해줘']]];
  const panels=groups.map(([title,description,prompts],index)=>el('section',{id:`ai-questions-${index}`},
    el('h3',{className:'sr-only',text:title}),el('p',{className:'ai-question-intro',text:description}),
    ...prompts.map(prompt=>button(prompt,()=>fill(prompt),signal,'ai-example'))));
  const buttons=groups.map(([title],index)=>{
    const node=button(title,()=>select(index),signal,'ai-category');
    node.setAttribute('aria-controls',`ai-questions-${index}`);return node;
  });
  function select(index){panels.forEach((panel,i)=>{panel.hidden=i!==index;buttons[i].setAttribute('aria-pressed',String(i===index));});}
  select(0);
  return el('section',{className:'ai-question-browser','aria-label':'업무별 시연 질문'},
    el('div',{className:'ai-categories',role:'group','aria-label':'질문 분류'},...buttons),
    el('div',{className:'ai-example-groups'},...panels));
}
