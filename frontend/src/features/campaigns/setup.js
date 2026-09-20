import {el} from '../../components/dom.js';
import {request} from '../../api/client.js';

export function campaignSetup(route,signal){
  const root=el('fieldset',{className:'campaign-setup',hidden:''},el('legend',{text:'전체 초안 설정'}));
  const values={};
  const choice=(key,title,options,initial)=>{
    const group=el('fieldset',{className:'campaign-ai-modes'},el('legend',{text:title}));
    const checks=[];values[key]=initial;
    for(const [value,label] of options){
      const input=el('input',{type:'checkbox',value});input.checked=value===initial;checks.push(input);
      input.addEventListener('change',()=>{values[key]=value;for(const c of checks)c.checked=c.value===value;},{signal});
      group.append(el('label',{},input,el('span',{text:label})));
    }
    root.append(group);return group;
  };
  const targets=el('div',{className:'small muted',text:'대상을 불러오는 중…'});root.append(targets);
  choice('objective','목표',[['재구매 유도','재구매 유도'],['첫 구매 유도','첫 구매 유도'],['방문 유도','방문 유도']],'재구매 유도');
  choice('channel','발송 채널',[['EMAIL','이메일'],['PUSH','앱 푸시'],['SMS','SMS']],'EMAIL');
  const benefit=el('input',{type:'text',maxlength:1000,'aria-label':'전체 초안 혜택',placeholder:'예: 15% 할인 쿠폰',required:''});
  root.append(el('label',{},el('span',{text:'제공할 혜택 (필수)'}),benefit));
  choice('brand_tone','공통 말투',['다정하고 편안하게','간결하고 명확하게','차분하고 전문적으로'].map(v=>[v,v]),'다정하고 편안하게');
  choice('primary_kpi','주요 지표',[['conversion_rate','전환율 (%)'],['click_rate','클릭률 (%)'],['revenue','기여 매출 (원)']],'conversion_rate');
  const target=el('input',{type:'number',min:0,step:'0.01',value:'5','aria-label':'전체 초안 KPI 목표값',required:''});
  root.append(el('label',{},el('span',{text:'KPI 목표값 (기본 추천: 전환율 5%)'}),target));
  const focuses=['혜택 강조','관계 강조','상품 탐색 강조'].map(v=>[v,v]);
  choice('a_focus','A안 강조점',focuses,'혜택 강조');choice('b_focus','B안 강조점',focuses,'관계 강조');
  root.append(el('p',{className:'small muted',text:'그룹별 하나를 선택합니다. A/B는 같은 말투로 서로 다른 강조점을 비교하며 비율은 50:50입니다.'}));
  let loaded=false;
  (async()=>{
    try{
      const rows=[];let page=1,total=1;
      while(rows.length<total){
        const result=await request(`/segments?dataset_id=${route.dataset}&page_size=100&page=${page++}`,{signal});
        rows.push(...result.items);total=result.total;if(!result.items.length)break;
      }
      if(signal.aborted)return;
      const group=choice('segment_revision_id','초안 대상',rows.map(r=>[r.revision_id,r.name]),null);
      targets.replaceWith(group);loaded=true;
      if(!rows.length)group.append(el('p',{text:'먼저 세그먼트를 저장해주세요.'}));
    }catch{if(!signal.aborted)targets.textContent='대상을 불러오지 못했습니다. 화면을 다시 열어주세요.';}
  })();
  return {root,read(){
    if(!loaded||!values.segment_revision_id)throw new Error('초안 대상을 선택해주세요.');
    if(!benefit.value.trim())throw new Error('제공할 혜택을 입력해주세요.');
    if(!target.value||!target.checkValidity()||(values.primary_kpi!=='revenue'&&Number(target.value)>100))throw new Error('KPI 목표값을 확인해주세요. 비율은 0~100입니다.');
    if(values.a_focus===values.b_focus)throw new Error('A안과 B안의 강조점을 다르게 선택해주세요.');
    return {...values,benefit:benefit.value.trim(),target_value:target.value};
  }};
}
