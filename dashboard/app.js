"use strict";
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icons = {
 activity:'<path d="M2 12h5l3-8 5 16 3-8h4"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 wind:'<path d="M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h7a3 3 0 1 1-3 3"/>',
 bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
 database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/>',
 flow:'<rect x="8" y="2" width="8" height="5" rx="1"/><rect x="1" y="17" width="8" height="5" rx="1"/><rect x="15" y="17" width="8" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/>',
 code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
 server:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h.1M7 17h.1M16 6h2M16 17h2"/>',
 external:'<path d="M14 3h7v7M10 14 21 3M11 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6"/>',
 logout:'<path d="M9 3H4v18h5M8 12h13m-5-5 5 5-5 5"/>',
 refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
 shield:'<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6zM8 12l3 3 5-6"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.1"/>',
 menu:'<path d="M3 6h18M3 12h18M3 18h18"/>'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.activity}</svg>`;
document.querySelectorAll("[data-icon]").forEach(el => el.innerHTML = icon(el.dataset.icon));
const state = {data:null,csrf:null,view:"overview",auto:true,range:"7d",overviewDevice:null,device:"all",readingRange:"all",alarmStatus:"all",table:"readings",search:"",sort:"id",direction:-1,page:0,flowId:null};
const pages = {
 overview:["Overblik","Overblik","Vindmålinger og alarmer samlet ét sted."],
 readings:["Vindmålinger","Vindmålinger","Se udviklingen og find målinger fra den enkelte installation."],
 alarms:["Alarmer","Alarmer","Følg aktive og kvitterede alarmer på tværs af installationer."],
 database:["Database","Database","Undersøg målinger, hændelser og alarmer fra din eksisterende database."],
 flow:["Hændelser","Hændelsesforløb","Se præcis hvilke hændelser og alarmer der hører til en måling."],
 test:["Send måling","Send en måling","Indtast en installation og vindhastighed for at teste API’et."]
};
const date = (value, short=false) => value ? new Date(value).toLocaleString("da-DK",short?{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}:{dateStyle:"short",timeStyle:"medium"}) : "—";
const num = (value) => Number(value).toLocaleString("da-DK", {maximumFractionDigits:2});
const badge = (value) => value === "active" ? '<span class="badge bad">Aktiv</span>' : value === "acknowledged" ? '<span class="badge good">Kvitteret</span>' : `<span class="badge neutral">${esc(value)}</span>`;
function toast(message){$("toast").textContent=message;$("toast").hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$("toast").hidden=true,4500);}
function showLogin(message="") {state.csrf=null;state.data=null;$("application").hidden=true;$("loginScreen").hidden=false;$("loginError").textContent=message;}
function enter(){ $("loginScreen").hidden=true;$("application").hidden=false;const hash=location.hash.slice(1);navigate(pages[hash]?hash:"overview",false);refresh(); }
async function request(path, method="GET", data){
 const headers={};if(data!==undefined)headers["Content-Type"]="application/json";
 if(method!=="GET"&&state.csrf)headers["X-CSRF-Token"]=state.csrf;
 const response=await fetch(`/dashboard/${path}`,{method,headers,body:data!==undefined?JSON.stringify(data):undefined,credentials:"same-origin",cache:"no-store",signal:AbortSignal.timeout(15000)});
 const body=await response.json();
 if(response.status===401 && path!=="login"){showLogin("Sessionen er udløbet. Log ind igen.");throw new Error("Log ind igen.");}
 return {response,body};
}
$("loginForm").addEventListener("submit",async e=>{e.preventDefault();const button=e.currentTarget.querySelector("button");button.disabled=true;$("loginError").textContent="";
 try {const {response,body}=await request("login","POST",{password:$("password").value});if(!response.ok)throw new Error(typeof body.detail==="string"?body.detail:"Login mislykkedes.");state.csrf=body.csrf_token;$("password").value="";enter();}
 catch(error){$("loginError").textContent=error.message.includes("fetch")?"Serveren svarer ikke. Kontrollér at Docker kører.":error.message;}finally{button.disabled=false;}
});
$("logout").addEventListener("click",async()=>{try{await request("logout","POST");showLogin();}catch(e){toast(e.message);}});
function navigate(view,updateHash=true){
 if(!pages[view])view="overview";state.view=view;
 document.querySelectorAll(".view").forEach(el=>el.hidden=el.id!==`view-${view}`);
 document.querySelectorAll(".nav-item").forEach(el=>el.classList.toggle("active",el.dataset.view===view));
 $("breadcrumb").textContent=pages[view][0];$("pageTitle").textContent=pages[view][1];$("pageDescription").textContent=pages[view][2];
 $("sidebar").classList.remove("open");if(updateHash)history.replaceState(null,"",`#${view}`);if(state.data)renderView();
}
document.addEventListener("click",e=>{const nav=e.target.closest("[data-view]");if(nav)navigate(nav.dataset.view);const flow=e.target.closest("[data-flow]");if(flow)openFlow(Number(flow.dataset.flow));const detail=e.target.closest("[data-detail]");if(detail)details(detail.dataset.kind,Number(detail.dataset.detail));const ack=e.target.closest("[data-ack]");if(ack)acknowledge(Number(ack.dataset.ack),ack);});
window.addEventListener("hashchange",()=>navigate(location.hash.slice(1),false));
$("menuButton").addEventListener("click",()=>$("sidebar").classList.toggle("open"));
$("autoButton").addEventListener("click",()=>{state.auto=!state.auto;$("autoButton").setAttribute("aria-pressed",String(state.auto));$("autoButton").textContent=state.auto?"Live · 5 sek.":"Opdatering pauset";if(state.auto)refresh();});
$("refreshButton").addEventListener("click",()=>refresh());
let refreshing=null;
async function refresh(force=false){
 if(!state.csrf)return;
 if(refreshing){await refreshing;if(!force)return;}
 refreshing=(async()=>{try{const {response,body}=await request("data");if(!response.ok)throw new Error("Data kunne ikke hentes.");state.data=body;
  $("connectionError").hidden=body.database_status==="connected"&&!body.errors.length;
  $("connectionError").textContent=body.database_status!=="connected"?"API'et svarer, men databasen er utilgængelig. Kontrollér MySQL-containeren.":body.errors.join(" ");
  $("liveBadge").className="badge "+(body.database_status==="connected"?"good":"warning");$("liveBadge").textContent=body.database_status==="connected"?"● Systemet svarer":"● Database afbrudt";
  $("lastUpdated").textContent="Opdateret "+new Date().toLocaleTimeString("da-DK");$("sideThreshold").textContent=body.threshold;$("legendThreshold").textContent=body.threshold;
  $("navAlarmCount").textContent=body.database_status==="connected"?body.alarms.filter(a=>a.status==="active").length:"—";
  renderView();
 }catch(e){if(state.csrf){$("connectionError").hidden=false;$("connectionError").textContent="Forbindelsen er afbrudt. Eventuelt viste data er fra sidste opdatering. "+e.message;$("liveBadge").className="badge bad";$("liveBadge").textContent="● Offline";const card=document.querySelector("#kpis .kpi-value");if(card){card.textContent="Offline";card.className="kpi-value wind-high";}}}
 finally{$("refreshButton").disabled=false;}})();
 $("refreshButton").disabled=true;await refreshing;refreshing=null;
}
setInterval(()=>{if(state.auto&&state.csrf&&!document.hidden)refresh();},5000);
function latestFirst(rows){return [...rows].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at)||b.id-a.id);}
function renderView(){if(!state.data)return;({overview:renderOverview,readings:renderReadings,alarms:renderAlarms,database:renderDatabase,flow:renderFlow,test:()=>{}})[state.view]();}
function renderOverview(){
 const devices=[...new Set(state.data.readings.map(r=>r.device_id))].sort();
 if(state.overviewDevice===null)state.overviewDevice=devices.includes("VINDMOELLE-01")?"VINDMOELLE-01":devices.includes("SIM-WIND-01")?"SIM-WIND-01":"all";
 const select=$("overviewDevice");
 const options='<option value="all">Alle installationer</option>'+devices.map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join("");
 if(select.innerHTML!==options)select.innerHTML=options;
 select.value=state.overviewDevice;

 const d=state.data,ready=d.database_status==="connected",latest=latestFirst(d.readings)[0],active=latestFirst(d.alarms.filter(a=>a.status==="active"));
 const cards=[
  ["API STATUS","Online","Forbindelse til FastAPI","activity","teal",false],
  ["DATABASE",ready?"Connected":"Disconnected",ready?"Database-health bekræftet":"MySQL svarer ikke","database",ready?"teal":"wind-high",true],
  ["DOCKER","Ikke tilgængelig","Ingen adgang til Docker-socket","server","muted",true],
  ["SENSORMÅLINGER",ready?num(d.readings.length):"—","Gemte målinger i alt","wind","",false],
  ["AKTIVE ALARMER",ready?num(active.length):"—",active.length?"Afventer opmærksomhed":"Ingen aktive alarmer","bell","",false],
  ["SENESTE VIND",ready&&latest?`${num(latest.wind_speed)} <small>m/s</small>`:"—",latest?latest.device_id:"Ingen målinger endnu","activity",latest?.anomaly_detected?"wind-high":"teal",false]
 ];
 $("kpis").innerHTML=cards.map((c,i)=>`<article class="kpi ${i===4&&active.length?"alert":""}"><div class="kpi-header"><span>${c[0]}</span>${icon(c[3])}</div><div class="kpi-value ${c[4]} ${c[5]?"compact":""}">${i===5?c[1]:esc(c[1])}</div><div class="kpi-sub">${i<2?`<span class="status-dot ${i===1&&!ready?"red":""}"></span>`:""}${esc(c[2])}</div></article>`).filter((_,i)=>i!==1&&i!==2).join("");
 const chartLatest=chartRows().at(-1);$("chartLatest").textContent=chartLatest?`${num(chartLatest.wind_speed)} m/s`:"—";
 $("alarmMiniCount").textContent=active.length;
 $("recentAlarms").innerHTML=active.length?active.slice(0,4).map(a=>`<div class="alarm-mini"><span class="status-dot red"></span><div><strong>${esc(a.device_id)}</strong><p>${esc(a.message)}</p><button class="text-link" data-flow="${a.reading_id}">Måling #${a.reading_id} →</button></div><span class="alarm-time">${date(a.created_at,true)}</span></div>`).join(""):'<div class="empty">Ingen aktive alarmer.<br>Driften kræver ingen kvittering lige nu.</div>';
 $("recentReadings").innerHTML=readingTable(latestFirst(d.readings).slice(0,5));
 $("systemStrip").innerHTML=`<span>${icon("activity")} FastAPI: ${esc(d.api_status)}</span><span>${icon("database")} Database: ${ready?"forbundet":"afbrudt"}</span>`;
 drawChart("overviewChart",chartRows());$("chartCount").textContent=`${chartRows().length} målinger i visningen`;
}
function chartRows(){const d=state.data;let rows=[...d.readings];if(state.overviewDevice!=="all")rows=rows.filter(r=>r.device_id===state.overviewDevice);if(state.range!=="all"){const cutoff=Date.now()-(state.range==="24h"?86400000:604800000);rows=rows.filter(r=>Date.parse(r.created_at)>=cutoff);}return rows.sort((a,b)=>Date.parse(a.created_at)-Date.parse(b.created_at)||a.id-b.id);}
$("overviewDevice").addEventListener("change",e=>{state.overviewDevice=e.target.value;renderOverview();});
document.querySelectorAll("[data-range]").forEach(el=>el.addEventListener("click",()=>{state.range=el.dataset.range;document.querySelectorAll("[data-range]").forEach(b=>b.classList.toggle("selected",b.dataset.range===state.range));renderOverview();}));
function drawChart(id,rows){
 const container=$(id);if(!rows.length){container.innerHTML='<div class="chart-empty">Ingen målinger i den valgte periode.<br>Prøv “Alle”, eller send en ny måling.</div>';return;}
 const W=Math.max(330,Math.min(1000,container.clientWidth-28)),H=270,L=46,R=24,T=22,B=40,threshold=state.data.threshold;
 const ymax=Math.max(40,Math.ceil(Math.max(...rows.map(r=>r.wind_speed),threshold)/10)*10+10);
 const times=rows.map(r=>Date.parse(r.created_at)),min=Math.min(...times),max=Math.max(...times);
 const x=(r)=>min===max?(W+L-R)/2:L+(Date.parse(r.created_at)-min)/(max-min)*(W-L-R);
 const y=(v)=>H-B-v/ymax*(H-T-B);
 const groups=new Map();
 for(const r of rows){if(!groups.has(r.device_id))groups.set(r.device_id,[]);groups.get(r.device_id).push(r);}
 let curves="";
 for(const series of groups.values()){
  const intervals=series.slice(1).map((r,i)=>Date.parse(r.created_at)-Date.parse(series[i].created_at)).filter(n=>n>0).sort((a,b)=>a-b);
  const gapLimit=Math.max(5400000,3*(intervals[Math.floor(intervals.length/2)]||0));
  let segment=[];
  const flush=()=>{if(segment.length>1)curves+=`<polyline data-series="${esc(series[0].device_id)}" points="${segment.map(r=>`${x(r).toFixed(2)},${y(r.wind_speed).toFixed(2)}`).join(" ")}" fill="none" stroke="#3bd9bd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;segment=[];};
  for(const r of series){if(segment.length&&Date.parse(r.created_at)-Date.parse(segment.at(-1).created_at)>gapLimit)flush();segment.push(r);}flush();
 }
 let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Vindhastigheder med grænse på ${threshold} meter pr. sekund"><defs><linearGradient id="shade-${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#3bd9bd" stop-opacity="0.18"/><stop offset="100%" stop-color="#3bd9bd" stop-opacity="0"/></linearGradient></defs>`;
 for(let i=0;i<=4;i++){const value=ymax*i/4,py=y(value);svg+=`<line x1="${L}" y1="${py}" x2="${W-R}" y2="${py}" stroke="#233147" stroke-dasharray="3 5"/><text x="${L-12}" y="${py+4}" text-anchor="end" fill="#71869f" font-size="10">${num(value)}</text>`;}
 svg+=`<text x="${L}" y="11" fill="#71869f" font-size="9">m/s</text><line x1="${L}" y1="${y(threshold)}" x2="${W-R}" y2="${y(threshold)}" stroke="#c7a06c" stroke-dasharray="5 5" opacity=".85"/><text x="${W-R}" y="${y(threshold)-7}" text-anchor="end" fill="#c7a06c" font-size="9">GRÆNSE ${threshold} m/s</text>${curves}`;
 for(const r of rows){svg+=`<circle class="chart-point" data-reading="${r.id}" tabindex="0" role="button" aria-label="${esc(r.device_id)}, ${num(r.wind_speed)} m/s, ${esc(date(r.created_at))}" cx="${x(r)}" cy="${y(r.wind_speed)}" r="${r.wind_speed>threshold?4:3}" fill="${r.wind_speed>threshold?"#fa7786":"#3bd9bd"}" stroke="#101a28" stroke-width="1.5"/>`;}
 for(let i=0;i<4;i++){const t=min+(max-min)*i/3;svg+=`<text x="${L+(W-L-R)*i/3}" y="${H-12}" text-anchor="${i===0?"start":i===3?"end":"middle"}" fill="#71869f" font-size="9">${esc(new Date(t).toLocaleString("da-DK",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}))}</text>`;}
 container.innerHTML=svg+"</svg>";
}
for(const id of ["overviewChart","readingsChart"]){const el=$(id);const show=e=>{const point=e.target.closest("[data-reading]");if(!point)return;const r=state.data.readings.find(r=>r.id===Number(point.dataset.reading));if(!r)return;const tip=$("chartTooltip");tip.textContent=`${r.device_id} · ${num(r.wind_speed)} m/s · ${date(r.created_at)}`;tip.hidden=false;const rect=point.getBoundingClientRect();tip.style.left=Math.min(window.innerWidth-tip.offsetWidth-12,(e.clientX||rect.x)+12)+"px";tip.style.top=Math.max(10,(e.clientY||rect.y)-55)+"px";};el.addEventListener("pointerover",show);el.addEventListener("pointermove",show);el.addEventListener("focusin",show);el.addEventListener("pointerout",()=>$("chartTooltip").hidden=true);el.addEventListener("focusout",()=>$("chartTooltip").hidden=true);el.addEventListener("click",e=>{const p=e.target.closest("[data-reading]");if(p){$("chartTooltip").hidden=true;openFlow(Number(p.dataset.reading));}});el.addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.dataset.reading)openFlow(Number(e.target.dataset.reading));});}
function readingTable(rows){return `<table><thead><tr><th>ID</th><th>INSTALLATION</th><th>VINDHASTIGHED</th><th>STATUS</th><th>TIDSPUNKT</th><th></th></tr></thead><tbody>${rows.length?rows.map(r=>`<tr><td class="number">#${r.id}</td><td class="device-cell">${esc(r.device_id)}</td><td class="number ${r.anomaly_detected?"wind-high":""}">${num(r.wind_speed)} <span class="muted">m/s</span></td><td><span class="badge ${r.anomaly_detected?"bad":"good"}">${r.anomaly_detected?"Overskridelse":"Normal"}</span></td><td>${date(r.created_at,true)}</td><td><button class="row-action" data-flow="${r.id}">Se forløb →</button></td></tr>`).join(""):'<tr><td colspan="6" class="empty">Ingen målinger endnu.</td></tr>'}</tbody></table>`;}
function renderReadings(){
 const devices=[...new Set(state.data.readings.map(r=>r.device_id))].sort();const select=$("deviceFilter");const options='<option value="all">Alle installationer</option>'+devices.map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join("");if(select.innerHTML!==options){select.innerHTML=options;select.value=devices.includes(state.device)?state.device:"all";state.device=select.value;}
 const cutoff=state.readingRange==="all"?0:Date.now()-(state.readingRange==="24h"?86400000:604800000);const rows=state.data.readings.filter(r=>(state.device==="all"||r.device_id===state.device)&&Date.parse(r.created_at)>=cutoff);drawChart("readingsChart",[...rows].sort((a,b)=>Date.parse(a.created_at)-Date.parse(b.created_at)||a.id-b.id));$("readingsTable").innerHTML=readingTable(latestFirst(rows).slice(0,100));$("readingsTotal").textContent=`${rows.length} målinger · viser seneste 100`;
}
document.querySelectorAll("[data-reading-range]").forEach(el=>el.addEventListener("click",()=>{state.readingRange=el.dataset.readingRange;document.querySelectorAll("[data-reading-range]").forEach(b=>b.classList.toggle("selected",b===el));renderReadings();}));
$("deviceFilter").addEventListener("change",e=>{state.device=e.target.value;renderReadings();});
function renderAlarms(){const rows=latestFirst(state.data.alarms.filter(a=>state.alarmStatus==="all"||a.status===state.alarmStatus));$("alarmsTable").innerHTML=`<table><thead><tr><th>ALARM</th><th>INSTALLATION</th><th>MÅLING</th><th>BESKED</th><th>STATUS</th><th>OPRETTET</th><th>KVITTERET</th><th></th></tr></thead><tbody>${rows.length?rows.map(a=>`<tr><td class="number">#${a.id}</td><td class="device-cell">${esc(a.device_id)}</td><td><button class="text-link" data-flow="${a.reading_id}">#${a.reading_id}</button></td><td>${esc(a.message)}</td><td>${badge(a.status)}</td><td>${date(a.created_at,true)}</td><td>${date(a.acknowledged_at,true)}</td><td>${a.status==="active"?`<button class="row-action ack" data-ack="${a.id}">Kvittér alarm</button>`:'<span class="muted">Set</span>'}</td></tr>`).join(""):'<tr><td colspan="8" class="empty">Ingen alarmer i den valgte kategori.</td></tr>'}</tbody></table>`;}
$("alarmFilters").addEventListener("click",e=>{const b=e.target.closest("[data-status]");if(!b)return;state.alarmStatus=b.dataset.status;$("alarmFilters").querySelectorAll("button").forEach(el=>el.classList.toggle("selected",el===b));renderAlarms();});
async function acknowledge(id,button){if(!confirm(`Kvittér alarm #${id}? Det betyder, at alarmen er set — ikke at fejlen er løst.`))return;button.disabled=true;
 try{const {response,body}=await request(`alarms/${id}/acknowledge`,"PATCH");if(!response.ok)throw new Error(typeof body.detail==="string"?body.detail:"Alarmen kunne ikke kvitteres.");await refresh(true);toast(`Alarm #${id} er kvitteret.`);}catch(e){toast(e.message);}finally{button.disabled=false;}
}
const columns={
 readings:[["id","ID"],["device_id","DEVICE ID"],["wind_speed","VIND m/s"],["anomaly_detected","ANOMALI"],["created_at","TIDSPUNKT"]],
 events:[["id","ID"],["event_type","EVENT TYPE"],["reading_id","READING ID"],["alarm_id","ALARM ID"],["device_id","DEVICE ID"],["payload","EVENT DATA"],["created_at","TIDSPUNKT"]],
 alarms:[["id","ID"],["reading_id","READING ID"],["device_id","DEVICE ID"],["message","BESKED"],["status","STATUS"],["created_at","OPRETTET"],["acknowledged_at","KVITTERET"]]
};
function cell(key,value){if(key.endsWith("_at"))return esc(date(value,true));if(key==="status")return badge(value);if(key==="anomaly_detected")return `<span class="badge ${value?"bad":"good"}">${value?"true":"false"}</span>`;if(key==="payload")return `<span title="Åbn detaljer for hele JSON-indholdet">${esc(JSON.stringify(value).slice(0,65))}…</span>`;return esc(value);}
function renderDatabase(){const cols=columns[state.table];let rows=state.data[state.table].filter(r=>JSON.stringify(r).toLocaleLowerCase("da").includes(state.search));rows.sort((a,b)=>{let x=a[state.sort],y=b[state.sort];if(x==null)return 1;if(y==null)return -1;if(typeof x==="number"&&typeof y==="number")return (x-y)*state.direction;return String(x).localeCompare(String(y),"da",{numeric:true})*state.direction;});const pages=Math.max(1,Math.ceil(rows.length/12));state.page=Math.min(state.page,pages-1);const shown=rows.slice(state.page*12,state.page*12+12);
 $("databaseTable").innerHTML=`<table><thead><tr>${cols.map(([k,label])=>`<th><button class="sort-button" data-sort="${k}">${label} ${state.sort===k?(state.direction===1?"↑":"↓"):"↕"}</button></th>`).join("")}<th>DETALJER</th></tr></thead><tbody>${shown.length?shown.map(r=>`<tr>${cols.map(([key])=>`<td class="${key==="id"||key.endsWith("_id")?"number":""}">${cell(key,r[key])}</td>`).join("")}<td><button class="row-action" data-detail="${r.id}" data-kind="${state.table}">Åbn →</button></td></tr>`).join(""):`<tr><td colspan="${cols.length+1}" class="empty">Ingen matchende rækker.</td></tr>`}</tbody></table>`;
 $("databaseCount").textContent=`${rows.length?state.page*12+1:0}–${Math.min(rows.length,(state.page+1)*12)} af ${rows.length} rækker`;$("previousPage").disabled=state.page===0;$("nextPage").disabled=state.page===pages-1;
}
$("databaseTabs").addEventListener("click",e=>{const b=e.target.closest("[data-table]");if(!b)return;state.table=b.dataset.table;state.sort="id";state.page=0;$("databaseTabs").querySelectorAll("button").forEach(el=>el.classList.toggle("selected",el===b));renderDatabase();});
$("databaseSearch").addEventListener("input",e=>{state.search=e.target.value.toLocaleLowerCase("da");state.page=0;renderDatabase();});
$("databaseTable").addEventListener("click",e=>{const b=e.target.closest("[data-sort]");if(!b)return;if(state.sort===b.dataset.sort)state.direction*=-1;else{state.sort=b.dataset.sort;state.direction=1;}renderDatabase();});
$("previousPage").addEventListener("click",()=>{state.page--;renderDatabase();});$("nextPage").addEventListener("click",()=>{state.page++;renderDatabase();});
function details(kind,id){const row=state.data[kind].find(r=>r.id===id);if(!row)return;$("dialogTitle").textContent=`${kind} · #${id}`;$("dialogContent").textContent=JSON.stringify(row,null,2);$("dialogFlow").hidden=false;$("dialogFlow").dataset.reading=kind==="readings"?id:row.reading_id;$("detailsDialog").showModal();}
$("closeDialog").addEventListener("click",()=>$("detailsDialog").close());$("dialogFlow").addEventListener("click",()=>{$("detailsDialog").close();openFlow(Number($("dialogFlow").dataset.reading));});
function openFlow(id){state.flowId=id;navigate("flow");}
const eventExplanation={SensorValueReceived:"Målingen er registreret i systemet.",AnomalyDetected:"Vindhastigheden overskred den gældende tærskel.",AlarmCreated:"Der blev oprettet en alarm til driftspersonalet.",AlarmAcknowledged:"Driftspersonalet har markeret alarmen som set."};
function renderFlow(){const rows=latestFirst(state.data.readings);if(!rows.some(r=>r.id===state.flowId))state.flowId=rows[0]?.id??null;$("flowReading").innerHTML=rows.map(r=>`<option value="${r.id}">#${r.id} · ${esc(r.device_id)} · ${num(r.wind_speed)} m/s</option>`).join("");$("flowReading").value=state.flowId;
 const r=rows.find(r=>r.id===state.flowId);if(!r){$("flowDetails").innerHTML='<div class="empty">Send en måling for at se et forløb.</div>';return;}
 const events=state.data.events.filter(e=>e.reading_id===r.id).sort((a,b)=>a.id-b.id);const alarms=state.data.alarms.filter(a=>a.reading_id===r.id);
 $("flowDetails").innerHTML=`<div class="flow-reading"><div><span class="eyebrow">MÅLING #${r.id}</span><strong class="${r.anomaly_detected?"wind-high":"teal"}">${num(r.wind_speed)} <small>m/s</small></strong></div><div><b>${esc(r.device_id)}</b><p>${date(r.created_at)}</p></div><span class="badge ${r.anomaly_detected?"bad":"good"}">${r.anomaly_detected?"Anomali registreret":"Normal måling"}</span></div><div class="timeline">${events.length?events.map(e=>`<div class="timeline-item"><span class="timeline-dot"></span><h3>${esc(e.event_type)}</h3><p>${esc(eventExplanation[e.event_type]||"Gemt domænehændelse.")}</p><small>Event #${e.id} · reading_id ${e.reading_id} · ${date(e.created_at)}</small><pre>${esc(JSON.stringify(e.payload,null,2))}</pre></div>`).join(""):'<div class="empty">Ingen events gemt for denne måling.</div>'}</div>${alarms.map(a=>`<div class="linked-alarm"><span>Alarm #${a.id} · ${esc(a.message)} ${badge(a.status)}</span>${a.status==="active"?`<button class="row-action ack" data-ack="${a.id}">Kvittér alarm</button>`:`<span class="small">Kvitteret ${date(a.acknowledged_at)}</span>`}</div>`).join("")}${!alarms.length?'<div class="notice">Ingen alarm er knyttet til denne måling.</div>':""}`;
}
$("flowReading").addEventListener("change",e=>{state.flowId=Number(e.target.value);renderFlow();});
$("readingForm").addEventListener("submit",async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button[type="submit"]');button.disabled=true;$("submitError").textContent="";$("submitResult").innerHTML="";$("httpStatus").textContent="Sender…";$("httpStatus").className="badge neutral";
 try{const data={device_id:$("deviceId").value.trim(),wind_speed:Number($("windSpeed").value)};const {response,body}=await request("readings","POST",data);$("httpStatus").textContent=`HTTP ${response.status}`;$("httpStatus").className="badge "+(response.ok?"good":"bad");$("apiResponse").textContent=JSON.stringify(body,null,2);if(!response.ok)throw new Error(typeof body.detail==="string"?body.detail:"Input blev afvist. Kontrollér felterne.");
 await refresh(true);$("submitResult").innerHTML=`<span class="badge ${body.anomaly_detected?"bad":"good"}">${body.anomaly_detected?"Anomali og alarm oprettet":"Normal måling gemt"}</span><p>Måling #${body.id} er gemt gennem API'et.</p><button class="btn subtle" data-flow="${body.id}">Se målingens events og alarm →</button>`;toast("Målingen er gemt.");}
 catch(error){$("submitError").textContent=error.message;}finally{button.disabled=false;}
});
(async()=>{try{const response=await fetch("/dashboard/session",{credentials:"same-origin",cache:"no-store"});if(response.ok){const body=await response.json();state.csrf=body.csrf_token;enter();}}catch(e){/* Login vises som udgangspunkt. */}})();

let resizeTimer; window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(state.data)renderView();},250);});
