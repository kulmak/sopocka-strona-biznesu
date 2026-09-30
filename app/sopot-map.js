/* <sopot-map> — Sopot postcode intensity map (Leaflet + d3), driven by attributes:
   pkd, day (anchor date, YYYY-MM-DD), t (0–72: hours across day-before / day / day-after), metric (count|zl), focus (postcode-hierarchy key), smoothing.
   Emits bubbling `sopot-focus` {detail:{key}} when a zone is clicked. Needs window.SopotModel (sopot-model.js), Leaflet and d3 loaded first. */
(function(){
const TPL=`<style>
sopot-map{display:block;position:relative;height:100%;min-height:240px}
sopot-map[mini]{min-height:0}
sopot-map[mini] .sm-zone{pointer-events:none}
sopot-map[mini] .sm-overlay{font-size:10px;padding:8px}
sopot-map[mini] .sm-evpin{width:10px;height:10px;border-width:1px}
sopot-map[mini] .sm-evpin.sel{width:12px;height:12px}
sopot-map .sm-wrap{position:absolute;inset:0}
sopot-map .sm-map{position:absolute;inset:0;background:var(--color-bg)}
sopot-map .leaflet-container{background:var(--color-bg);font-family:var(--font-body)}
sopot-map .leaflet-popup-content-wrapper,sopot-map .leaflet-popup-tip{border-radius:0;box-shadow:var(--shadow-md)}
sopot-map .leaflet-bar a{border-radius:0!important}
sopot-map .leaflet-control-attribution{font-size:10px;opacity:.75}
sopot-map .sm-boundary{fill:none;stroke:var(--color-accent-900);stroke-width:1.2;pointer-events:none}
sopot-map .sm-sea{fill:var(--color-accent-100);stroke:none;pointer-events:none}
sopot-map .sm-land{fill:var(--color-neutral-200);stroke:none;pointer-events:none}
sopot-map .sm-evid{fill:var(--color-bg);fill-opacity:.55;pointer-events:none}
sopot-map .sm-sealabel{font:italic 13px var(--font-body);fill:var(--color-accent-700);letter-spacing:.2em;text-transform:uppercase;pointer-events:none}
sopot-map .sm-zone{cursor:default;stroke:none;fill:transparent}
sopot-map .sm-zone:hover{fill:rgba(255,255,255,.22)!important}
sopot-map .sm-zone.disp{stroke:var(--color-accent-900);stroke-width:.9;stroke-dasharray:3 2;stroke-opacity:.75}
sopot-map .sm-zlabel{font:600 11px var(--font-body);fill:var(--color-accent-900);pointer-events:none;text-anchor:middle;paint-order:stroke;stroke:var(--color-bg);stroke-width:3px}
sopot-map .sm-zlabel.grp{font-size:12px;letter-spacing:.04em}
sopot-map .sm-evpin{width:16px;height:16px;transform:rotate(45deg);background:var(--color-accent-900);border:2px solid var(--color-bg);box-shadow:0 0 0 1px var(--color-accent-900)}
sopot-map .sm-evpin.sel{width:20px;height:20px;box-shadow:0 0 0 2px var(--color-accent-900),0 0 0 6px rgba(89,128,166,.25)}
sopot-map .sm-overlay{position:absolute;inset:0;z-index:600;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;background:color-mix(in srgb,var(--color-bg) 78%,transparent);font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--color-accent-900)}
sopot-map .sm-lock{display:none;z-index:500;letter-spacing:0;text-transform:none}
sopot-map.locked .sm-lock{display:flex}
sopot-map[mini] .sm-wrap{pointer-events:none}
sopot-map .sm-venue{display:flex;align-items:center;gap:5px;white-space:nowrap}
sopot-map .sm-venue i{display:block;flex:none;width:14px;height:14px;background:var(--color-bg);border:2.5px solid var(--color-accent-900);box-sizing:border-box;box-shadow:0 0 0 2px var(--color-bg)}
sopot-map .sm-venue span{font:600 11px var(--font-body);color:var(--color-text);background:color-mix(in srgb,var(--color-bg) 88%,transparent);padding:1px 5px;border:1px solid var(--color-neutral-300)}
sopot-map[mini] .sm-venue i{width:9px;height:9px;border-width:2px;box-shadow:0 0 0 1px var(--color-bg)}
sopot-map[mini] .sm-venue span{display:none}
sopot-map[adding="true"] .leaflet-container,sopot-map[adding="true"] .sm-zone{cursor:crosshair!important}
sopot-map .sm-flabel{font:600 11px var(--font-body);paint-order:stroke;stroke:var(--color-bg);stroke-width:3px;pointer-events:none;text-anchor:middle}
sopot-map[mini] .leaflet-pane > svg path.leaflet-interactive{pointer-events:none!important;cursor:default}
sopot-map[mini] .sm-sealabel{display:none}
sopot-map[mini] .sm-overlay{font-size:10px;padding:8px;letter-spacing:.04em}
sopot-map[mini] .sm-lock > div > div:first-child{font-size:14px!important}
sopot-map[mini] .sm-lockwhy{display:none}
</style>
<div class="sm-wrap"><div class="sm-map"></div><div class="sm-overlay sm-loading">Ładowanie granic obszarów…</div>
<div class="sm-overlay sm-lock"><div style="max-width:420px;display:flex;flex-direction:column;gap:6px"><div style="font-family:var(--font-heading);font-size:26px;text-transform:uppercase">Mapa niedostępna</div><div class="sm-lockwhy" style="font-size:14px;opacity:.75"></div></div></div></div>`;
const KX=64.73,KY=111.2;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc=v=>String(v).replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
const seis=(d3,n)=>d3.interpolateTurbo(.06+.88*Math.max(0,Math.min(1,n)));

class SopotMap extends HTMLElement{
  static get observedAttributes(){return ['pkd','day','t','metric','focus','smoothing','event','hot','pad-right','pad-bottom','padright','padbottom','venues','fit','adding'];}
  get adding(){return this.getAttribute('adding')==='true';}
  get pkd(){return this.getAttribute('pkd')||'56.10.A';}
  get day(){return this.getAttribute('day')||'2026-06-20';}
  get t(){return +(this.getAttribute('t')||24);}
  get focusKey(){return this.getAttribute('focus')||'';}
  get smoothing(){return +(this.getAttribute('smoothing')||1);}
  get mini(){return this.hasAttribute('mini');}
  get metric(){const v=this.getAttribute('metric');return v==='zl'||v==='rel'?v:'count';}
  // fit padding that keeps the framed area clear of overlays laid over the map (top-right readout, bottom-left legend)
  _pads(){if(this.mini)return {tl:[6,6],br:[6,6]};const pr=+(this.getAttribute('pad-right')||this.getAttribute('padright')||0),pb=+(this.getAttribute('pad-bottom')||this.getAttribute('padbottom')||0),sz=this._map?this._map.getSize():{x:1000,y:600};
    // never reserve more than 40% of the width / 25% of the height for overlays, so narrow embeds still frame the area
    return {tl:[40,40],br:[Math.max(40,Math.min(pr+16,sz.x*.4)),Math.max(40,Math.min(pb+16,sz.y*.25))]};}
  // current calendar date and in-day fractional hour derived from the 72-hour window
  cur(){const M=window.SopotModel,t=this.t;return {k:M.addDays(this.day,Math.floor(t/24)-1),tt:t%24,H:Math.floor(t)%24};}
  connectedCallback(){if(this._init)return;this._init=true;this.innerHTML=TPL;this._boot();}
  disconnectedCallback(){if(this._ro)this._ro.disconnect();}
  attributeChangedCallback(n,o,v){if(!this._ready||o===v)return;
    if(n==='focus'){this._flyToFocus();this._draw();}else if(n==='fit'){if(!this.focusKey)this._flyToFocus();}else if(n==='venues'){this._drawVenues();}else if(n==='adding'){}else if(/^pad/.test(n)){this._flyToFocus(false);}else if(n==='hot'){this._drawHot();}else if(n==='t'){const c=this.cur();if(c.k!==this._lastK||c.H!==this._lastH)this._paint();else this._renderHeat();}else if(n==='smoothing'){this.HEAT=null;this._renderHeat();}else if(n==='metric'){this._renderHeat();}else this._paint();}
  async _boot(){
    const L=this.L=window.L,d3=this.d3=window.d3,el=this.querySelector('.sm-map');
    const mini=this.mini;
    const map=this._map=L.map(el,mini?{zoomControl:false,attributionControl:false,dragging:false,scrollWheelZoom:false,doubleClickZoom:false,touchZoom:false,boxZoom:false,keyboard:false,maxZoom:18.5,zoomSnap:.1}:{zoomControl:true,scrollWheelZoom:true,maxZoom:18.5,zoomSnap:.25,attributionControl:true}).setView([54.4425,18.5620],13);
    if(!mini)map.attributionControl.setPrefix(false).addAttribution('<span title="Granica miasta: GUGiK PRG; ląd: BDOT10k; obszary: model z adresów UM Sopot i wykazu Poczty Polskiej (nieoficjalne)">Granice: GUGiK · UM Sopot · Poczta Polska (model)</span>');
    const svg=this.svg=d3.select(map.getPanes().overlayPane).append('svg').style('position','absolute');
    const defs=svg.append('defs');const uid=this._uid='sm'+Math.random().toString(36).slice(2,7);
    this.cityClip=defs.append('clipPath').attr('id',uid+'city').append('path');
    this.focusClip=defs.append('clipPath').attr('id',uid+'focus').append('path');
    const pat=defs.append('pattern').attr('id',uid+'hatch').attr('width',6).attr('height',6).attr('patternUnits','userSpaceOnUse').attr('patternTransform','rotate(45)');
    pat.append('rect').attr('width',6).attr('height',6).attr('fill',css('--color-neutral-100'));pat.append('line').attr('x1',0).attr('y1',0).attr('x2',0).attr('y2',6).attr('stroke',css('--color-neutral-400'));
    const gRoot=this.gRoot=svg.append('g').attr('class','leaflet-zoom-hide');
    this.gSea=gRoot.append('path').attr('class','sm-sea');this.gSeaLabel=gRoot.append('text').attr('class','sm-sealabel');this.gLand=gRoot.append('path').attr('class','sm-land');
    const gCity=gRoot.append('g').attr('clip-path',`url(#${uid}city)`);
    const gHeatWrap=gCity.append('g').attr('clip-path',`url(#${uid}focus)`);
    this.heatImg=gHeatWrap.append('image').attr('preserveAspectRatio','none').style('image-rendering','auto');
    this.gWash=gHeatWrap.append('path').attr('class','sm-evid');
    this.gContours=gHeatWrap.append('g').attr('fill','none').style('pointer-events','none');
    this.gFlow=gHeatWrap.append('g').attr('fill','none').attr('stroke-linecap','round').attr('stroke-linejoin','round').style('pointer-events','none');
    this.gCells=gCity.append('g');
    this.gEdges=gCity.append('path').attr('fill','none').attr('stroke','#fff').style('pointer-events','none');
    this.gGroupEdges=gCity.append('path').attr('fill','none').attr('stroke','#fff').attr('stroke-opacity',.9).attr('stroke-width',1.1).style('pointer-events','none');
    this.gFocusLine=gCity.append('path').attr('fill','none').attr('stroke',css('--color-text')).attr('stroke-width',2).style('pointer-events','none');
    this.gHot=gCity.append('path').attr('fill','none').attr('stroke',css('--color-accent-900')).attr('stroke-width',2.2).attr('stroke-linejoin','round').style('pointer-events','none');
    this.gOutline=gRoot.append('path').attr('class','sm-boundary');
    this.gLabels=gRoot.append('g');
    this.gVenArea=gRoot.append('g').attr('fill','none').attr('stroke',css('--color-accent-700')).attr('stroke-width',mini?1.5:2.5).attr('stroke-linejoin','round').style('pointer-events','none');
    this.gVenArrow=gRoot.append('g').style('pointer-events','none');
    this.path=d3.geoPath(d3.geoTransform({point(x,y){const p=map.latLngToLayerPoint(L.latLng(y,x));this.stream.point(p.x,p.y);}}));
    this.evLayer=L.layerGroup().addTo(map);this.venLayer=L.layerGroup().addTo(map);
    map.on('click',e=>{if(this.adding&&!this.mini)this.dispatchEvent(new CustomEvent('sopot-venue-add',{bubbles:true,composed:true,detail:{lat:e.latlng.lat,lng:e.latlng.lng}}));});
    map.on('zoomend viewreset',()=>this._draw());map.on('moveend',()=>this._renderHeat());
    this._ro=new ResizeObserver(()=>{if(!this.offsetHeight)return;map.invalidateSize();if(this._ready)this._flyToFocus(false);});this._ro.observe(this);
    try{
      const [M,ci,la,lo]=await Promise.all([window.SopotModel.ready,...['data/sopot-city.geojson','data/sopot-land.geojson','data/sopot-lower-evidence.geojson'].map(u=>fetch(u).then(r=>{if(!r.ok)throw new Error(u);return r.json();}))]);
      this.M=M;this.city=ci.features[0];this.land=la.features[0];this.lower=lo.features[0];
      this.querySelector('.sm-loading').style.display='none';this._ready=true;map.invalidateSize();this._frame(false);this._flyToFocus(false);this._draw();
    }catch(err){this.querySelector('.sm-loading').textContent='Nie udało się wczytać granic obszarów ('+err.message+').';}
  }
  _bounds(){const L=this.L,b=L.geoJSON(this.land).getBounds();return L.latLngBounds([b.getSouth(),b.getWest()],[b.getNorth(),b.getEast()+.012]);}
  _fit(){try{const b=JSON.parse(this.getAttribute('fit')||'null');return b&&b.length===2?this.L.latLngBounds(b):null;}catch(e){return null;}}
  _frame(animate){const map=this._map,b=this._bounds();if(!b.isValid()||!map.getSize().y)return;this._framed=true;map.setMinZoom(0);map.setMaxBounds(null);const p=this._pads(),o=this.mini?{padding:[2,2]}:{paddingTopLeft:[10,10],paddingBottomRight:[p.br[0]-30,p.br[1]-30]};
    if(animate&&!this.mini)map.flyToBounds(b,{...o,duration:.7});else map.fitBounds(b,{...o,animate:false});
    const z=map.getBoundsZoom(b,false,this.L.point(20,20));map.setMinZoom(z);map.setMaxZoom(this.mini?z+3:z+2.5);map.setMaxBounds(b.pad(.25));}
  _flyToFocus(animate=true){const u=this.M.unitOf(this.focusKey);
    if(!u){const fb=this._fit();if(!fb||!this._map.getSize().y){this._frame(animate);return;}if(!this._framed)this._frame(false);const p=this._pads(),o=this.mini?{padding:[6,6],maxZoom:17,animate:false}:{paddingTopLeft:p.tl,paddingBottomRight:p.br,maxZoom:17};
      if(animate&&!this.mini)this._map.flyToBounds(fb,{...o,duration:.8});else this._map.fitBounds(fb,{...o,animate:false});return;}
    const pad=u.level==='code'?.0012:.0006,bb=[[u.minLat-pad,u.minLng-pad],[u.maxLat+pad,u.maxLng+pad]];
    const p=this._pads(),o={paddingTopLeft:p.tl,paddingBottomRight:p.br,maxZoom:u.level==='code'?16.5:u.level==='fives'?16:15.5};
    if(this.mini)this._map.fitBounds(bb,{padding:[6,6],animate:false,maxZoom:18});else if(!animate)this._map.fitBounds(bb,{...o,animate:false});else this._map.flyToBounds(bb,{...o,duration:.8});}
  _pxPerKm(){const m=this._map,a=m.latLngToLayerPoint([54.44,18.55]),b=m.latLngToLayerPoint([54.44,18.55+1/KX]);return Math.abs(b.x-a.x);}
  _draw(){
    if(!this._ready)return;const M=this.M,map=this._map,path=this.path,f=M.unitOf(this.focusKey),inFocus=pc=>!f||f.codes.has(pc);
    const b=path.bounds(this.city),pad=60,x0=b[0][0]-pad,y0=b[0][1]-pad,x1=b[1][0]+pad,y1=b[1][1]+pad;this.VB=[x0,y0,x1,y1];
    this.svg.attr('width',x1-x0).attr('height',y1-y0).style('left',x0+'px').style('top',y0+'px');this.gRoot.attr('transform',`translate(${-x0},${-y0})`);
    const cityD=path(this.city);this.cityClip.attr('d',cityD);this.gOutline.attr('d',cityD);this.gSea.attr('d',cityD);this.gLand.attr('d',path(this.land));this.gWash.attr('d',path(this.lower));
    const sp=map.latLngToLayerPoint([54.4400,18.5960]);this.gSeaLabel.attr('x',sp.x).attr('y',sp.y).attr('text-anchor','middle').attr('transform',`rotate(-68 ${sp.x} ${sp.y})`).text('Zatoka Gdańska');
    const groups=M.childrenOf(f),kids=[...M.UL.code.values()];
    this.focusClip.attr('d',cityD);
    const P=ll=>map.latLngToLayerPoint(ll);let e='',ge='',fe='';
    for(const ed of M.EDGES){const ia=inFocus(ed.a),ib=inFocus(ed.b);
      const p1=P([ed.p[1],ed.p[0]]),p2=P([ed.q[1],ed.q[0]]),seg=`M${p1.x},${p1.y}L${p2.x},${p2.y}`;
      if(f&&ia!==ib)fe+=seg;else if(M.keyAt.tens(ed.a)!==M.keyAt.tens(ed.b))ge+=seg;else e+=seg;}
    this.gEdges.attr('d',e).attr('stroke-opacity',.55).attr('stroke-width',.45);this.gGroupEdges.attr('d',ge);this.gFocusLine.attr('d',fe);
    this.CELL={kids,groups};
    this.gCells.selectAll('path').data(kids,u=>u.key).join('path').attr('class',u=>'sm-zone leaflet-interactive'+(u.disputed?' disp':'')).attr('d',u=>path(u.feature))
      .on('click',(ev,u)=>{ev.stopPropagation();if(this.mini)return;if(this.adding){const ll=this._map.mouseEventToLatLng(ev);this.dispatchEvent(new CustomEvent('sopot-venue-add',{bubbles:true,composed:true,detail:{lat:ll.lat,lng:ll.lng}}));return;}});
    this._drawHot();this._drawVenues();this.HEAT=null;this._paint();
  }
  // merchant venues (attribute `venues`, JSON): pin + label, thick outline of the venue's area, and the event's pull on that area as an arrow
  // (head at the venue = inflow, head at the event = outflow; width grows with the pull; dashed = no measurable effect)
  _drawVenues(){
    if(!this._ready)return;const M=this.M,L=this.L,map=this._map,mini=this.mini;let list=[];try{list=JSON.parse(this.getAttribute('venues')||'[]')||[];}catch(e){list=[];}
    this.venLayer.clearLayers();const P=ll=>map.latLngToLayerPoint(ll),ev=M.eventById(this.getAttribute('event')||'');
    const keys=[...new Set(list.map(v=>v.key).filter(Boolean))];
    this.gVenArea.selectAll('path').data(keys,k=>k).join('path').attr('d',k=>{const u=M.UL.code.get(k);return u?this.path(u.feature):'';});
    const arrows=[];
    if(ev)for(const v of list){if(v.force==null)continue;const E=P([ev.lat,ev.lng]),V=P([v.lat,v.lng]),dx=V.x-E.x,dy=V.y-E.y,d=Math.hypot(dx,dy);if(d<14)continue;
      const ux=dx/d,uy=dy/d,f=v.force,mag=Math.abs(f),weak=mag<3,inflow=f>=0,w=mini?(.8+Math.min(2.5,mag/25)):(1.3+Math.min(6,mag/12)),s0=mini?6:12,s1=mini?7:13;
      const x0=E.x+ux*s0,y0=E.y+uy*s0,x1=V.x-ux*s1,y1=V.y-uy*s1,cx=(x0+x1)/2-uy*d*.15,cy=(y0+y1)/2+ux*d*.15;
      const hx=inflow?x1:x0,hy=inflow?y1:y0,tx=inflow?x1-cx:x0-cx,ty=inflow?y1-cy:y0-cy,tl=Math.hypot(tx,ty)||1,tux=tx/tl,tuy=ty/tl,hs=mini?4:7+Math.min(4,mag/30);
      const head=weak?'':`M${hx-tux*hs+tuy*hs*.6},${hy-tuy*hs-tux*hs*.6}L${hx},${hy}L${hx-tux*hs-tuy*hs*.6},${hy-tuy*hs+tux*hs*.6}`;
      arrows.push({d:`M${x0},${y0}Q${cx},${cy} ${x1},${y1}`,head,w,weak,inflow,lx:.25*x0+.5*cx+.25*x1,ly:.25*y0+.5*cy+.25*y1,label:weak?'bez wpływu':`${f>0?'+':'−'}${mag} pkt · ${inflow?'napływ':'odpływ'}`});}
    const col=a=>a.inflow?css('--color-accent-900'):css('--color-neutral-600');
    const g=this.gVenArrow.selectAll('g').data(arrows).join(enter=>{const g=enter.append('g');g.append('path').attr('class','halo').attr('fill','none').attr('stroke','#fff').attr('stroke-opacity',.85).attr('stroke-linecap','round');g.append('path').attr('class','ink').attr('fill','none').attr('stroke-linecap','round');g.append('path').attr('class','head').attr('fill','none').attr('stroke-linecap','round').attr('stroke-linejoin','round');g.append('text').attr('class','sm-flabel');return g;});
    g.select('.halo').attr('d',a=>a.d).attr('stroke-width',a=>a.w+3);
    g.select('.ink').attr('d',a=>a.d).attr('stroke',col).attr('stroke-width',a=>a.w).attr('stroke-dasharray',a=>a.weak?'3 4':null);
    g.select('.head').attr('d',a=>a.head).attr('stroke',col).attr('stroke-width',a=>a.w);
    g.select('.sm-flabel').attr('x',a=>a.lx).attr('y',a=>a.ly-6).attr('fill',col).text(a=>mini?'':a.label);
    for(const v of list){const icon=L.divIcon({className:'',html:`<div class="sm-venue"><i></i><span>${esc(v.name)}</span></div>`,iconSize:[14,14],iconAnchor:[7,7]});
      const mk=L.marker([v.lat,v.lng],{icon,draggable:!mini,title:v.name,zIndexOffset:500}).addTo(this.venLayer);
      if(!mini)mk.on('dragend',()=>{const ll=mk.getLatLng();this.dispatchEvent(new CustomEvent('sopot-venue-move',{bubbles:true,composed:true,detail:{id:v.id,lat:ll.lat,lng:ll.lng}}));});}
  }
  // thick accent outline around the busiest group at the current level (attribute `hot`)
  _drawHot(){if(!this._ready||this.mini)return;const M=this.M,u=M.unitOf(this.getAttribute('hot')||''),f=M.unitOf(this.focusKey);
    if(!u){this.gHot.attr('d','');return;}const P=ll=>this._map.latLngToLayerPoint(ll);let d='';
    for(const ed of M.EDGES){const ia=u.codes.has(ed.a),ib=u.codes.has(ed.b);if(ia===ib)continue;if(f&&!(f.codes.has(ed.a)&&f.codes.has(ed.b)))continue;const p1=P([ed.p[1],ed.p[0]]),p2=P([ed.q[1],ed.q[0]]);d+='M'+p1.x+','+p1.y+'L'+p2.x+','+p2.y;}
    this.gHot.attr('d',d);}
  _paint(){
    if(!this._ready||!this.CELL)return;const M=this.M,c=M.ctx(this.pkd),{k,H}=this.cur();this._lastK=k;this._lastH=H;
    const off=c.lv==='locked'||c.lv==='region';this.classList.toggle('locked',off);
    this.querySelector('.sm-lockwhy').textContent=c.lv==='locked'?'Zbyt mało podmiotów w grupie — dane mogłyby ujawnić informacje o konkurencji.':'Dla tego kodu MCC analiza jest możliwa tylko na poziomie całego regionu, więc podział na obszary miasta jest wyłączony.';
    const lab=u=>M.nameOf(u),pct=v=>(v>=0?'+':'')+Math.round(v)+'%',hatch=`url(#${this._uid}hatch)`;
    // FIX 1 of 2 vs the prototype: one M.valueOf call per zone per paint (was three), and the
    // privacy gates decide whether a zone is drawn at all — an area the panel refuses to quantify
    // must not get a confident colour. research/app-forensics.md §7, honourable mentions.
    const vals=new Map();
    for(const u of this.CELL.kids)if(!vals.has(u.key))vals.set(u.key,M.readable(u)?M.valueOf(u,k,H,c):null);
    this.gCells.selectAll('path').style('fill',u=>vals.get(u.key)?null:hatch).style('fill-opacity',u=>vals.get(u.key)?null:.5)
      .each(function(u){const x=vals.get(u.key);
        const txt=x?pct(x.r*100)+' vs zwykle'+(x.src==='parent'?' (wartość większego obszaru: '+lab(x.from)+')':''):`dane ukryte · ${M.gateLine(u)||'mniej niż 3 podmioty'}`;
        this.innerHTML=`<title>${lab(u)}: ${txt}${u.disputed?' · granica niepewna (źródła adresowe niezgodne)':''} </title>`;});
    // event pins for the current calendar day (plus night events spilling over from the day before)
    const L=this.L,ev=this.evLayer;ev.clearLayers();const sel=this.getAttribute('event')||'';
    const evs=[...M.eventsOn(k),...M.eventsOn(M.addDays(k,-1)).filter(e=>M.eventWindow(e).en>24&&!M.eventsOn(k).includes(e))];
    for(const e of evs){if(this.mini&&e.id!==sel)continue;const u=M.eventUplift(e,c);const icon=L.divIcon({className:'',html:`<div class="sm-evpin${e.id===sel?' sel':''}"></div>`,iconSize:[e.id===sel?20:16,e.id===sel?20:16],iconAnchor:[e.id===sel?10:8,e.id===sel?10:8]});
      L.marker([e.lat,e.lng],{icon}).bindPopup(`<b>${e.title}</b><br>${e.time}–${e.end} · ${e.place}${u?`<br>Wzrost dla ${c.lv==='mcc'?'MCC '+c.p.mcc:'grupy '+M.GROUPS[c.g].name}: +${u}%`:''}`).addTo(ev);}
    this._renderHeat();
  }
  _heatWeights(){
    const M=this.M,map=this._map,f=M.unitOf(this.focusKey),key=[this.focusKey,map.getZoom(),map.getPixelOrigin().x,map.getPixelOrigin().y,map.getPixelBounds().min.x,map.getPixelBounds().min.y,this.smoothing].join('|');
    if(this.HEAT&&this.HEAT.key===key)return this.HEAT;
    const VB=this.VB,o=map.getPixelOrigin(),pb=map.getPixelBounds(),step=6;
    const X0=Math.floor(Math.max(VB[0],pb.min.x-o.x)/step)*step,Y0=Math.floor(Math.max(VB[1],pb.min.y-o.y)/step)*step,X1=Math.min(VB[2],pb.max.x-o.x),Y1=Math.min(VB[3],pb.max.y-o.y);
    const gw=Math.max(1,Math.ceil((X1-X0)/step)),gh=Math.max(1,Math.ceil((Y1-Y0)/step));
    const codes=[...M.UL.code.values()];
    const us=[];codes.forEach((u,ci)=>{for(const s of u.samples)us.push({ci,x:(s[0]-18.55)*KX,y:(s[1]-54.44)*KY});});
    const sigma=(f?(f.level==='code'?.09:.12):.16)*this.smoothing,s2=2*sigma*sigma,BK=Math.max(.7,sigma*4.2),expected=2*Math.PI*sigma*sigma/(.11*.11);
    const buckets=new Map();us.forEach((o,q)=>{const kk=Math.floor(o.x/BK)+','+Math.floor(o.y/BK);let arr=buckets.get(kk);if(!arr){arr=[];buckets.set(kk,arr);}arr.push(q);});
    const W=[],LL=[];
    for(let j=0;j<gh;j++)for(let i=0;i<gw;i++){const ll=map.layerPointToLatLng([X0+i*step+step/2,Y0+j*step+step/2]);LL.push(ll);
      const px=(ll.lng-18.55)*KX,py=(ll.lat-54.44)*KY,w=[],bx=Math.floor(px/BK),by=Math.floor(py/BK);
      for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){const arr=buckets.get((bx+dx)+','+(by+dy));if(!arr)continue;
        for(const q of arr){const o=us[q],ddx=o.x-px,ddy=o.y-py,e=Math.exp(-(ddx*ddx+ddy*ddy)/s2);if(e>2e-4)w.push(q,e);}}
      W.push(w);}
    const cv=document.createElement('canvas');cv.width=gw;cv.height=gh;
    this.HEAT={key,X0,Y0,gw,gh,step,codes,us,W,LL,cv,ctx2:cv.getContext('2d'),expected};return this.HEAT;
  }
  // raw field at fractional in-day hour tt on calendar day k: per-pixel value + coverage alpha
  _field(k,tt){
    const M=this.M,c=M.ctx(this.pkd),H=this._heatWeights(),N=H.gw*H.gh,metric=this.metric;
    const raw=new Float32Array(N).fill(NaN),alpha=new Float32Array(N),sst=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
    // FIX 2 of 2 vs the prototype: the heat raster is gated on the same privacy rules as the
    // tooltip. It used M.predCount, which has no gate, so it painted 125 of 151 areas while the
    // tooltip declared only 18 readable. An area we refuse to quantify is not coloured at all.
    const A=H.codes.map(u=>{
      if(!M.readable(u))return null;
      const v=metric==='zl'?M.amountAt(u,k,tt,c):metric==='rel'?M.relAt(u,k,tt,c):M.predCount(u,k,tt,c);
      return v==null||!isFinite(v)?null:v;});
    for(let p=0;p<N;p++){const w=H.W[p];let s=0,sw=0,st=0;
      for(let q=0;q<w.length;q+=2){const wt=w[q+1];st+=wt;const a=A[H.us[w[q]].ci];if(a==null)continue;s+=a*wt;sw+=wt;}
      if(sw>1e-5){raw[p]=s/sw;alpha[p]=sst(st/(.35*H.expected))*sst((sw/st-.15)/.7);}}
    return {raw,alpha,rel:metric==='rel'};
  }
  _renderHeat(){
    if(!this._ready||!this.VB)return;const M=this.M,d3=this.d3,c=M.ctx(this.pkd);
    if(c.lv==='locked'||c.lv==='region'){this.heatImg.attr('href',null);this.gContours.selectAll('*').remove();this.gFlow.selectAll('*').remove();return;}
    const {k,tt}=this.cur(),H=this._heatWeights(),N=H.gw*H.gh,F=this._field(k,tt),vals=new Float32Array(N).fill(NaN),alpha=F.alpha;
    if(F.rel){for(let p=0;p<N;p++){const r=F.raw[p];if(!isNaN(r))vals[p]=r<0?.5+r/.8:.5+r/2;}}
    else{const sorted=[...F.raw].filter((v,p)=>!isNaN(v)&&alpha[p]>.3).sort((a,b)=>a-b);
      const lo=sorted[Math.floor(sorted.length*.02)]??0,hi=sorted[Math.floor(sorted.length*.98)]??1,span=Math.max(1e-6,hi-lo);
      for(let p=0;p<N;p++)if(!isNaN(F.raw[p]))vals[p]=(F.raw[p]-lo)/span;}
    const img=H.ctx2.createImageData(H.gw,H.gh);
    for(let p=0;p<N;p++){const v=vals[p];if(isNaN(v))continue;const col=d3.rgb(seis(d3,v));img.data[4*p]=col.r;img.data[4*p+1]=col.g;img.data[4*p+2]=col.b;img.data[4*p+3]=Math.round(235*alpha[p]);}
    H.ctx2.putImageData(img,0,0);
    this.heatImg.attr('x',H.X0).attr('y',H.Y0).attr('width',H.gw*H.step).attr('height',H.gh*H.step).attr('href',H.cv.toDataURL());
    const cvals=Array.from(vals,(v,p)=>isNaN(v)||alpha[p]<.5?-1:v);
    const cont=d3.contours().size([H.gw,H.gh]).thresholds(d3.range(.1,1,.1))(cvals);
    const cp=d3.geoPath(d3.geoTransform({point(x,y){this.stream.point(H.X0+x*H.step,H.Y0+y*H.step);}}));
    this.gContours.selectAll('path').data(cont).join('path').attr('d',cp).attr('stroke','#fff').attr('stroke-opacity',(d,i)=>i%5===4?.55:.28).attr('stroke-width',(d,i)=>i%5===4?.9:.5);
    this._renderFlow(k,tt,F);
  }
  // tendency arrows: gradient of the change of the field over the next hour — arrows point from where activity is fading to where it is growing
  _renderFlow(k,tt,F){
    const M=this.M,H=this._heatWeights(),gw=H.gw,gh=H.gh;
    if(this.mini||this.hasAttribute('noflow')){this.gFlow.selectAll('*').remove();return;}
    let k2=k,t2=tt+1;if(t2>=24){t2-=24;k2=M.addDays(k,1);}
    const F2=this._field(k2,t2),D=new Float32Array(gw*gh);
    for(let p=0;p<D.length;p++){const a=F.raw[p],b=F2.raw[p];D[p]=isNaN(a)||isNaN(b)?NaN:b-a;}
    const K=Math.max(6,Math.round(54/H.step)),arrows=[];let gmax=0;
    for(let j=Math.floor(K/2);j<gh-1;j+=K)for(let i=Math.floor(K/2);i<gw-1;i+=K){const p=j*gw+i;if(F.alpha[p]<.5)continue;
      const l=D[p-1],r=D[p+1],u=D[p-gw],d=D[p+gw];if([l,r,u,d].some(v=>v===undefined||isNaN(v)))continue;
      const gx=(r-l)/2,gy=(d-u)/2,g=Math.hypot(gx,gy);if(!(g>0))continue;gmax=Math.max(gmax,g);arrows.push({x:H.X0+(i+.5)*H.step,y:H.Y0+(j+.5)*H.step,gx,gy,g});}
    const L=Math.min(30,K*H.step*.55),paths=[];
    for(const a of arrows){const m=a.g/gmax;if(m<.12)continue;const len=L*(.35+.65*m),ux=a.gx/a.g,uy=a.gy/a.g,x0=a.x-ux*len/2,y0=a.y-uy*len/2,x1=a.x+ux*len/2,y1=a.y+uy*len/2;
      const hx=-ux*5+uy*3.5,hy=-uy*5-ux*3.5,hx2=-ux*5-uy*3.5,hy2=-uy*5+ux*3.5;
      paths.push({d:`M${x0},${y0}L${x1},${y1}M${x1+hx},${y1+hy}L${x1},${y1}L${x1+hx2},${y1+hy2}`,o:.45+.55*m});}
    const sel=this.gFlow.selectAll('g').data(paths).join(enter=>{const g=enter.append('g');g.append('path').attr('class','halo').attr('stroke','#fff').attr('stroke-width',3.4).attr('stroke-opacity',.75);g.append('path').attr('class','ink').attr('stroke',css('--color-text')).attr('stroke-width',1.5);return g;});
    sel.select('.halo').attr('d',p=>p.d);sel.select('.ink').attr('d',p=>p.d).attr('stroke-opacity',p=>p.o);
  }

}
if(!customElements.get('sopot-map'))customElements.define('sopot-map',SopotMap);
})();
