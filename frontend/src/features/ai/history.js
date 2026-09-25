// Bounded conversational context, not a source of authoritative metrics or IDs.
export function recentTurns(messages){
  return messages.filter(m=>!m.pending&&!m.error&&['user','assistant'].includes(m.role)).slice(-6).map(m=>{
    if(m.role==='user')return {role:'user',content:m.content.slice(0,2000)};
    const r=m.response,d=r?.data||{};
    let content=r?.message||m.content||'';
    if(r?.result_type==='segment_preview')content+=`\n조회한 고객 조건: ${d.description||''}`;
    if(r?.result_type==='copy_recommendation')content+='\n'+JSON.stringify({channel:d.channel,variants:d.variants});
    return {role:'assistant',content:content.slice(0,2000)};
  }).filter(t=>t.content);
}
