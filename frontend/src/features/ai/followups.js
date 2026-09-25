// Suggestions come from structured results; no extra model call or automatic action.
const item=(label,prompt)=>({label:label||prompt,prompt});
export function followups(message,hint){
  if(!message||message.pending||message.saving)return [];
  if(message.error)return message.prompt?[item('질문 다시 요청하기',message.prompt)]:[];
  const response=message.response;if(!response)return [];
  const data=response.data||{};
  if(response.result_type==='copy_recommendation')return [item('더 짧게 다듬어줘','방금 추천한 A/B 문구를 더 짧게 다듬어줘. 저장하지 말아줘'),item('다정한 말투로 바꿔줘','방금 추천한 A/B 문구를 다정한 말투로 바꿔줘. 저장하지 말아줘')];
  if(response.result_type==='segment_preview'){
    if(message.saved&&hint?.kind==='segment'&&hint.id===message.saved.id)return [
      item('이메일 캠페인 준비',`이 세그먼트(${hint.name})로 이메일 캠페인 초안을 만들어줘. 혜택은 15% 할인 쿠폰으로 제안해줘`),
      item('푸시 캠페인 준비',`이 세그먼트(${hint.name})에 3000원 적립금을 안내하는 푸시 초안을 만들어줘`),
      item('이 대상의 기존 캠페인 비교','이 세그먼트의 완료 캠페인을 전환율 높은 순으로 비교해줘')];
    const options=[];
    if(!data.proposal_id&&data.description&&data.description.length<1000)options.unshift(item('이 조건으로 저장 초안 만들기',`${data.description} 조건의 고객을 세그먼트로 저장할 초안으로 만들어줘`));
    if(data.proposal_id)options.push(item('조건 다시 보기',`${data.description||data.name} 조건의 고객을 다시 미리 보고 싶어`));
    return options;
  }
  if(response.result_type==='campaign_comparison'){
    if(!data.campaigns?.length)return [
      item('전체 캠페인에서 다시 찾기','선택 기간의 전체 캠페인을 모든 채널에서 전환율 높은 순으로 비교해줘'),
      item('고객 현황 살펴보기','활성 고객 수를 알려줘')];
    const subject=hint?.kind==='campaign_list'?'위 캠페인': '전체 캠페인';
    return [
      item('클릭률로 다시 비교해줘',`${subject}을 클릭률 순으로 비교해줘`),
      item('매출 상위 3개를 보여줘',`${subject} 중 매출 상위 3개를 보여줘`),
      item(data.channel==='EMAIL'?'푸시 캠페인 살펴보기':'이메일 캠페인 살펴보기',data.channel==='EMAIL'?'푸시로 발송한 캠페인들만 비교해줘':'이메일로 발송한 캠페인들만 비교해줘')];
  }
  if(response.result_type==='campaign_draft')return [item('기존 캠페인 성과 비교','선택 기간의 전체 완료 캠페인을 전환율 높은 순으로 비교해줘')];
  if(response.result_type==='clarification'&&/먼저.*(저장|세그먼트)|세그먼트를 저장/.test(response.message||'')&&hint?.kind!=='segment')return [];
  if(response.result_type==='clarification')return hint?.kind==='segment'&&/채널|혜택|캠페인/.test(response.message||'')?[
    item('채널·혜택 지정하기','이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘')]:[
    item('지원하는 지표부터 조회','활성 고객 수를 알려줘'),item('완료 캠페인 비교','선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘')];
  const keys=Object.keys(data.metrics||{});
  if(keys.includes('new_customers'))return [item('신규 미구매 고객을 찾아줘', '선택 기간에 가입했고 아직 구매하지 않은 고객을 찾아줘'),item('구매 전환율도 알려줘', '구매 전환율을 알려줘')];
  if(keys.includes('dormant_customers'))return [item('휴면 VIP를 찾아줘', '60일 이상 미구매하고 누적 구매액이 30만원 이상인 고객을 찾아줘')];
  if(keys.includes('active_customers'))return [item('구매 전환율도 알려줘', '구매 전환율을 알려줘'),item('장바구니 이탈 고객을 찾아줘', '장바구니에 담았지만 구매 이벤트가 없는 고객을 찾아줘')];
  if(keys.includes('repeat_purchase_rate'))return [item('반복 구매자를 찾아줘', '완료 주문이 3건 이상인 반복 구매자를 찾아줘'),item('이메일 동의 고객을 저장해줘', '완료 주문 3건 이상이고 이메일에 동의한 고객을 세그먼트 저장 초안으로 만들어줘')];
  if(keys.includes('purchase_conversion_rate'))return [item('장바구니 이탈 고객을 찾아줘', '장바구니 이벤트는 있지만 구매 이벤트는 없는 고객을 찾아줘'),item('신규 미구매 고객을 찾아줘', '가입 후 30일 이내이고 구매 이력이 없는 고객을 찾아줘')];
  return [
    item('휴면 VIP 찾아보기','60일 이상 구매하지 않고 누적 구매액이 30만원 이상인 고객을 찾아줘'),
    item(keys.includes('new_customers')?'활성 고객 수 확인':'신규 고객 수 확인',keys.includes('new_customers')?'활성 고객 수를 알려줘':'신규 고객 수를 알려줘'),
    item('성과 상위 캠페인 찾기','선택 기간의 완료 캠페인 중 전환율 상위 3개를 보여줘')];
}
