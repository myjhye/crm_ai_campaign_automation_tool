import {el} from '../../components/dom.js';
import {routeHash} from '../../app/router.js';
import {isUUID} from '../../api/client.js';
const percent=value=>value==null?'—':`${Number(value).toFixed(2)}%`;
export function comparison(data,route){
  if(!data.campaigns.length)return el('p',{text:'조건에 맞는 완료 캠페인이 없습니다. 기간이나 문맥을 바꿔 다시 조회해주세요.'});
  const koreanDate=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(value);
  const from=data.from?koreanDate(new Date(data.from)):route.from;
  const to=data.to?koreanDate(new Date(Date.parse(data.to)-1)):route.to;
  const rows=data.campaigns.map(row=>el('tr',{},el('th',{scope:'row'},isUUID(row.campaign_id)?el('a',{text:row.name,
    href:routeHash({view:'campaigns',resource:row.campaign_id,dataset:route.dataset,from,to,tab:'results'})}):el('span',{text:row.name})),
    ...[row.channel,`${row.sent_count.toLocaleString('ko-KR')}명`,percent(row.conversion_rate),percent(row.click_rate),row.revenue==null?'—':`${Number(row.revenue).toLocaleString('ko-KR')}원`].map(text=>el('td',{text}))));
  return el('section',{className:'ai-comparison'},el('div',{className:'ai-comparison-scroll'},el('table',{},
    el('caption',{text:`${from} ~ ${to} · 완료 캠페인 ${data.total_matched}개 중 ${rows.length}개`}),el('thead',{},el('tr',{},...['캠페인','채널','발송','전환율','클릭률','기여 매출'].map(text=>el('th',{scope:'col',text})))),el('tbody',{},...rows))),
    el('p',{className:'small muted',text:'같은 발송 기간의 관측 성과입니다. 캠페인별 대상과 혜택이 달라 인과적인 우열을 의미하지 않습니다.'}));
}
