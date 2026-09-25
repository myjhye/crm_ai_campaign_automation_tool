import {el, button} from '../../components/dom.js';
export function chatInput({signal,submit,clearContext,onInput}){
  const chip=el('div',{className:'ai-context-chip'});
  const suggestions=el('section',{className:'ai-followup-suggestions','aria-label':'이어지는 질문',hidden:''});
  const input=el('textarea',{id:'ai-input',rows:1,maxlength:2000,placeholder:'지표를 묻거나 다음 작업을 요청해보세요.'});
  const send=el('button',{className:'button',type:'submit',text:'전송','aria-label':'전송'});
  const bar=el('form',{className:'ai-input-bar'},el('label',{for:'ai-input',className:'sr-only',text:'AI에게 요청하기'}),input,send);
  const node=el('div',{className:'ai-composer'},suggestions,chip,bar,el('p',{className:'ai-input-help',text:'Enter 전송 · Shift+Enter 줄바꿈 · 저장은 확인 후 실행됩니다'}));
  const resize=()=>{input.style.height='auto';input.style.height=`${Math.min(input.scrollHeight,150)}px`;};
  let busy=false,composing=false;
  input.addEventListener('compositionstart',()=>{composing=true;},{signal});
  input.addEventListener('compositionend',()=>{composing=false;},{signal});
  input.addEventListener('input',()=>{onInput(input.value);resize();},{signal});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&!composing&&e.keyCode!==229){e.preventDefault();bar.requestSubmit();}},{signal});
  bar.addEventListener('submit',e=>{e.preventDefault();if(!busy&&input.value.trim())submit(input.value.trim());},{signal});
  return {node,input,fill(text){input.value=text;onInput(text);resize();input.focus({preventScroll:true});},
    suggestions(items,fill){suggestions.hidden=!items.length;suggestions.replaceChildren(el('span',{className:'small muted',text:'이어서 살펴보기'}),el('div',{className:'ai-followup-options'},...items.map(item=>button(item.label,()=>{if(!busy)fill(item.prompt);},signal,'ai-followup-question'))));},
    context(hint){chip.replaceChildren();chip.hidden=!hint;if(hint)chip.append(el('span',{text:hint.label}),button('문맥 제거',clearContext,signal,'ai-context-remove'));},
    busy(value){busy=value;input.disabled=value;send.disabled=value;send.replaceChildren(value?el('span',{className:'ai-spinner','aria-hidden':'true'}):document.createTextNode('전송'));send.setAttribute('aria-label',value?'응답 기다리는 중':'전송');}};
}
