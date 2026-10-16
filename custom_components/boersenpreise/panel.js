/* Börsenpreise v0.0.5 — no external frontend dependencies. */
function priceColor(price, levels, fallback, lower) {
  if (lower && price < lower.limit) return lower.color;
  return levels.find(level => price <= level.limit)?.color || fallback;
}
function roundedBar(x, top, width, height, negative) {
  const bottom = top + height, right = x + width;
  const radius = Math.min(3.5, width / 2, height);
  return negative
    ? `M ${x} ${top} H ${right} V ${bottom-radius} Q ${right} ${bottom} ${right-radius} ${bottom} H ${x+radius} Q ${x} ${bottom} ${x} ${bottom-radius} Z`
    : `M ${x} ${bottom} V ${top+radius} Q ${x} ${top} ${x+radius} ${top} H ${right-radius} Q ${right} ${top} ${right} ${top+radius} V ${bottom} Z`;
}
class BoersenpreisePanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    this.day = new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
    this.request = 0;
  }
  set hass(value) { this._hass = value; if (!this.started && this.isConnected) this.start(); }
  connectedCallback() { if (this._hass && !this.started) this.start(); }
  disconnectedCallback() { clearInterval(this.timer); this.started=false; this.request++; }
  start() { this.started=true; this.load().then(()=>{if(new URL(window.location.href).searchParams.get('settings')==='1')this.openSettings();}); this.timer=setInterval(()=>this.load(),30000); }
  async openSettings() {
    if(this.editorOpen || !this._hass.user?.is_admin)return;
    this.editorOpen=true;
    try {
      const settings=await this._hass.callWS({type:'boersenpreise/colors'});
      if(!this.isConnected){this.editorOpen=false;return;}
      const editor=document.createElement('boersenpreise-color-editor');
      editor.settings=settings;editor.hass=this._hass;
      const close=()=>{editor.remove();this.editorOpen=false;const url=new URL(window.location.href);url.searchParams.delete('settings');window.history.replaceState(null,'',url);this.load();};
      editor.oncancel=close;editor.onsaved=close;this.shadowRoot.append(editor);
    }catch(_){this.editorOpen=false;this.failure=true;this.render();}
  }
  async load() {
    if(this.editorOpen)return;
    const request=++this.request;
    try {
      const result=await this._hass.callWS({type:'boersenpreise/day',day:this.day});
      if (request!==this.request || !this.isConnected || this.editorOpen) return;
      this.data=result; this.failure=false; this.render();
    } catch (_) { if(request===this.request && !this.editorOpen) {this.failure=true; this.render();} }
  }
  move(offset) {
    const date=new Date(this.day+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+offset);
    this.day=date.toISOString().slice(0,10); this.load();
  }
  render() {
    const d=this.data, s=d?.settings;
    const rows=d?.day===this.day ? d.prices : [];
    const levels=s?.price_levels || (s ? [{limit:s.green_limit,color:s.green_color},{limit:s.yellow_limit,color:s.yellow_color}] : []);
    const lower=s && Number.isFinite(s.low_limit) ? {limit:s.low_limit,color:s.low_color} : null;
    const money=x=>x.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2});
    const time=ts=>new Intl.DateTimeFormat('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(new Date(ts*1000));
    const prices=rows.map(r=>r.eur_mwh/10);
    let chart='';
    if(rows.length) {
      const lo=Math.min(0,...prices), hi=Math.max(1,...prices), range=hi-lo;
      const y=v=>30+(hi-v)/range*240, baseline=y(0), width=960/d.expected;
      const bars=rows.map((r,i)=>{
        const p=r.eur_mwh/10;
        const color=priceColor(p,levels,s.high_color,lower);
        const shape=roundedBar(60+(r.ts-d.start_ts)/900*width+1,Math.min(y(p),baseline),Math.max(1,width-2),Math.max(1,Math.abs(y(p)-baseline)),p<0);
        return `<path class="bar" tabindex="0" d="${shape}" fill="${color}"><title>${time(r.ts)} – ${time(r.ts+900)}: ${money(p)} ct/kWh</title></path>`;
      }).join('');
      const ticks=Array.from({length:5},(_,i)=>{const v=hi-range*i/4;return `<text x="50" y="${y(v)+4}" text-anchor="end">${money(v)}</text><line class="grid" x1="60" x2="1020" y1="${y(v)}" y2="${y(v)}"/>`;}).join('');
      const labels=Array.from({length:Math.ceil(d.expected/8)},(_,i)=>`<text x="${60+i*8*width}" y="300">${time(d.start_ts+i*7200).split(' ')[0]}</text>`).join('');
      chart=`<div class="scroll"><svg viewBox="0 0 1050 320" role="img" aria-label="Viertelstundenpreise in Cent pro Kilowattstunde">${ticks}<line class="zero" x1="60" x2="1020" y1="${baseline}" y2="${baseline}"/>${bars}${labels}</svg></div>`;
    }
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color,#172033);background:var(--primary-background-color,#f4f6fa);min-height:100vh;font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif)}
      *{box-sizing:border-box}header{display:flex;align-items:center;gap:16px;padding:20px 28px;background:var(--card-background-color,white);border-bottom:1px solid var(--divider-color,#ddd)}h1{font-size:23px;margin:0}header small{margin-left:auto;color:var(--secondary-text-color,#667)}main{max-width:1250px;margin:auto;padding:28px}.intro{color:var(--secondary-text-color,#667);line-height:1.6}.nav{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:24px 0}button,input{font:inherit;padding:11px 16px;border:1px solid var(--divider-color,#ccd);border-radius:10px;background:var(--card-background-color,white);color:inherit}button{cursor:pointer}button:hover{border-color:#22a6b3}button:disabled{opacity:.4;cursor:default}.card{padding:24px;background:var(--card-background-color,white);border:1px solid var(--divider-color,#e3e7ef);border-radius:18px;margin-bottom:18px}.stats{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:24px}.stat{flex:1;min-width:150px}.stat small{display:block;color:var(--secondary-text-color,#667);margin-bottom:8px}.stat strong{font-size:24px}.scroll{overflow-x:auto}svg{width:100%;min-width:850px;display:block}svg text{fill:var(--secondary-text-color,#667);font-size:12px}.grid{stroke:var(--divider-color,#ddd);stroke-dasharray:3 4}.zero{stroke:var(--primary-text-color,#172033);stroke-width:1.5}.bar:focus,.bar:hover{stroke:var(--primary-text-color,#172033);stroke-width:2;outline:none}.legend{display:flex;flex-wrap:wrap;gap:20px;font-size:14px}.dot{width:12px;height:12px;display:inline-block;border-radius:3px;margin-right:6px}.empty{padding:60px 15px;text-align:center;color:var(--secondary-text-color,#667)}.notice{line-height:1.6;font-size:12px;color:var(--secondary-text-color,#667)}.notice p{margin:0 0 10px}.nav{margin-top:0}details{margin-top:20px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid var(--divider-color,#ddd)}.warning{color:var(--error-color,#b45309)}@media(max-width:600px){header{gap:8px}h1{font-size:20px}#settings{font-size:13px;padding:8px 10px}main{padding:16px}.card{padding:16px}header{padding:16px}header small{display:none}}
      </style><header><ha-menu-button></ha-menu-button><h1>Börsenpreise</h1>${this._hass?.user?.is_admin?'<button id="settings" aria-label="Farbeinstellungen öffnen">Einstellungen</button>':''}<small>ENTSO-E · DE-LU · v0.0.5</small></header><main>
      <div class="nav"><button id="prev" aria-label="Vorheriger Tag">← Zurück</button><input id="day" aria-label="Tag auswählen" type="date" min="${s?.import_start||'2025-10-01'}" value="${this.day}"><button id="next">Weiter →</button><button id="today">Heute</button><button id="tomorrow">Morgen</button></div>
      ${this.failure?'<p class="warning">Verbindung zu Home Assistant fehlgeschlagen. Automatische Wiederholung folgt.</p>':''}
      <section class="card">${rows.length?`<div class="stats"><div class="stat"><small>Tiefster Preis</small><strong>${money(Math.min(...prices))} ct/kWh</strong></div><div class="stat"><small>Tagesmittel${rows.length<d.expected?' (unvollständig)':''}</small><strong>${money(prices.reduce((a,b)=>a+b,0)/prices.length)} ct/kWh</strong></div><div class="stat"><small>Höchster Preis</small><strong>${money(Math.max(...prices))} ct/kWh</strong></div></div>${chart}`:'<div class="empty">Noch keine Preise für diesen Tag vorhanden.<br>Historische Tage werden im Hintergrund geladen. Künftige Preise erscheinen nach ihrer Veröffentlichung.</div>'}
      ${s?`<div class="legend">${lower?`<span><i class="dot" style="background:${lower.color}"></i>unter ${money(lower.limit)} ct/kWh</span>`:''}${levels.map((level,i)=>`<span><i class="dot" style="background:${level.color}"></i>${i?`über ${money(levels[i-1].limit)} bis`:lower?(lower.limit===level.limit?'bei':`ab ${money(lower.limit)} bis`):'bis'} ${money(level.limit)} ct/kWh</span>`).join('')}<span><i class="dot" style="background:${s.high_color}"></i>${levels.length?`über ${money(levels[levels.length-1].limit)} ct/kWh`:lower?`ab ${money(lower.limit)} ct/kWh`:'Alle Preise'}</span></div>`:''}
      ${rows.length?`<details><summary>Alle ${rows.length} Viertelstunden anzeigen</summary><table><thead><tr><th>Zeitraum (Europe/Berlin)</th><th>ct/kWh</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${time(r.ts)} – ${time(r.ts+900)}</td><td>${money(r.eur_mwh/10)}</td></tr>`).join('')}</tbody></table></details>`:''}</section>
      <div class="card notice"><p>Day-Ahead-Preise für Deutschland / Luxemburg · 15-Minuten-Intervalle<br>Reiner Börsenpreis ohne Tarifaufschläge, Netzentgelte und Steuern.</p>Historischer Import: ${d?.complete??0} / ${d?.total??0} Tage vollständig.<br>${d?.influx_enabled?`InfluxDB 2 aktiv · ${d.influx_pending} Tage zur Übertragung ausstehend.`:'InfluxDB 2 ist deaktiviert. Preise werden lokal gespeichert.'}<br>Farben und Preis Zohnen: Einstellungen oben · Verbindungen: Geräte & Dienste → Börsenpreise → Konfigurieren.
      ${d?.error?'<p class="warning">ENTSO-E nicht erreichbar oder Zugang abgelehnt. Erneuter Versuch folgt.</p>':''}${d?.influx_error?'<p class="warning">InfluxDB-Übertragung fehlgeschlagen. Lokale Preise sind erhalten; erneuter Versuch folgt.</p>':''}</div></main>`;
    this.shadowRoot.querySelector('#prev').disabled=this.day<=(s?.import_start||'2025-10-01');
    this.shadowRoot.querySelector('#prev').onclick=()=>this.move(-1);
    this.shadowRoot.querySelector('#next').onclick=()=>this.move(1);
    this.shadowRoot.querySelector('#day').onchange=e=>{if(e.target.value && e.target.validity.valid){this.day=e.target.value;this.load();}};
    const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
    this.shadowRoot.querySelector('#today').onclick=()=>{this.day=today();this.load();};
    this.shadowRoot.querySelector('#tomorrow').onclick=()=>{this.day=today();this.move(1);};
    const settingsButton=this.shadowRoot.querySelector('#settings');if(settingsButton)settingsButton.onclick=()=>this.openSettings();
    const menu=this.shadowRoot.querySelector('ha-menu-button'); if(menu) menu.hass=this._hass;
  }
}
if(!customElements.get('boersenpreise-panel')) customElements.define('boersenpreise-panel',BoersenpreisePanel);

function sortedPriceZones(levels) {
  const zones=levels.map(level=>({limit:Number(level.limit),color:level.color}));
  if(!zones.length || zones.some((level,index)=>!Number.isFinite(level.limit) || !/^#[0-9a-f]{6}$/i.test(level.color) || zones.some((other,j)=>j!==index && other.limit===level.limit))) throw new Error('invalid_settings');
  return zones.sort((a,b)=>b.limit-a.limit);
}
class BoersenpreiseColorEditor extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});}
  connectedCallback(){this.model=structuredClone(this.settings);this.model.price_levels.sort((a,b)=>b.limit-a.limit);this.render();}
  collect(){return {high_color:this.shadowRoot.querySelector('#high').value,low_color:this.shadowRoot.querySelector('#low').value,price_levels:Array.from(this.shadowRoot.querySelectorAll('.zone')).map(row=>({limit:row.querySelector('[data-limit]').valueAsNumber,color:row.querySelector('[data-color]').value}))};}
  render(){
    const model=this.model;
    this.shadowRoot.innerHTML=`<style>
      :host{font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif);color:var(--primary-text-color,#172033)}*{box-sizing:border-box}dialog{color:inherit;width:min(620px,calc(100vw - 28px));max-height:calc(100dvh - 32px);padding:0;border:1px solid var(--divider-color,#dde3eb);border-radius:18px;background:var(--card-background-color,white);box-shadow:0 20px 70px #0003}dialog::backdrop{background:#0006}form{margin:0}header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 24px}header{border-bottom:1px solid var(--divider-color,#e3e7ef)}h2{font-size:21px;margin:0}h3{font-size:17px;margin:0 0 14px}.body{padding:22px 24px;max-height:calc(100dvh - 210px);overflow:auto}.outside{display:flex;align-items:center;justify-content:space-between;gap:16px;font-size:15px;line-height:1.4}.zones{margin:24px 0;padding:20px 0;border-top:1px solid var(--divider-color,#e3e7ef);border-bottom:1px solid var(--divider-color,#e3e7ef)}.zone{display:flex;align-items:center;gap:12px;padding:10px 0}.price{display:flex;align-items:center;gap:8px;flex:1;min-width:0}.price input{width:100%;max-width:170px;min-width:70px;border:1px solid var(--divider-color,#ccd);border-radius:8px;padding:10px;font:inherit;color:inherit;background:var(--primary-background-color,#f5f7fa)}.unit{font-size:13px;white-space:nowrap;color:var(--secondary-text-color,#667)}input[type=color]{display:block;width:76px;min-width:76px;height:36px;padding:3px;border:1px solid var(--divider-color,#ccd);border-radius:8px;background:var(--card-background-color,white);cursor:pointer}input[type=color]::-webkit-color-swatch-wrapper{padding:0}input[type=color]::-webkit-color-swatch{border:0;border-radius:4px}input[type=color]::-moz-color-swatch{border:0;border-radius:4px}button,a{font:inherit;color:inherit}button{border:1px solid var(--divider-color,#ccd);border-radius:9px;padding:10px 14px;cursor:pointer;background:var(--card-background-color,white)}button:hover{border-color:var(--primary-color,#0099b0)}button:disabled{opacity:.5;cursor:wait}.close,.remove{border:0;padding:8px;font-size:22px;line-height:1}.remove{color:var(--secondary-text-color,#667)}.add{margin-top:12px;color:var(--primary-color,#0099b0)}.hint{font-size:12px;line-height:1.6;color:var(--secondary-text-color,#667);margin:12px 0 0}.message{font-size:13px;color:var(--error-color,#b42318);margin:12px 0 0;min-height:16px}footer{justify-content:flex-end;border-top:1px solid var(--divider-color,#e3e7ef)}.save{background:var(--primary-color,#0099b0);border-color:transparent;color:var(--text-primary-color,white)}@media(max-width:450px){header,footer{padding:16px}.body{padding:18px 16px}.zone{gap:8px}.outside{font-size:14px}.unit{font-size:12px}}
      </style><dialog aria-labelledby="editor-title"><form><header><h2 id="editor-title">Farben und Preis Zohnen</h2><button class="close" id="close" type="button" aria-label="Schließen">×</button></header><div class="body">
      <label class="outside"><span>Oberhalb des letzten Preises</span><input id="high" type="color" aria-label="Oberhalb des letzten Preises" value="${model.high_color}"></label>
      <section class="zones"><h3>Preis Zohnen</h3><div id="rows">${model.price_levels.map((level,index)=>`<div class="zone"><label class="price"><input data-limit type="number" step="any" required aria-label="Preiszone ${index+1} in ct/kWh" value="${Number(level.limit)}"><span class="unit">ct/kWh</span></label><input data-color type="color" aria-label="Farbe Preiszone ${index+1}" value="${level.color}"><button type="button" class="remove" data-remove="${index}" aria-label="Preiszone ${index+1} entfernen">×</button></div>`).join('')}</div><button class="add" id="add" type="button">+ Hinzufügen</button><p class="hint">Höchster Preis oben, niedrigster unten. Beim Speichern werden die Preis Zohnen automatisch sortiert.</p></section>
      <label class="outside"><span>Unterhalb des niedrigsten Preises</span><input id="low" type="color" aria-label="Unterhalb des niedrigsten Preises" value="${model.low_color}"></label>
      <p class="hint">Die Unterhalb-Farbe gilt unter dem niedrigsten Preisziel, die Oberhalb-Farbe über dem höchsten. Zwischen zwei Preiszielen gilt die Farbe des höheren Preisziels.</p><p class="message" id="message" role="status" aria-live="polite"></p></div><footer><button id="cancel" type="button">Abbrechen</button><button class="save" type="submit">Speichern</button></footer></form></dialog>`;
    const root=this.shadowRoot,dialog=root.querySelector('dialog');
    dialog.addEventListener('cancel',event=>{event.preventDefault();if(!this.busy)this.oncancel?.();});
    for(const id of ['close','cancel'])root.querySelector('#'+id).onclick=()=>{if(!this.busy)this.oncancel?.();};
    root.querySelector('#add').onclick=()=>{if(!root.querySelector('form').reportValidity())return;this.model=this.collect();const highest=Math.max(0,...this.model.price_levels.map(level=>level.limit));this.model.price_levels.push({limit:highest+5,color:'#22c55e'});this.model.price_levels.sort((a,b)=>b.limit-a.limit);this.render();};
    root.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{this.model=this.collect();this.model.price_levels.splice(Number(button.dataset.remove),1);this.render();});
    root.querySelectorAll('[data-limit]').forEach(input=>input.onchange=()=>{if(!root.querySelector('form').checkValidity())return;const draft=this.collect();try{draft.price_levels=sortedPriceZones(draft.price_levels);this.model=draft;root.querySelector('#message').textContent='';}catch(_){root.querySelector('#message').textContent='Jede Preiszone benötigt einen eigenen Preis.';}});
    root.querySelector('form').onsubmit=event=>{event.preventDefault();this.save();};
    dialog.showModal();
  }
  async save(){
    if(this.busy || !this.shadowRoot.querySelector('form').reportValidity())return;
    const message=this.shadowRoot.querySelector('#message');
    let draft;
    try{draft=this.collect();draft.price_levels=sortedPriceZones(draft.price_levels);}catch(_){message.textContent='Bitte mindestens eine Preiszone mit eindeutigem Preis hinzufügen.';return;}
    this.busy=true;this.shadowRoot.querySelectorAll('input,button').forEach(element=>element.disabled=true);message.textContent='';
    try{await this.hass.callWS({type:'boersenpreise/colors',settings:draft});this.onsaved?.();}
    catch(_){message.textContent='Speichern fehlgeschlagen. Verbindung, Preise und Administratorrechte prüfen.';}
    finally{this.busy=false;this.shadowRoot.querySelectorAll('input,button').forEach(element=>element.disabled=false);}
  }
}
if(!customElements.get('boersenpreise-color-editor'))customElements.define('boersenpreise-color-editor',BoersenpreiseColorEditor);
