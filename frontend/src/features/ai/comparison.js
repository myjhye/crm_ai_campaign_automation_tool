import {el} from '../../components/dom.js';
import {routeHash} from '../../app/router.js';
import {isUUID} from '../../api/client.js';
const percent=value=>value==null?'—':`${Number(value).toFixed(2)}%`;
export function comparison(data,route){
  const koreanDate=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(value);
  const from=data.from?koreanDate(new Date(data.from)):route.from;
  const to=data.to?koreanDate(new Date(Date.parse(data.to)-1)):route.to;
  const scope=`${from} ~ ${to} · ${data.channel&&data.channel!=='ANY'?data.channel:'모든 채널'} · ${data.scope==='context'?'이전 대화의 대상 내 조회':data.scope==='dataset'?'선택 데이터셋 전체에서 조회':'조회 범위 정보 없음'}`;
  if(!data.campaigns.length)return el('section',{className:'ai-comparison-empty'},
    el('p',{className:'small muted',text:scope}),
    el('p',{text:data.scope==='context'?'이전 결과 안에는 이 조건에 맞는 캠페인이 없습니다. “전체 캠페인에서 이메일로 발송한 캠페인을 비교해줘”처럼 범위를 지정해보세요.':'조회는 정상 처리됐지만 해당 조건의 발송 기록이 없습니다. 상단 발송 기간을 넓히거나 채널 조건을 바꿔보세요.'}));
  const rows=data.campaigns.map(row=>el('tr',{},el('th',{scope:'row'},isUUID(row.campaign_id)?el('a',{text:row.name,
    href:routeHash({view:'campaigns',resource:row.campaign_id,dataset:route.dataset,from,to,tab:'results'})}):el('span',{text:row.name})),
    ...[row.channel,`${row.sent_count.toLocaleString('ko-KR')}명`,percent(row.conversion_rate),percent(row.click_rate),row.revenue==null?'—':`${Number(row.revenue).toLocaleString('ko-KR')}원`].map(text=>el('td',{text}))));
  return el('section',{className:'ai-comparison'},el('div',{className:'ai-comparison-scroll'},el('table',{},
    el('caption',{text:`${scope} · 완료 캠페인 ${data.total_matched}개 중 ${rows.length}개`}),el('thead',{},el('tr',{},...['캠페인','채널','발송','전환율','클릭률','기여 매출'].map(text=>el('th',{scope:'col',text})))),el('tbody',{},...rows))),
    el('p',{className:'small muted',text:'같은 발송 기간의 관측 성과입니다. 캠페인별 대상과 혜택이 달라 인과적인 우열을 의미하지 않습니다.'}));
}
