/* Börsenpreise v0.0.2 — no external frontend dependencies. */
class BoersenpreisePanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    this.day = new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
    this.request = 0;
  }
  set hass(value) { this._hass = value; if (!this.started && this.isConnected) this.start(); }
  connectedCallback() { if (this._hass && !this.started) this.start(); }
  disconnectedCallback() { clearInterval(this.timer); this.started=false; this.request++; }
  start() { this.started=true; this.load(); this.timer=setInterval(()=>this.load(),30000); }
  async load() {
    const request=++this.request;
    try {
      const result=await this._hass.callWS({type:'boersenpreise/day',day:this.day});
      if (request!==this.request || !this.isConnected) return;
      this.data=result; this.failure=false; this.render();
    } catch (_) { if(request===this.request) {this.failure=true; this.render();} }
  }
  move(offset) {
    const date=new Date(this.day+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+offset);
    this.day=date.toISOString().slice(0,10); this.load();
  }
  render() {
    const d=this.data, s=d?.settings;
    const rows=d?.day===this.day ? d.prices : [];
    const money=x=>x.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2});
    const time=ts=>new Intl.DateTimeFormat('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(new Date(ts*1000));
    const prices=rows.map(r=>r.eur_mwh/10);
    let chart='';
    if(rows.length) {
      const lo=Math.min(0,...prices), hi=Math.max(1,...prices), range=hi-lo;
      const y=v=>30+(hi-v)/range*240, baseline=y(0), width=960/d.expected;
      const bars=rows.map((r,i)=>{
        const p=r.eur_mwh/10;
        const color=p<=s.green_limit?s.green_color:p<=s.yellow_limit?s.yellow_color:s.high_color;
        return `<rect tabindex="0" x="${60+(r.ts-d.start_ts)/900*width+1}" y="${Math.min(y(p),baseline)}" width="${Math.max(1,width-2)}" height="${Math.max(1,Math.abs(y(p)-baseline))}" fill="${color}"><title>${time(r.ts)} – ${time(r.ts+900)}: ${money(p)} ct/kWh</title></rect>`;
      }).join('');
      const ticks=Array.from({length:5},(_,i)=>{const v=hi-range*i/4;return `<text x="50" y="${y(v)+4}" text-anchor="end">${money(v)}</text><line class="grid" x1="60" x2="1020" y1="${y(v)}" y2="${y(v)}"/>`;}).join('');
      const labels=Array.from({length:Math.ceil(d.expected/8)},(_,i)=>`<text x="${60+i*8*width}" y="300">${time(d.start_ts+i*7200).split(' ')[0]}</text>`).join('');
      chart=`<div class="scroll"><svg viewBox="0 0 1050 320" role="img" aria-label="Viertelstundenpreise in Cent pro Kilowattstunde">${ticks}<line class="zero" x1="60" x2="1020" y1="${baseline}" y2="${baseline}"/>${bars}${labels}</svg></div>`;
    }
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color,#172033);background:var(--primary-background-color,#f4f6fa);min-height:100vh;font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif)}
      *{box-sizing:border-box}header{display:flex;align-items:center;gap:16px;padding:20px 28px;background:var(--card-background-color,white);border-bottom:1px solid var(--divider-color,#ddd)}h1{font-size:23px;margin:0}header small{margin-left:auto;color:var(--secondary-text-color,#667)}main{max-width:1250px;margin:auto;padding:28px}.intro{color:var(--secondary-text-color,#667);line-height:1.6}.nav{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:24px 0}button,input{font:inherit;padding:11px 16px;border:1px solid var(--divider-color,#ccd);border-radius:10px;background:var(--card-background-color,white);color:inherit}button{cursor:pointer}button:hover{border-color:#22a6b3}button:disabled{opacity:.4;cursor:default}.card{padding:24px;background:var(--card-background-color,white);border:1px solid var(--divider-color,#e3e7ef);border-radius:18px;margin-bottom:18px}.stats{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:24px}.stat{flex:1;min-width:150px}.stat small{display:block;color:var(--secondary-text-color,#667);margin-bottom:8px}.stat strong{font-size:24px}.scroll{overflow-x:auto}svg{width:100%;min-width:850px;display:block}svg text{fill:var(--secondary-text-color,#667);font-size:12px}.grid{stroke:var(--divider-color,#ddd);stroke-dasharray:3 4}.zero{stroke:var(--primary-text-color,#172033);stroke-width:1.5}rect:focus,rect:hover{stroke:var(--primary-text-color,#172033);stroke-width:2;outline:none}.legend{display:flex;flex-wrap:wrap;gap:20px;font-size:14px}.dot{width:12px;height:12px;display:inline-block;border-radius:3px;margin-right:6px}.empty{padding:60px 15px;text-align:center;color:var(--secondary-text-color,#667)}.notice{line-height:1.7;font-size:14px}details{margin-top:20px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid var(--divider-color,#ddd)}.warning{color:var(--error-color,#b45309)}@media(max-width:600px){main{padding:16px}.card{padding:16px}header{padding:16px}header small{display:none}}
      </style><header><ha-menu-button></ha-menu-button><h1>Börsenpreise</h1><small>ENTSO-E · DE-LU · v0.0.2</small></header><main>
      <p class="intro">Day-Ahead-Preise für Deutschland / Luxemburg · 15-Minuten-Intervalle<br>Reiner Börsenpreis ohne Tarifaufschläge, Netzentgelte und Steuern.</p>
      <div class="nav"><button id="prev" aria-label="Vorheriger Tag">← Zurück</button><input id="day" aria-label="Tag auswählen" type="date" min="${s?.import_start||'2025-10-01'}" value="${this.day}"><button id="next">Weiter →</button><button id="today">Heute</button><button id="tomorrow">Morgen</button></div>
      ${this.failure?'<p class="warning">Verbindung zu Home Assistant fehlgeschlagen. Automatische Wiederholung folgt.</p>':''}
      <section class="card">${rows.length?`<div class="stats"><div class="stat"><small>Tiefster Preis</small><strong>${money(Math.min(...prices))} ct/kWh</strong></div><div class="stat"><small>Tagesmittel${rows.length<d.expected?' (unvollständig)':''}</small><strong>${money(prices.reduce((a,b)=>a+b,0)/prices.length)} ct/kWh</strong></div><div class="stat"><small>Höchster Preis</small><strong>${money(Math.max(...prices))} ct/kWh</strong></div></div>${chart}`:'<div class="empty">Noch keine Preise für diesen Tag vorhanden.<br>Historische Tage werden im Hintergrund geladen. Künftige Preise erscheinen nach ihrer Veröffentlichung.</div>'}
      ${s?`<div class="legend"><span><i class="dot" style="background:${s.green_color}"></i>bis ${money(s.green_limit)} ct/kWh</span><span><i class="dot" style="background:${s.yellow_color}"></i>über ${money(s.green_limit)} bis ${money(s.yellow_limit)} ct/kWh</span><span><i class="dot" style="background:${s.high_color}"></i>über ${money(s.yellow_limit)} ct/kWh</span></div>`:''}
      ${rows.length?`<details><summary>Alle ${rows.length} Viertelstunden anzeigen</summary><table><thead><tr><th>Zeitraum (Europe/Berlin)</th><th>ct/kWh</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${time(r.ts)} – ${time(r.ts+900)}</td><td>${money(r.eur_mwh/10)}</td></tr>`).join('')}</tbody></table></details>`:''}</section>
      <div class="card notice">Historischer Import: ${d?.complete??0} / ${d?.total??0} Tage vollständig.<br>${d?.influx_enabled?`InfluxDB 2 aktiv · ${d.influx_pending} Tage zur Übertragung ausstehend.`:'InfluxDB 2 ist deaktiviert. Preise werden lokal gespeichert.'}<br>Farben, Preisgrenzen und Verbindungen: Einstellungen → Geräte & Dienste → Börsenpreise → Konfigurieren.
      ${d?.error?'<p class="warning">ENTSO-E nicht erreichbar oder Zugang abgelehnt. Erneuter Versuch folgt.</p>':''}${d?.influx_error?'<p class="warning">InfluxDB-Übertragung fehlgeschlagen. Lokale Preise sind erhalten; erneuter Versuch folgt.</p>':''}</div></main>`;
    this.shadowRoot.querySelector('#prev').disabled=this.day<=(s?.import_start||'2025-10-01');
    this.shadowRoot.querySelector('#prev').onclick=()=>this.move(-1);
    this.shadowRoot.querySelector('#next').onclick=()=>this.move(1);
    this.shadowRoot.querySelector('#day').onchange=e=>{if(e.target.value && e.target.validity.valid){this.day=e.target.value;this.load();}};
    const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin'}).format(new Date());
    this.shadowRoot.querySelector('#today').onclick=()=>{this.day=today();this.load();};
    this.shadowRoot.querySelector('#tomorrow').onclick=()=>{this.day=today();this.move(1);};
    const menu=this.shadowRoot.querySelector('ha-menu-button'); if(menu) menu.hass=this._hass;
  }
}
if(!customElements.get('boersenpreise-panel')) customElements.define('boersenpreise-panel',BoersenpreisePanel);
