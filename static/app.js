import { renderCalendar } from "./calendar.js";
const $ = s => document.querySelector(s);
const main = $("#main"), dialog = $("#dialog"), selector = $("#languages");
const esc = v => String(v ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icons = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  history:'<path d="M3 11a9 9 0 1 1 2 7M3 5v6h6m3-5v6l4 2"/>',
  cards:'<path d="M4 16l-2-10 14-3 1 3"/><rect x="6" y="8" width="15" height="12" rx="2"/>',
  globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  trend:'<path d="m2 17 7-7 4 4 8-9m-6 0h6v6"/>',
  video:'<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
  article:'<path d="M12 6Q7 3 2 5v14q5-2 10 1 5-3 10-1V5q-5-2-10 1v14"/>'
};
function icon(name){return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">'+icons[name]+'</svg>'}
document.querySelectorAll("[data-icon]").forEach(el=>el.insertAdjacentHTML("afterbegin",icon(el.dataset.icon)));
let languages=[], lang=null, activities=[], cards=[], stats, days=7, filter="all", version=0;
const titles={dashboard:"Dashboard",history:"Activity history",flashcards:"Flashcards"};
const page=()=>Object.hasOwn(titles,location.hash.slice(1))?location.hash.slice(1):"dashboard";
function iso(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-")}
function local(day){return new Date(day+"T12:00:00")}
function duration(m){return (m>=60?Math.floor(m/60)+"h ":"")+(m%60||m<60?m%60+"m":"")}
async function api(path,method="GET",body){
  const r=await fetch("/api/languages"+path,{method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if(!r.ok){const data=await r.json();throw Error(typeof data.detail==="string"?data.detail:data.detail.map(e=>e.loc.at(-1)+" — "+e.msg).join(". "))}
  return r.status===204?null:r.json();
}
function notify(message){const n=$("#notice");n.textContent=message;n.hidden=false;clearTimeout(notify.timer);notify.timer=setTimeout(()=>n.hidden=true,4500)}
function choose(id){lang=id;localStorage.setItem("polyglotta.language",id);filter="all";return refresh()}
async function refresh(){
  const v=++version,now=new Date();
  selector.innerHTML=languages.map(l=>'<option value="'+l.id+'">'+esc(l.name)+'</option>').join("")+'<option value="add">＋ Add language</option>';
  selector.value=lang??"add";
  if(lang){
    const result=await Promise.all(["/activities","/cards","/statistics?days="+days+"&today="+iso(now)].map(p=>api("/"+lang+p)));
    if(v!==version)return;
    [activities,cards,stats]=result;
  }else{
    activities=[];cards=[];stats={total:0,weekly:0,by_type:{video:0,article:0},days:Array.from({length:days},(_,i)=>{const d=new Date(now);d.setDate(d.getDate()-days+i+1);return {day:iso(d),video:0,article:0}})};
  }
  render();
}
function action(name,label,id="",cls=""){return '<button class="'+cls+'" data-action="'+name+'" data-id="'+id+'">'+label+'</button>'}
function empty(type){
  const info=!lang?["globe","Add your first language","Choose a language to start your immersion journal.","language","Add language"]:
    type==="cards"?["cards","Your deck is ready","Save a word or phrase from your immersion sessions.","card","Create flashcard"]:
    ["history","No activities yet","Log a video or article to start tracking your time.","activity","Log activity"];
  return '<div class="empty">'+icon(info[0])+'<h3>'+info[1]+'</h3><p>'+info[2]+'</p>'+action(info[3],info[4]+" →","","textbtn")+'</div>';
}
function chart(){
  const max=Math.max(30,...stats.days.map(d=>d.video+d.article)), cap=Math.ceil(max/3)*3;
  const bars=stats.days.map((d,i)=>{
    const label=days===7?local(d.day).toLocaleDateString(undefined,{weekday:"short"}):i%5===0?local(d.day).getDate():"";
    return '<div class="column" title="'+d.day+': '+d.video+'m watching, '+d.article+'m reading"><div class="stack"><b class="video" style="height:'+100*d.video/cap+'%"></b><b class="article" style="height:'+100*d.article/cap+'%"></b></div><small>'+label+'</small></div>';
  }).join("");
  return '<section class="panel"><div class="panelhead"><h2>Immersion trend</h2><div class="seg">'+[7,30].map(v=>action("range",v+"D",v,v===days?"active":"")).join("")+'</div></div><div class="plot"><div class="axes">'+[3,2,1,0].map(n=>'<div class="axis"><span>'+n*cap/3+'m</span></div>').join("")+'</div><div class="bars">'+bars+'</div></div><div class="legend">'+dot("video")+'Watching '+dot("article")+'Reading</div></section>';
}
const dot=kind=>'<span class="dot '+kind+'"></span>';
function mix(){
  const share=stats.total?100*stats.by_type.video/stats.total:0;
  const bg=stats.total?'conic-gradient(#76a883 0 '+share+'%,var(--gold) '+share+'% 100%)':'#e8ede4';
  return '<section class="panel"><h2>Activity mix</h2><div class="sub">Lifetime immersion by type</div><div class="mix"><div class="ring" style="background:'+bg+'"><div><strong>'+activities.length+'</strong><small>sessions</small></div></div><div class="mixlist">'+["video","article"].map(k=>'<div>'+dot(k)+(k==="video"?"Watching":"Reading")+'<b>'+duration(stats.by_type[k])+'</b></div>').join("")+'</div></div></section>';
}
function link(url,label){return url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+label+'</a>':label}
function rows(items,full){
  if(!activities.length)return empty("activities");
  if(!items.length)return '<p class="empty">No sessions match this filter.</p>';
  return '<div>'+items.map(a=>'<div class="entry"><span class="badge '+(a.kind==="article"?"read":"")+'">'+icon(a.kind)+'</span><div class="entry-text"><b>'+link(a.url,esc(a.title))+'</b><div class="sub">'+(a.kind==="article"?"Article":"YouTube video")+' · '+esc(local(a.day).toLocaleDateString())+'</div></div><b>'+duration(a.minutes)+'</b>'+(full?'<div class="row-actions">'+action("from","Create card",a.id)+action("activity","Edit",a.id)+action("del-activities","Delete",a.id)+'</div>':'')+'</div>').join("")+'</div>';
}
function render(){
  const p=page();$("#crumb").textContent=titles[p];document.title=titles[p]+" · Polyglotta";
  document.querySelectorAll("nav a").forEach(a=>{if(a.hash==="#"+p)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
  const today=new Date().toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric",year:"numeric"});
  const h='<div class="heading"><h1>'+(p==="dashboard"?"Immersion overview":titles[p])+'</h1>';
  if(p==="dashboard"){
    main.innerHTML=h+'<span class="date">'+today+'</span></div><section class="hero"><canvas aria-hidden="true"></canvas><div class="eyebrow">TOTAL IMMERSION TIME</div><div class="number">'+Math.floor(stats.total/60)+'<em>h</em>'+stats.total%60+'<em>m</em></div><div class="week">'+icon("trend")+'<b>'+duration(stats.weekly)+'</b> in the last 7 days</div></section><div class="panels">'+chart()+mix()+'</div><section class="panel calendar-panel"></section><section class="panel"><div class="panelhead"><h2>Recent activity</h2><a href="#history" class="textbtn">View history →</a></div>'+rows(activities.slice(0,4),false)+'</section>';
    renderCalendar($(".calendar-panel"), activities, iso(new Date()));
    import("/static/globe.js").then(({drawGlobe})=>{const c=$("canvas");if(c){drawGlobe(c);globeObserver.disconnect();globeObserver.observe(c)}});
  }else if(p==="history"){
    main.innerHTML=h+'</div><section class="panel"><div class="filters"><label>Show <select id="filter"><option value="all">All activities</option><option value="video">YouTube videos</option><option value="article">Articles</option></select></label></div>'+rows(activities.filter(a=>filter==="all"||a.kind===filter),true)+'</section>';
    $("#filter").value=filter;
  }else{
    main.innerHTML=h+'<div class="inline">'+(cards.length?action("practice","Practice")+action("card","＋ Add card","","primary"):"")+'</div></div><section class="panel"><h2>Your deck</h2>'+(cards.length?cards.map(c=>'<div class="entry"><div class="entry-text"><b>'+esc(c.front)+'</b><div>'+esc(c.back)+'</div>'+link(c.url,"Source ↗")+'</div><div class="row-actions">'+action("card","Edit",c.id)+action("del-cards","Delete",c.id)+'</div></div>').join(""):empty("cards"))+'</section>';
  }
}
const globeObserver=new ResizeObserver(async entries=>{const {drawGlobe}=await import("/static/globe.js");for(const {target} of entries)if(target.isConnected)drawGlobe(target)});
function openDialog(title,content){
  $("#dialogBody").innerHTML='<h2 id="modalTitle">'+title+'</h2>'+content;
  dialog.setAttribute("aria-labelledby","modalTitle");
  if(!dialog.open)dialog.showModal();
}
function form(title,fields,submitLabel,save){
  openDialog(title,'<form>'+fields+'<p class="error" role="alert"></p><div class="foot"><button type="button" data-close>Cancel</button><button class="primary">'+submitLabel+'</button></div></form>');
  const f=dialog.querySelector("form");
  f.onsubmit=async e=>{
    e.preventDefault();
    if(f.dataset.busy)return;
    f.dataset.busy="1";
    const submit=f.querySelector(".primary");submit.disabled=true;
    try{
      const after=await save(Object.fromEntries(new FormData(f)));
      dialog.close();
      await refresh();
      if(typeof after==="function")after();
    }catch(err){if(dialog.open)f.querySelector(".error").textContent=err.message;else notify(err.message)}
    finally{delete f.dataset.busy;submit.disabled=false}
  };
}
function field(label,name,value="",type="text",attrs="required maxlength=300"){
  return '<label>'+label+'<input name="'+name+'" type="'+type+'" value="'+esc(value)+'" '+attrs+'></label>';
}
function languageForm(after){
  selector.value=lang??"add";
  form("Add a language",field("Language name","name","","text",'required maxlength="80" placeholder="e.g. Japanese"'),"Add language",async data=>{
    const l=await api("","POST",data);languages.push(l);lang=l.id;localStorage.setItem("polyglotta.language",lang);filter="all";return after;
  });
}
function activityForm(a={}){
  const path="/"+lang+"/activities"+(a.id?"/"+a.id:"");
  form(a.id?"Edit activity":"Log activity",
    '<label>Activity type<select name="kind"><option value="video">YouTube video</option><option value="article" '+(a.kind==="article"?"selected":"")+'>Article</option></select></label>'+
    field("Title","title",a.title)+field("Session date","day",a.day??iso(new Date()),"date","required")+
    field("Time spent (minutes)","minutes",a.minutes,"number","required min=1 max=1440 step=1")+
    field("Source URL (optional)","url",a.url,"url",'placeholder="https://"'),"Save activity",data=>api(path,a.id?"PUT":"POST",{...data,url:data.url||null,minutes:Number(data.minutes)}));
}
function cardForm(c={}){
  const path="/"+lang+"/cards"+(c.id?"/"+c.id:"");
  form(c.id?"Edit flashcard":"Create flashcard",["front","back"].map(k=>'<label>'+k[0].toUpperCase()+k.slice(1)+'<textarea required maxlength="4000" rows="2" name="'+k+'">'+esc(c[k])+'</textarea></label>').join("")+field("Source URL (optional)","url",c.url,"url",'placeholder="https://"'),"Save card",data=>api(path,c.id?"PUT":"POST",{...data,url:data.url||null}));
}
function practice(deck,index=0,revealed=false){
  const c=deck[index];
  openDialog("Practice",'<small>Card '+(index+1)+' of '+deck.length+' · '+(revealed?"Back":"Front")+'</small><div class="practice">'+esc(revealed?c.back:c.front)+'</div>'+(revealed?link(c.url,"Open source ↗"):"")+'<div class="foot"><button data-close>Close</button><button class="primary" id="advance">'+(!revealed?"Reveal answer":index+1===deck.length?"Finish":"Next card")+'</button></div>');
  $("#advance").focus();
  $("#advance").onclick=()=>{if(!revealed)practice(deck,index,true);else if(index+1<deck.length)practice(deck,index+1);else{dialog.close();notify("Practice complete.")}};
}
function handle(actionName,id){
  if(actionName==="language")return languageForm();
  if(actionName==="range"){days=id;return refresh()}
  if(!lang)return languageForm(()=>handle(actionName,id));
  const a=activities.find(v=>v.id===id),c=cards.find(v=>v.id===id);
  if(actionName==="activity")return activityForm(a);
  if(actionName==="card")return cardForm(c);
  if(actionName==="from")return cardForm({url:a.url});
  if(actionName==="practice")return practice([...cards]);
  if(actionName.startsWith("del-")){
    const collection=actionName.slice(4);
    const item=collection==="cards"?c.front:a.title;
    form("Delete "+(collection==="cards"?"card":"activity")+"?",'<p>'+esc(item)+'</p>',"Delete",()=>api("/"+lang+"/"+collection+"/"+id,"DELETE"));
  }
}
main.onclick=e=>{const b=e.target.closest("[data-action]");if(b)Promise.resolve(handle(b.dataset.action,Number(b.dataset.id))).catch(err=>notify(err.message))};
main.onchange=e=>{if(e.target.id==="filter"){filter=e.target.value;render()}};
dialog.onclick=e=>{if(e.target.closest("[data-close]"))dialog.close()};
selector.onchange=()=>{if(selector.value==="add")languageForm();else choose(Number(selector.value)).catch(err=>notify(err.message))};
// With no languages yet, the select contains only its add action.
selector.onpointerdown=e=>{if(!languages.length){e.preventDefault();languageForm()}};
selector.onkeydown=e=>{if(!languages.length&&["Enter"," "].includes(e.key)){e.preventDefault();languageForm()}};
$("#log").onclick=()=>handle("activity");
window.addEventListener("hashchange",()=>{if(stats)render()});
async function init(){
  languages=await api("");
  const previous=Number(localStorage.getItem("polyglotta.language"));
  lang=languages.find(l=>l.id===previous)?.id??languages[0]?.id??null;
  await refresh();
}
init().catch(err=>{main.textContent="Could not load the workspace. "+err.message});
