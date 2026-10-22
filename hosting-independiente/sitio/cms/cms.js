/* Cisne Negro CMS · framework-free client. The server owns authorization and publication. */
(function () {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clone = value => JSON.parse(JSON.stringify(value));
  const json = value => JSON.stringify(value);
  const money = value => new Intl.NumberFormat('es-MX', {style:'currency', currency:'MXN', maximumFractionDigits:2}).format(Number(value) || 0);
  const date = value => { if (!value) return 'Sin fecha'; const d = new Date(value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('es-MX', {dateStyle:'medium', timeStyle:'short'}); };
  const bytes = n => { n = Number(n) || 0; return n < 1024 * 1024 ? (n / 1024).toFixed(0) + ' KB' : n < 1024 ** 3 ? (n / 1024 ** 2).toFixed(1) + ' MB' : (n / 1024 ** 3).toFixed(2) + ' GB'; };
  const uid = prefix => prefix + '-' + (globalThis.crypto?.randomUUID ? crypto.randomUUID().slice(0, 12) : Date.now().toString(36) + Math.random().toString(36).slice(2, 6));
  const paths = {home:'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',edit:'m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15z',menu:'M4 3h16v18H4zM8 7h8M8 11h8M8 15h5',media:'M3 4h18v16H3zM3 15l5-5 5 5 3-3 5 5M15 8h.01',event:'M4 5h16v16H4zM7 3v4M17 3v4M4 10h16M8 14h2M14 14h2',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2',history:'M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2',users:'M8 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M2 21v-3a6 6 0 0 1 12 0v3M16 4a4 4 0 0 1 0 8M17 15a5 5 0 0 1 5 5v1',club:'M4 4h16v17H4zM8 8h8M8 12h5M14 17l2 2 4-4',upload:'M12 16V3M7 8l5-5 5 5M3 15v6h18v-6',plus:'M12 4v16M4 12h16',video:'M4 4h16v16H4zM10 8l6 4-6 4z',arrow:'M5 12h14M14 7l5 5-5 5',check:'m4 12 5 5L20 6'};
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.menu}"></path></svg>`;
  const modules = [{id:'inicio',label:'Inicio',icon:'home'},{id:'editor',label:'Editor visual',icon:'edit'},{id:'menu',label:'Menú y cervezas',icon:'menu'},{id:'media',label:'MediaHub',icon:'media'},{id:'eventos',label:'Eventos y galería',icon:'event'},{id:'negocio',label:'Datos del negocio',icon:'settings'},{id:'publicaciones',label:'Publicaciones',icon:'history'},{id:'usuarios',label:'Usuarios',icon:'users',owner:true}];
  const state = {user:null, csrf:'', document:null, baseline:null, publicBaseline:null, version:null, published:null, schema:[], summary:{}, dirty:false, busy:false, agentBusy:false, route:'inicio', menuTab:'barril', contentTab:'events', media:{q:'',category:'',kind:'',page:1,archived:false}, mediaCache:new Map(), uploads:[], uploading:false, uploadEpoch:0, uploadController:null, viewToken:0, interrupted:null};
  const owner = () => state.user?.role === 'owner';
  function getPath(obj, key) { return key.split('.').reduce((v, k) => v == null ? undefined : v[k], obj); }
  function setPath(obj, key, value) {
    const parts = key.split('.'); if (parts.some(p => ['__proto__','constructor','prototype'].includes(p))) throw new Error('Campo no permitido.');
    const last = parts.pop(); let current = obj;
    parts.forEach((p, i) => { if (!current[p] || typeof current[p] !== 'object') current[p] = /^\d+$/.test(parts[i + 1] || last) ? [] : {}; current = current[p]; });
    current[last] = value;
  }
  function safeURL(value) { const s = String(value || ''); return /^(\/[^/]|https?:\/\/|blob:)/i.test(s) ? s : ''; }
  function imageURL(value, kind = '') {
    if (!value) return ''; const safe = safeURL(value); if (safe) return safe;
    if (/^[a-zA-Z0-9_./-]+$/.test(value) && !value.includes('..')) return '/assets/img/' + (kind === 'barril' ? 'cervezas/' : kind === 'comida' ? 'menu/' : '') + value;
    return '';
  }
  function toast(message, error = false) { const el = document.createElement('div'); el.className = 'toast' + (error ? ' error' : ''); el.textContent = message; $('#notifications').append(el); setTimeout(() => el.remove(), error ? 10000 : 6000); }
  function message(text, reload = false) {
    const box = $('#page-message'); box.hidden = !text; box.replaceChildren(); if (!text) return;
    const p = document.createElement('p'); p.textContent = text; box.append(p);
    if (reload) { const b = document.createElement('button'); b.className = 'button secondary small'; b.textContent = 'Recargar borrador del servidor'; b.addEventListener('click', reloadDraft); box.append(b); }
  }
  function status() {
    const e = $('#save-status'); e.textContent = state.busy ? 'Guardando…' : state.dirty ? 'Cambios sin guardar' : 'Borrador guardado'; e.classList.toggle('dirty', state.dirty);
    $('#save-draft').disabled = !state.document || state.busy || !state.dirty;
    $('#publish').hidden = !owner(); $('#publish').disabled = !state.document || state.busy;
  }
  function changed() { state.dirty = json(state.document) !== json(state.baseline); status(); window.CisneAgent?.refresh(); }
  async function api(path, options = {}) {
    const init = {credentials:'same-origin', ...options, headers:{Accept:'application/json', ...(options.headers || {})}};
    if (init.body && !(init.body instanceof FormData)) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(init.body); }
    if (init.method && init.method !== 'GET') init.headers['X-CSRF-Token'] = state.csrf;
    let response;
    try { response = await fetch('/cms/api' + path, init); } catch (_) { throw new Error('No pudimos conectar. Revisa tu conexión e intenta de nuevo; tus cambios siguen en este navegador.'); }
    let data; try { data = await response.json(); } catch (_) { throw new Error('El servidor no devolvió una respuesta válida. Intenta de nuevo.'); }
    if (!response.ok) {
      const error = new Error(data.error || data.message || 'No fue posible completar la operación.'); error.status = response.status; error.details = data.details;
      if (response.status === 401 && path !== '/session' && path !== '/login') { state.interrupted = state.document ? {user:state.user?.id, document:clone(state.document), baseline:clone(state.baseline), version:state.version, dirty:state.dirty} : null; showLogin('Tu sesión terminó. Vuelve a entrar para continuar.'); }
      if (response.status === 409) message('Otra persona actualizó el borrador. Tus cambios permanecen aquí. Revisa la versión del servidor antes de continuar.', true);
      throw error;
    }
    return data;
  }
  function stopUploads() { state.uploadEpoch++; state.uploadController?.abort(); state.uploads.forEach(job=>{if(['queued','uploading'].includes(job.status)){job.status='error';job.error='Carga interrumpida. Vuelve a intentarlo.';}}); }
  function showLogin(error = '') { closeAgent(false); window.CisneAgent?.reset(); stopUploads(); $$('dialog[open]').forEach(el=>el.close()); $('#boot').hidden = true; $('#app').hidden = true; $('#login-screen').hidden = false; $('#login-error').textContent = error; $('#login-error').hidden = !error; }
  async function loadState(keepLocal = false) {
    const data = await api('/state'); state.document = data.document; state.baseline = clone(data.document); state.publicBaseline = data.published_document || null; state.version = data.version; state.published = data.published_version; state.schema = (data.schema || []).map(friendlyField); state.summary = data.summary || {}; state.user = data.user || state.user; state.dirty = false;
    if (keepLocal && state.interrupted?.user === state.user.id && state.interrupted.dirty) {
      const old = state.interrupted; state.document = old.document; state.baseline = old.baseline; state.version = old.version; state.dirty = true;
      message('Recuperamos los cambios que tenías abiertos en este navegador. Guárdalos para continuar.');
    }
    state.interrupted = null; $('#boot').hidden = true; $('#login-screen').hidden = true; $('#app').hidden = false;
    $('#user-name').textContent = state.user.name || state.user.username; $('#user-role').textContent = owner() ? 'Propietario' : 'Editor'; $('#user-avatar').textContent = (state.user.name || state.user.username).slice(0, 2).toUpperCase();
    $('#main-nav').innerHTML = modules.filter(m => !m.owner || owner()).map(m => `<a class="nav-item" href="#${m.id}" data-nav="${m.id}">${icon(m.icon)}<span>${m.label}</span></a>`).join('') + (owner() ? `<a class="nav-item" href="/admin/">${icon('club')}<span>Pasaporte</span><span aria-hidden="true">↗</span></a>` : '');
    status(); await route();
  }
  async function reloadDraft() { if(state.busy)return; if (state.dirty && !confirm('Se descartarán los cambios sin guardar de este navegador. ¿Cargar la versión del servidor?')) return; state.busy=true; $('#app').inert=true; status(); try { message(''); await loadState(); toast('Borrador actualizado.'); } catch (e) { toast(e.message, true); } finally {state.busy=false;$('#app').inert=false;status();} }
  async function saveDraft() {
    if (state.busy) throw new Error('Espera a que termine la operación actual.'); if (!state.dirty) return;
    state.busy = true; status(); const submitted = clone(state.document);
    try { const result = await api('/draft', {method:'PUT',body:{document:submitted,version:state.version}}); state.version = result.version; state.baseline = submitted; changed(); message(''); toast('Borrador guardado. La página pública no ha cambiado.'); refreshPreview(); }
    finally { state.busy = false; status(); }
  }
  function diff(a, b, prefix = '', out = []) {
    if (json(a) === json(b)) return out;
    if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) { new Set([...Object.keys(a),...Object.keys(b)]).forEach(k => diff(a[k],b[k],prefix ? prefix + '.' + k : k,out)); }
    else out.push({path:prefix,before:a,after:b}); return out;
  }
  function textValue(v) { if (v == null) return 'Sin contenido'; if (typeof v === 'boolean') return v ? 'Sí' : 'No'; return typeof v === 'object' ? JSON.stringify(v,null,2) : String(v); }
  function diffHTML(changes) { return changes.length ? `<div class="diff-list">${changes.map(x => `<div class="diff-row"><strong>${esc(state.schema.find(s => s.key === x.path)?.label || x.path)}</strong><div class="diff-values"><span><small>Publicado</small><br>${esc(textValue(x.before))}</span><span><small>Borrador</small><br>${esc(textValue(x.after))}</span></div></div>`).join('')}</div>` : '<p class="muted">El borrador coincide con la versión publicada.</p>'; }
  async function publishDialog() {
    if (!owner()) return;
    const changes = diff(state.publicBaseline,state.document);
    dialog({title:'Publicar una nueva versión',body:`<p class="muted">Se guardará el borrador y se actualizarán la página y el menú con una versión completa.</p><div class="section-space">${diffHTML(changes)}</div><label for="publish-note">Nota de esta publicación</label><input id="publish-note" name="note" maxlength="300" placeholder="Por ejemplo: precios de temporada y nuevos barriles" required>`,submit:'Publicar ahora',onSubmit:async form => {
      if (state.dirty) await saveDraft(); state.busy = true; status();
      try { const result = await api('/publish',{method:'POST',body:{version:state.version,note:form.elements.note.value.trim()}}); state.published = result.published_version ?? result.version; toast('La nueva versión ya está publicada.'); if (!state.dirty) await loadState(); }
      finally { state.busy = false; status(); }
    }});
  }
  function dialog({title,body,submit='Guardar',onSubmit,width=false}) {
    const el = document.createElement('dialog'); const titleId = uid('dialog'); el.className = width ? 'wide-dialog' : ''; el.setAttribute('aria-labelledby',titleId);
    el.innerHTML = `<form><div class="dialog-head"><h2 id="${titleId}">${esc(title)}</h2><button type="button" class="icon-button" data-close aria-label="Cerrar">×</button></div><div class="dialog-body">${body}</div><p class="form-error dialog-error" role="alert" hidden></p><div class="dialog-footer"><button type="button" class="button ghost" data-close>${submit ? 'Cancelar' : 'Cerrar'}</button>${submit ? `<button type="submit" class="button primary">${esc(submit)}</button>` : ''}</div></form>`;
    document.body.append(el); const form = $('form',el); let edited = false, submitting = false; const opener = document.activeElement;
    const close = (force = false) => { if (submitting && !force) return; if (!force && edited && onSubmit && !confirm('¿Cerrar sin guardar estos cambios?')) return; el.close(); };
    $$('[data-close]',el).forEach(b => b.addEventListener('click',() => close()));
    form.addEventListener('input',() => { edited = true; el.dataset.edited='true'; }); form.addEventListener('change',() => { edited = true; el.dataset.edited='true'; });
    el.addEventListener('cancel',e => { e.preventDefault(); close(); });
    el.addEventListener('close',() => { el.remove(); if (opener?.isConnected) opener.focus(); });
    form.addEventListener('submit',async e => { e.preventDefault(); if (!onSubmit || submitting || !form.reportValidity()) return; submitting = true; form.inert=true; const b = $('[type=submit]',form); b.disabled = true; $('.dialog-error',el).hidden = true;
      try { await onSubmit(form,el); submitting = false; close(true); }
      catch (error) { $('.dialog-error',el).textContent = error.message; $('.dialog-error',el).hidden = false; $('.dialog-error',el).scrollIntoView({block:'nearest'}); }
      finally { submitting = false; form.inert=false; b.disabled = false; }
    }); el.showModal(); return {el,form,close,clean:() => {edited=false;delete el.dataset.edited;}};
  }
  function pageHeading(title,description,actions='') { return `<div class="page-heading"><div><p class="eyebrow">Cisne Negro · Panel del equipo</p><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${actions ? `<div class="button-row">${actions}</div>` : ''}</div>`; }
  function empty(title,description='') { return `<div class="empty"><h3>${esc(title)}</h3><p>${esc(description)}</p></div>`; }
  function setView(html) { $('#workspace').innerHTML = html; }
  async function route() {
    if (!state.document) return;
    const name = location.hash.slice(1).split('?')[0] || 'inicio', requestedAgent = name === 'agente';
    const target = requestedAgent ? state.route : name;
    state.route = modules.some(m => m.id === target && (!m.owner || owner())) ? target : 'inicio'; state.viewToken++;
    if (requestedAgent) history.replaceState(null, '', location.pathname + location.search + '#' + state.route);
    $$('.nav-item[data-nav]').forEach(a => { if (a.dataset.nav === state.route) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    $('#breadcrumb').textContent = modules.find(m => m.id === state.route).label; closeSidebar();
    try {
      const views = {inicio:renderHome,editor:renderEditor,menu:renderMenu,media:renderMedia,eventos:renderEvents,negocio:renderBusiness,publicaciones:renderRevisions,usuarios:renderUsers}; await views[state.route]();
      window.CisneAgent?.refresh();
      if (requestedAgent) openAgent();
    } catch (e) { setView(pageHeading('No pudimos cargar esta sección',e.message,'<button class="button secondary" data-action="retry-view">Volver a intentar</button>')); }
  }
  let agentOpener = null;
  function closeAgent(restoreFocus = true) {
    const popup = $('#agent-popup');
    if (!popup.open) return;
    popup.close(); window.CisneAgent?.unmount(); $('#agent-launcher').setAttribute('aria-expanded','false');
    if (restoreFocus && agentOpener?.isConnected) agentOpener.focus({preventScroll:true});
  }
  function openAgent() {
    if (!state.document || $('#app').hidden || $('#agent-popup').open) return;
    if (!window.CisneAgent) { toast('No se pudo cargar el agente. Recarga el panel.', true); return; }
    agentOpener = document.activeElement?.closest('#app') ? document.activeElement : $('#agent-launcher');
    closeSidebar(); $('#agent-popup').showModal(); $('#agent-launcher').setAttribute('aria-expanded','true');
    window.CisneAgent.mount($('#agent-workspace'), {
      api, mediaPicker, toast,
      snapshot: () => ({version:state.version, dirty:state.dirty, busy:state.busy, menu:clone(state.document?.menu || {})}),
      save: saveDraft,
      refresh: async () => {
        if (state.dirty) throw new Error('Hay cambios locales sin guardar. Recarga el borrador después de guardarlos.');
        await loadState(); message('');
      },
      run: async task => {
        if (state.busy) throw new Error('Espera a que termine la operación actual.');
        if (state.dirty) throw new Error('Guarda primero los cambios del CMS para trabajar con el agente.');
        state.agentBusy=true; state.busy=true; $('#sidebar').inert=true; $('.workspace-shell').inert=true; $('#logout').disabled=true; $('#agent-launcher').classList.add('is-working'); status();
        try { return await task(); }
        finally { state.agentBusy=false; state.busy=false; $('#sidebar').inert=false; $('.workspace-shell').inert=false; $('#logout').disabled=false; $('#agent-launcher').classList.remove('is-working'); status(); }
      }
    });
    $('#agent-close').focus({preventScroll:true});
  }
  $('#agent-launcher').addEventListener('click', openAgent);
  $('#agent-close').addEventListener('click', () => closeAgent());
  $('#agent-popup').addEventListener('cancel', event => { event.preventDefault(); closeAgent(); });
  $('#agent-popup').addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const focusable = $$('button, a[href], input, select, textarea, summary, [tabindex]', $('#agent-popup')).filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  });
  function productCount() { const m = state.document.menu || {}; return ['barril','latas','sin_alcohol'].reduce((n,k) => n + (m[k]?.length || 0),0) + (m.comida || []).reduce((n,c) => n + (c.items?.length || 0),0); }
  function renderHome() {
    const s = state.summary; const quick = [{id:'editor',icon:'edit',title:'Dale vida a la portada',desc:'Textos, imágenes y el video del hero'},{id:'menu',icon:'menu',title:'Pon al día la carta',desc:'Precios, disponibilidad y maridajes'},{id:'media',icon:'media',title:'Encuentra la siguiente historia',desc:'Fotos y videos de tu cervecería'}];
    setView(pageHeading('Hola, ' + (state.user.name || state.user.username).split(' ')[0] + '.', 'Este es el lugar para mantener al Cisne al día.') + `<div class="welcome"><h2>Una buena cerveza.<br>Una historia que contar.</h2><p>Todo lo que hace único al Cisne, en manos de tu equipo.</p><a class="button primary" href="#editor">Editar la página ${icon('arrow')}</a><img src="/assets/img/marca/cisne-mascota.jpg" alt="Mascota de Cisne Negro" width="160" height="160"></div><div class="grid three"><div class="stat"><span class="eyebrow">En la carta</span><div class="stat-number">${productCount()}</div><p>Productos para descubrir</p></div><div class="stat"><span class="eyebrow">MediaHub</span><div class="stat-number">${Number(s.media)||0}</div><p>Fotos y videos${s.media_processing ? ' · ' + Number(s.media_processing) + ' en proceso' : ''}</p></div><div class="stat"><span class="eyebrow">Experiencias</span><div class="stat-number">${state.document.events?.length || 0}</div><p>Eventos en tu calendario</p></div></div><div class="grid two section-space"><section class="card"><div class="card-head"><h2>¿Por dónde empezamos?</h2></div>${quick.map(q => `<a class="quick-link" href="#${q.id}"><span>${icon(q.icon)}</span><div><strong>${q.title}</strong><small>${q.desc}</small></div>${icon('arrow')}</a>`).join('')}</section><section class="card"><div class="card-head"><h2>Tu publicación</h2><span class="badge ${state.dirty?'':'green'}">${state.dirty?'Pendientes':'Borrador guardado'}</span></div><ul class="list"><li><strong>Borrador ${esc(state.version)}</strong><small>Guarda tus cambios para conservarlos sin publicarlos.</small></li><li><strong>${state.published == null ? 'Sin versión publicada' : 'Versión publicada ' + esc(state.published)}</strong><small>La web y el menú comparten el contenido publicado.</small></li><li><strong>${bytes(s.storage_bytes)}${s.storage_limit ? ' de ' + bytes(s.storage_limit) : ''}</strong><small>Almacenamiento multimedia${s.storage_limit ? '' : ' · cuota disponible en el servidor'}</small></li></ul><a class="button ghost small section-space" href="#publicaciones">Revisar publicaciones ${icon('arrow')}</a></section></div>`);
  }
  function optionsHTML(options,value) { return (options || []).map(o => { const v = typeof o === 'object' ? o.value : o, label = typeof o === 'object' ? o.label : o; return `<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(label)}</option>`; }).join(''); }
  function friendlyField(field) {
    const s={...field}; if(!s.key.startsWith('page.'))return s; const key=s.key.slice(5);
    const labels={hero_desc:'Descripción breve',hero_video_desktop:'Video para escritorio',hero_video_mobile:'Video para celular',hero_title:'Título de la portada',hero_lead:'Texto de bienvenida',hero_kicker:'Ubicación y presentación',hero_mode:'Imagen o video de portada',hero_image:'Fotografía de portada',hero_poster:'Fotografía mientras carga el video',historia_image:'Fotografía de la historia',historia_image_alt:'Descripción alternativa de la fotografía',schema_description:'Descripción para los resultados de búsqueda'};
    const groups={hero:'Portada',historia:'Nuestra historia',pair:'Maridajes destacados',schema:'Buscadores',galeria:'Galería',visitanos:'Visítanos',barril:'Cervezas de barril',comedor:'Cocina',eventos:'Eventos',pasaporte:'Pasaporte'};
    const prefix=key.split('_')[0]; if(groups[prefix])s.section=groups[prefix]; if(labels[key])s.label=labels[key];
    const pair=key.match(/^pair_(\d+)_(beer_id|food_id|description)$/);
    if(pair){s.label=`Maridaje ${Number(pair[1])+1} · ${pair[2]==='beer_id'?'Cerveza':pair[2]==='food_id'?'Platillo':'Descripción'}`;if(pair[2]!=='description')s.type='select';}
    const numbered=key.match(/_(h2|h3|p|li|cite)_(\d+)$/);
    if(numbered){const names={h2:'Título de la sección',h3:'Subtítulo',p:'Texto',li:'Punto destacado',cite:'Autor de la cita'};s.label=names[numbered[1]]+(numbered[1]==='h2'&&numbered[2]==='1'?'':' '+numbered[2]);}
    return s;
  }
  function schemaField(s) {
    const pair=s.key.match(/^page\.pair_\d+_(beer|food)_id$/);
    if(pair){const items=pair[1]==='beer'?(state.document.menu.barril||[]):(state.document.menu.comida||[]).flatMap(c=>c.items||[]);s={...s,type:'select',options:[{value:'',label:'Selecciona una opción'},...items.map(p=>({value:p.id,label:p.nombre}))]};}
    const value = getPath(state.document,s.key); const id = 'field-' + s.key.replace(/[^\w-]/g,'-'); const attrs = `id="${id}" data-doc-path="${esc(s.key)}" data-type="${esc(s.type)}" ${s.readonly || s.readOnly ? 'readonly' : ''}`;
    let control;
    if (['image','video'].includes(s.type)) { const url = imageURL(value); control = `<div class="field-media">${url ? s.type==='video'?`<video src="${esc(url)}" muted preload="metadata" aria-label="Video seleccionado"></video>`:`<img src="${esc(url)}" alt="" loading="lazy">`:`<span class="image-placeholder">${icon(s.type==='video'?'video':'media')}</span>`}<div><span class="fine">${value?'Archivo seleccionado':'Sin archivo seleccionado'}</span><button id="${id}" class="button secondary" type="button" data-pick-path="${esc(s.key)}" data-kind="${s.type}">Elegir en MediaHub</button>${value?` <button class="button ghost" type="button" data-clear-path="${esc(s.key)}">Quitar</button>`:''}</div></div>`; }
    else if (s.type === 'textarea') control = `<textarea ${attrs} rows="4">${esc(value)}</textarea>`;
    else if (s.type === 'boolean') control = `<label class="check"><input type="checkbox" ${attrs} ${value?'checked':''}>${esc(s.label)}</label>`;
    else if (s.type === 'select') control = `<select ${attrs}>${optionsHTML(s.options,value)}</select>`;
    else if (s.type === 'multiselect') control = `<select ${attrs} multiple size="5">${(s.options||[]).map(o => { const v=typeof o==='object'?o.value:o,l=typeof o==='object'?o.label:o; return `<option value="${esc(v)}" ${(value||[]).map(String).includes(String(v))?'selected':''}>${esc(l)}</option>`; }).join('')}</select>`;
    else control = `<input ${attrs} type="${s.type==='number'?'number':s.type==='url'?'url':'text'}" ${s.type==='number'?'step="any"':''} value="${esc(value)}">`;
    return `<div class="field ${s.type==='textarea'?'wide':''}" data-field-key="${esc(s.key)}">${s.type==='boolean'?'':`<label for="${id}">${esc(s.label)}</label>`}${control}${s.help ? `<p class="field-help">${esc(s.help)}</p>` : ''}</div>`;
  }
  function schemaGroups(fields,accordion=false,opened=['Portada']) {
    const grouped = new Map(); fields.forEach(s => { const section=s.section || 'Contenido'; if(!grouped.has(section))grouped.set(section,[]); grouped.get(section).push(s); });
    const order=['Portada','Cervezas de barril','Cocina','Maridajes destacados','Nuestra historia','Galería','Eventos','Pasaporte','Visítanos','Pie de página','Buscadores'];
    return [...grouped].sort((a,b)=>{const rank=x=>order.includes(x)?order.indexOf(x):99;return rank(a[0])-rank(b[0]);}).map(([section,items]) => accordion?`<details class="card settings-group editor-group" data-editor-section="${esc(section)}" ${opened.includes(section)?'open':''}><summary><span>${esc(section)}</span><small>${items.length} campos</small></summary><div class="fields">${items.map(schemaField).join('')}</div></details>`:`<section class="card settings-group"><h2>${esc(section)}</h2><div class="fields">${items.map(schemaField).join('')}</div></section>`).join('');
  }
  function renderEditor() {
    const fields=state.schema.filter(s => s.key.startsWith('page.'));
    const opened=$('.editor-fields')?$$('[data-editor-section][open]').map(el=>el.dataset.editorSection):['Portada'];
    setView(pageHeading('Editor visual','Selecciona un bloque de la vista previa o edita sus campos. Guarda el borrador para actualizar la vista.')+`<div class="editor-layout"><div class="editor-fields">${fields.length?schemaGroups(fields,true,opened):empty('No hay campos disponibles','El servidor todavía no ofrece campos de página editables.')}</div><section class="preview-panel" aria-label="Vista previa privada"><div class="preview-tools"><div class="button-row"><button class="button secondary" data-preview-size="desktop" aria-pressed="true">Escritorio</button><button class="button ghost" data-preview-size="mobile" aria-pressed="false">Celular</button></div><button class="button ghost" data-action="refresh-preview">Actualizar</button></div><div class="preview-frame-wrap" id="preview-wrap"><iframe id="preview-frame" src="/cms/preview/?v=${encodeURIComponent(state.version)}" title="Vista previa privada de la página"></iframe></div><p class="preview-note">Solo visible para el equipo. Los cambios guardados no aparecen en la web hasta publicarlos.</p></section></div>`);
  }
  function refreshPreview() { const frame=$('#preview-frame'); if(frame)frame.src='/cms/preview/?v='+encodeURIComponent(state.version)+'&t='+Date.now(); }
  function renderBusiness() {
    const fields=state.schema.filter(s=>s.key.startsWith('menu.negocio.'));
    setView(pageHeading('Datos del negocio','La información que ayuda a encontrar el Cisne y venir a visitarlo.')+(fields.length?schemaGroups(fields):empty('No hay campos de negocio disponibles','Revisa la configuración editorial del servidor.')));
  }
  function inputField(name,label,value='',type='text',extra='') {
    const id=uid('input'); return `<div class="field ${type==='textarea'?'wide':''}"><label for="${id}">${esc(label)}</label>${type==='textarea'?`<textarea id="${id}" name="${esc(name)}" ${extra}>${esc(value)}</textarea>`:`<input id="${id}" name="${esc(name)}" type="${type}" value="${esc(value)}" ${extra}>`}</div>`;
  }
  function fieldValue(form,name) { return form.elements.namedItem(name)?.value?.trim() || ''; }
  function menuList(kind,category) { const menu=state.document.menu; return kind==='comida' ? menu.comida[Number(category)].items : menu[kind]; }
  function rowActions(kind,index,category,length) {
    const data=`data-kind="${kind}" data-index="${index}" data-category="${category==null?'':category}"`;
    return `<div class="row-actions"><button class="icon-button" data-action="edit-product" ${data} aria-label="Editar producto" title="Editar">${icon('edit')}</button><button class="icon-button" data-action="move-product" data-direction="-1" ${data} ${index===0?'disabled':''} aria-label="Subir producto">↑</button><button class="icon-button" data-action="move-product" data-direction="1" ${data} ${index===length-1?'disabled':''} aria-label="Bajar producto">↓</button><button class="icon-button" data-action="delete-product" ${data} aria-label="Eliminar producto" title="Eliminar">×</button></div>`;
  }
  function productTable(items,kind,category) {
    if(!items.length)return empty('Esta sección está por estrenarse','Agrega el primer producto para comenzar.');
    return `<div class="table-wrap" tabindex="0" role="region" aria-label="Productos de ${kind==='comida'?esc(state.document.menu.comida[category].seccion):esc(kind)}"><table><thead><tr><th scope="col">Producto</th><th scope="col">Precio</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead><tbody>${items.map((p,i)=>{
      const src=imageURL(p.img,kind); const available=p.disponible!==false, visible=p.visible!==false;
      return `<tr data-search="${esc((p.nombre+' '+(p.estilo||'')+' '+(p.descripcion||'')).toLowerCase())}"><td><div class="table-item">${src?`<img src="${esc(src)}" alt="" loading="lazy" width="48" height="48">`:`<span class="image-placeholder">${icon('menu')}</span>`}<div><strong>${esc(p.nombre)}</strong><small>${esc(p.estilo||p.detalle||p.descripcion||'')}</small></div></div></td><td class="mono">${kind==='barril'?(p.precios||[]).map(x=>`<div>${money(x.precio)} <small class="muted">${esc(x.medida)}</small></div>`).join(''):money(p.precio)}</td><td><span class="badge ${visible?(available?'green':''):'gray'}">${!visible?'Oculto':available?'Disponible':'Agotado'}</span></td><td>${rowActions(kind,i,category,items.length)}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function renderMenu() {
    const menu=state.document.menu; const tabs=[['barril','Cervezas de barril'],['comida','Cocina'],['latas','Latas'],['sin_alcohol','Sin alcohol'],['vuelo','Vuelo del Cisne']];
    let body='';
    if(state.menuTab==='vuelo'){
      const fields=state.schema.filter(s=>s.key.startsWith('menu.vuelo.'));
      const fallback=[{key:'menu.vuelo.nombre',label:'Nombre',type:'text'},{key:'menu.vuelo.descripcion',label:'Descripción',type:'textarea'},{key:'menu.vuelo.precio_desde',label:'Precio desde (MXN)',type:'number'},{key:'menu.vuelo.nota',label:'Nota para el cliente',type:'textarea'}];
      body=`<section class="card"><h2>Una para cada gusto</h2><p class="section-space">Configura la presentación del vuelo. Las opciones disponibles dependen del barril publicado.</p><div class="fields section-space">${(fields.length?fields:fallback).map(schemaField).join('')}</div></section>`;
    }else if(state.menuTab==='comida'){
      body=(menu.comida||[]).map((c,i)=>`<section><div class="category-head"><div><h2>${esc(c.seccion||c.nombre)}</h2><span class="count">${c.items.length} productos</span></div><div class="button-row"><button class="button small secondary" data-action="new-product" data-kind="comida" data-category="${i}">+ Producto</button><button class="icon-button" data-action="edit-category" data-category="${i}" aria-label="Editar categoría ${esc(c.seccion)}">${icon('edit')}</button><button class="icon-button" data-action="move-category" data-direction="-1" data-category="${i}" ${i===0?'disabled':''} aria-label="Subir categoría">↑</button><button class="icon-button" data-action="move-category" data-direction="1" data-category="${i}" ${i===menu.comida.length-1?'disabled':''} aria-label="Bajar categoría">↓</button><button class="icon-button" data-action="delete-category" data-category="${i}" aria-label="Eliminar categoría">×</button></div></div>${productTable(c.items,'comida',i)}</section>`).join('')||empty('Organiza tu cocina','Crea una categoría, como entradas o platos fuertes, y agrega sus productos.');
    }else body=productTable(menu[state.menuTab]||[],state.menuTab);
    setView(pageHeading('La carta del Cisne','Una misma información para la página, los barriles y el menú QR.',state.menuTab==='comida'?'<button class="button primary" data-action="new-category">+ Categoría</button>':state.menuTab!=='vuelo'?`<button class="button primary" data-action="new-product" data-kind="${state.menuTab}">+ Producto</button>`:'')+`<div class="tabs" aria-label="Tipo de producto">${tabs.map(([id,label])=>`<button data-menu-tab="${id}" aria-pressed="${state.menuTab===id}">${label}</button>`).join('')}</div>${state.menuTab!=='vuelo'?'<div class="toolbar"><label class="sr-only" for="menu-search">Buscar productos</label><input type="search" id="menu-search" placeholder="Buscar en esta sección…"></div>':''}${body}`);
  }
  function newProductID(name) { const base=name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'producto'; const all=[...(state.document.menu.barril||[]),...(state.document.menu.latas||[]),...(state.document.menu.sin_alcohol||[]),...(state.document.menu.comida||[]).flatMap(c=>c.items)]; return all.some(p=>p.id===base)?base+'-'+Date.now().toString(36):base; }
  function priceRow(p={medida:'',precio:''}) { return `<div class="inline-fields" data-price-row><label class="sr-only">Presentación</label><input data-price-name aria-label="Presentación" placeholder="Por ejemplo: 12 oz" value="${esc(p.medida)}" required maxlength="60"><label class="sr-only">Precio en pesos</label><input data-price-amount aria-label="Precio en pesos" type="number" min="0" step="0.01" value="${esc(p.precio)}" required><button type="button" class="icon-button" data-remove-price aria-label="Quitar presentación">×</button></div>`; }
  function productDialog(kind,category,index=null) {
    const list=menuList(kind,category); const original=index==null?null:list[index]; const p=clone(original||{nombre:'',precio:0,visible:true,disponible:true}); const beer=kind==='barril'||kind==='latas'; const dishes=(state.document.menu.comida||[]).flatMap(c=>c.items); let selectedImage=p.img||'';
    const profileOptions=Object.keys(state.document.menu.perfiles||{}).map(v=>({value:v,label:v.charAt(0).toUpperCase()+v.slice(1)}));
    let body=`<div class="fields">${inputField('nombre','Nombre',p.nombre,'text','required maxlength="180"')}${beer?inputField('estilo','Estilo',p.estilo||''):''}${beer?inputField('abv','Alcohol (% ABV)',p.abv??'','number','min="0" max="100" step="0.1"'):''}${beer?`<div class="field"><label for="product-perfil">Perfil</label><select name="perfil" id="product-perfil"><option value="">Sin perfil</option>${optionsHTML(profileOptions,p.perfil)}</select></div>`:''}${beer?inputField('cerveceria','Cervecería',p.cerveceria||''):''}${kind==='latas'?inputField('origen','Origen',p.origen||''):''}${kind==='barril'?inputField('ibu','Amargor (IBU)',p.ibu??'','number','min="0" step="1"'):''}${kind!=='barril'?inputField('precio','Precio (MXN)',p.precio??0,'number','required min="0" step="0.01"'):''}${kind==='comida'?inputField('descripcion','Descripción',p.descripcion||'','textarea'):''}${kind==='sin_alcohol'?inputField('detalle','Presentación / detalle',p.detalle||''):''}${kind==='barril'?inputField('notas','Notas de cata',p.notas||'','textarea')+inputField('historia','Historia del nombre',p.historia||'','textarea'):''}</div><div class="field"><span class="field-label">Fotografía</span><div class="field-media" id="product-photo"><img src="${esc(imageURL(selectedImage,kind)||'/assets/img/marca/favicon-192.png')}" alt="Vista previa del producto" width="70" height="60"><div><button type="button" class="button secondary" id="choose-product-photo">Elegir en MediaHub</button><button type="button" class="button ghost" id="clear-product-photo">Quitar</button></div></div></div>`;
    if(kind==='barril') body+=`<hr class="form-divider"><h3>Presentaciones y precios</h3><p class="field-help">La medida debe ser única. La presentación de 4 oz alimenta el Vuelo del Cisne.</p><div id="price-rows" class="section-space">${(p.precios?.length?p.precios:[{medida:'12 oz',precio:0},{medida:'4 oz',precio:0}]).map(priceRow).join('')}</div><button class="button ghost small" type="button" id="add-price">+ Presentación</button><hr class="form-divider"><h3>Maridajes</h3><div class="choice-list section-space">${dishes.map(d=>`<label class="check"><input type="checkbox" name="marida_con" value="${esc(d.id)}" ${(p.marida_con||[]).includes(d.id)?'checked':''}>${esc(d.nombre)}</label>`).join('')||'<p class="fine">Primero agrega productos de cocina.</p>'}</div><p class="field-help">Selecciona combinaciones recomendadas para esta cerveza.</p><h3 class="section-space">Maridajes oficiales</h3><div class="choice-list section-space">${dishes.map(d=>`<label class="check"><input type="checkbox" name="marida_oficial" value="${esc(d.id)}" ${(p.marida_oficial||[]).includes(d.id)?'checked':''}>${esc(d.nombre)}</label>`).join('')}</div><p class="field-help">Las combinaciones oficiales también se incluyen entre los maridajes recomendados.</p>`;
    body+=`<hr class="form-divider"><div class="button-row"><label class="check"><input type="checkbox" name="visible" ${p.visible!==false?'checked':''}>Visible en la carta</label><label class="check"><input type="checkbox" name="disponible" ${p.disponible!==false?'checked':''}>Disponible para pedir</label></div>`;
    const d=dialog({title:original?'Editar producto':'Un nuevo producto',body,submit:'Guardar en el borrador',onSubmit:async form=>{
      p.nombre=fieldValue(form,'nombre'); if(!p.nombre)throw new Error('Escribe el nombre del producto.');
      ['estilo','cerveceria','origen','descripcion','detalle','notas','historia','perfil'].forEach(k=>{if(form.elements.namedItem(k))p[k]=fieldValue(form,k);});
      ['abv','ibu','precio'].forEach(k=>{if(form.elements.namedItem(k)){const v=fieldValue(form,k);if(v==='')delete p[k];else p[k]=Number(v);}});
      p.visible=form.elements.visible.checked;p.disponible=form.elements.disponible.checked;p.img=selectedImage;
      if(kind==='barril'){
        p.precios=$$('[data-price-row]',form).map(row=>({medida:$('[data-price-name]',row).value.trim(),precio:Number($('[data-price-amount]',row).value)}));
        if(!p.precios.length)throw new Error('Agrega al menos una presentación.');if(new Set(p.precios.map(x=>x.medida.toLowerCase())).size!==p.precios.length)throw new Error('Cada presentación debe tener una medida distinta.');
        p.marida_oficial=$$('input[name=marida_oficial]:checked',form).map(x=>x.value);p.marida_con=[...new Set([...$$('input[name=marida_con]:checked',form).map(x=>x.value),...p.marida_oficial])];
      }
      if(!p.id)p.id=newProductID(p.nombre);if(original)list[index]=p;else list.push(p);changed();renderMenu();toast('Producto actualizado en el borrador.');
    }});
    $('#choose-product-photo',d.el).addEventListener('click',async()=>{const item=await mediaPicker('image');if(item){selectedImage=item.url;$('#product-photo img',d.el).src=item.url;d.form.dispatchEvent(new Event('input'));}});
    $('#clear-product-photo',d.el).addEventListener('click',()=>{selectedImage='';$('#product-photo img',d.el).src='/assets/img/marca/favicon-192.png';d.form.dispatchEvent(new Event('input'));});
    if(kind==='barril'){
      $('#add-price',d.el).addEventListener('click',()=>{$('#price-rows',d.el).insertAdjacentHTML('beforeend',priceRow());d.form.dispatchEvent(new Event('input'));});
      $('#price-rows',d.el).addEventListener('click',e=>{if(e.target.closest('[data-remove-price]')){e.target.closest('[data-price-row]').remove();d.form.dispatchEvent(new Event('input'));}});
    }
  }
  function categoryDialog(index=null) { const current=index==null?null:state.document.menu.comida[index]; dialog({title:current?'Editar categoría':'Nueva categoría',body:inputField('name','Nombre de la categoría',current?.seccion||'','text','required maxlength="100"'),submit:'Guardar en el borrador',onSubmit:async form=>{const name=fieldValue(form,'name');if(!name)throw new Error('Escribe un nombre.');if(current)current.seccion=name;else(state.document.menu.comida ||= []).push({id:uid('categoria'),seccion:name,items:[]});changed();renderMenu();}}); }
  function removePairings(ids) { (state.document.menu.barril||[]).forEach(b=>['marida_con','marida_oficial'].forEach(k=>{if(Array.isArray(b[k]))b[k]=b[k].filter(id=>!ids.includes(id));})); }
  function moveItem(list,index,direction) { const next=index+direction;if(next<0||next>=list.length)return;[list[index],list[next]]=[list[next],list[index]];changed(); }
  function renderEvents() {
    const isEvents=state.contentTab==='events';const items=state.document[state.contentTab]||[];
    setView(pageHeading('Momentos para volver','Administra las experiencias y fotografías que se muestran en la página.',`<button class="button primary" data-action="new-content">+ ${isEvents?'Evento':'Fotografía'}</button>`)+`<div class="tabs" aria-label="Contenido"><button data-content-tab="events" aria-pressed="${isEvents}">Eventos</button><button data-content-tab="gallery" aria-pressed="${!isEvents}">Galería</button></div>`+(items.length?`<div class="event-grid">${items.map((item,i)=>`<article class="card event-card ${isEvents?'':'gallery-card'}">${imageURL(item.image)?`<img src="${esc(imageURL(item.image))}" alt="${esc(item.alt||'')}" loading="lazy">`:''}<div>${isEvents?`<span class="badge ${item.visible===false?'gray':'green'}">${item.visible===false?'Oculto':item.date?esc(date(item.date)):'Sin fecha'}</span>`:''}<h3>${esc(isEvents?item.title:item.caption||item.alt||'Fotografía de galería')}</h3><p>${esc(isEvents?item.description:item.alt||'Sin descripción alternativa')}</p><div class="button-row"><button class="button secondary small" data-action="edit-content" data-index="${i}">Editar</button><button class="icon-button" data-action="move-content" data-index="${i}" data-direction="-1" ${i===0?'disabled':''} aria-label="Mover antes">↑</button><button class="icon-button" data-action="move-content" data-index="${i}" data-direction="1" ${i===items.length-1?'disabled':''} aria-label="Mover después">↓</button><button class="icon-button" data-action="delete-content" data-index="${i}" aria-label="Eliminar ${isEvents?'evento':'fotografía'}">×</button></div></div></article>`).join('')}</div>`:empty(isEvents?'El próximo encuentro empieza aquí':'Las historias también se ven',isEvents?'Agrega una fecha, una imagen y lo que hará especial la experiencia.':'Elige fotografías del MediaHub para compartir la vida de la cervecería.')));
  }
  function contentDialog(index=null) {
    const type=state.contentTab,isEvents=type==='events',list=state.document[type] ||= [];const current=index==null?null:list[index];const item=clone(current||{id:uid(isEvents?'evento':'foto'),visible:true});let selected=item.image||'';
    const body=`<div class="fields">${isEvents?inputField('title','Nombre del evento',item.title||'','text','required maxlength="180"')+inputField('date','Fecha',item.date?item.date.slice(0,16):'','datetime-local')+inputField('description','Descripción',item.description||'','textarea')+inputField('url','Enlace del evento',item.url||'','url','placeholder="https://…"'):inputField('caption','Pie de foto',item.caption||'','textarea')}${inputField('alt','Descripción alternativa de la imagen',item.alt||'','text','maxlength="300"')}</div><div class="field"><span class="field-label">Imagen</span><div class="field-media"><img id="content-image" src="${esc(imageURL(selected)||'/assets/img/marca/favicon-192.png')}" alt="Vista previa de imagen"><button type="button" class="button secondary" id="choose-content-image">Elegir en MediaHub</button></div></div>${isEvents?`<label class="check"><input type="checkbox" name="visible" ${item.visible!==false?'checked':''}>Mostrar en la página</label>`:''}`;
    const d=dialog({title:current?(isEvents?'Editar evento':'Editar fotografía'):(isEvents?'Nuevo evento':'Agregar a la galería'),body,submit:'Guardar en el borrador',onSubmit:async form=>{
      ['title','date','description','url','caption','alt'].forEach(k=>{if(form.elements.namedItem(k))item[k]=fieldValue(form,k);});
      if(!selected)throw new Error('Selecciona una imagen del MediaHub.'); item.image=selected;if(isEvents)item.visible=form.elements.visible.checked;if(current)list[index]=item;else list.push(item);changed();renderEvents();
    }});
    $('#choose-content-image',d.el).addEventListener('click',async()=>{const media=await mediaPicker('image');if(media){selected=media.url;$('#content-image',d.el).src=media.url;if(!fieldValue(d.form,'alt'))d.form.elements.alt.value=media.alt||'';d.form.dispatchEvent(new Event('input'));}});
  }
  const mediaStatus = item => item.status==='processing'?'Procesando':item.status==='error'?'Error al procesar':item.archived?'Archivado':'Listo';
  function categoryOptions(categories,value='') { return `<option value="">Todas las categorías</option>`+(categories||[]).map(c=>{const v=typeof c==='string'?c:c.category||c.name||c.value;return `<option value="${esc(v)}" ${v===value?'selected':''}>${esc(v)}${typeof c==='object'&&c.count!=null?' ('+Number(c.count)+')':''}</option>`;}).join(''); }
  async function getMedia(filters) {
    const params=new URLSearchParams();Object.entries(filters).forEach(([k,v])=>{if(v!==''&&v!=null)params.set(k,String(v));});const data=await api('/media?'+params);(data.items||[]).forEach(item=>state.mediaCache.set(String(item.id),item));return data;
  }
  function mediaCards(items,picker=false) {
    return items.length?`<div class="media-grid">${items.map(item=>{
      const ready=(!item.status||item.status==='ready')&&!item.archived;const src=safeURL(item.thumbnail|| (item.kind==='image'?item.url:''));
      return `<article class="media-card"><button type="button" ${picker?'data-select-media':'data-media-edit'}="${esc(item.id)}" ${picker&&!ready?'disabled':''} aria-label="${picker?'Seleccionar':'Editar'} ${esc(item.title||item.name)}"><div class="media-visual">${src?`<img src="${esc(src)}" alt="" loading="lazy" width="320" height="240">`:icon(item.kind==='video'?'video':'media')}<span class="badge ${item.status==='error'?'danger':item.status==='processing'?'':item.kind==='video'?'':'gray'}">${item.status==='processing'||item.status==='error'?mediaStatus(item):item.kind==='video'?'Video':'Imagen'}</span></div><div class="media-card-info"><strong>${esc(item.title||item.name)}</strong><small>${esc(item.category||'Sin clasificar')} · ${bytes(item.size)}</small><small>${item.width&&item.height?`${Number(item.width)} × ${Number(item.height)} · `:''}${esc(item.archived?'Archivado':item.source||'Archivo del equipo')}</small></div></button></article>`;
    }).join('')}</div>`:empty('Todavía no hay archivos aquí','Prueba otra búsqueda o sube material de la cervecería.');
  }
  function pager(data,scope='media') { const page=Number(data.page)||1,pages=Number(data.pages)||1;return `<div class="pagination"><span>${Number(data.total)||0} archivos · Página ${page} de ${Math.max(pages,1)}</span><div class="button-row"><button type="button" class="button ghost small" data-${scope}-page="${page-1}" ${page<=1?'disabled':''}>← Anterior</button><button type="button" class="button ghost small" data-${scope}-page="${page+1}" ${page>=pages?'disabled':''}>Siguiente →</button></div></div>`; }
  let mediaRequest=0, mediaTimer=null;
  function renderUploadQueue() {
    const target=$('#upload-progress');if(!target)return;
    target.innerHTML=state.uploads.length?`<div class="upload-progress" aria-live="polite">${state.uploads.map((u,i)=>`<div class="upload-item"><span>${esc(u.file.name)}</span><span class="${u.status==='error'?'form-error':'fine'}">${esc(u.status==='queued'?'En cola':u.status==='uploading'?'Subiendo…':u.status==='done'?u.message||'Recibido':u.error||'Error')}</span>${u.status==='error'?`<button class="button small ghost" data-retry-upload="${i}">Reintentar</button>`:''}</div>`).join('')}</div>`:'';
  }
  function renderMedia() {
    setView(pageHeading('MediaHub','La cerveza, la cocina y quienes le dan vida al Cisne. Todo tu material en un solo lugar.')+`<div class="upload-zone" id="upload-zone">${icon('upload')}<div><h3>De tu cámara a la historia del Cisne</h3><p>Arrastra fotos o videos. También puedes elegir varios archivos desde tu equipo.</p></div><label class="button primary" for="media-upload">Subir archivos</label><input class="sr-only" id="media-upload" type="file" multiple accept="image/jpeg,image/png,image/webp,image/heic,image/heif,video/mp4,.heic,.heif"></div><div id="upload-progress"></div><div class="toolbar"><label class="sr-only" for="media-search">Buscar archivos</label><input type="search" id="media-search" placeholder="Buscar por nombre, etiquetas o descripción…" value="${esc(state.media.q)}"><label class="sr-only" for="media-category">Categoría</label><select id="media-category">${categoryOptions([],state.media.category)}</select><label class="sr-only" for="media-kind">Tipo de archivo</label><select id="media-kind"><option value="">Fotos y videos</option value="image" ${state.media.kind==='image'?'selected':''}>Imágenes</option><option value="video" ${state.media.kind==='video'?'selected':''}>Videos</option></select><label class="check"><input type="checkbox" id="media-archived" ${state.media.archived?'checked':''}>Archivados</label></div><div id="media-results"><div class="loading-screen"><span class="spinner" aria-hidden="true"></span><p>Buscando en la biblioteca…</p></div></div>`);
    renderUploadQueue();const zone=$('#upload-zone');['dragenter','dragover'].forEach(name=>zone.addEventListener(name,e=>{e.preventDefault();zone.classList.add('dragover');}));['dragleave','drop'].forEach(name=>zone.addEventListener(name,e=>{e.preventDefault();zone.classList.remove('dragover');}));zone.addEventListener('drop',e=>startUploadDialog(Array.from(e.dataTransfer.files)));
    $('#media-upload').addEventListener('change',e=>{startUploadDialog(Array.from(e.target.files));e.target.value='';});
    $('#media-search').addEventListener('input',e=>{state.media.q=e.target.value;state.media.page=1;clearTimeout(mediaTimer);mediaTimer=setTimeout(loadMediaGrid,300);});
    ['category','kind','archived'].forEach(k=>$('#media-'+k).addEventListener('change',e=>{state.media[k]=k==='archived'?e.target.checked:e.target.value;state.media.page=1;loadMediaGrid();}));
    return loadMediaGrid();
  }
  async function loadMediaGrid() {
    if(state.route!=='media')return;const request=++mediaRequest;
    try { const data=await getMedia(state.media);if(request!==mediaRequest||state.route!=='media'||!$('#media-results'))return;
      $('#media-results').innerHTML=mediaCards(data.items||[])+pager(data);$('#media-category').innerHTML=categoryOptions(data.categories,state.media.category);
      if((data.items||[]).some(i=>i.status==='processing')){clearTimeout(mediaTimer);mediaTimer=setTimeout(loadMediaGrid,6000);}
    } catch(e){if(request===mediaRequest&&$('#media-results'))$('#media-results').innerHTML=empty('La biblioteca no pudo cargar',e.message)+'<button class="button secondary section-space" data-action="reload-media">Volver a intentar</button>';}
  }
  function startUploadDialog(files) {
    if(!files.length)return;
    dialog({title:files.length===1?'Subir un archivo':`Subir ${files.length} archivos`,body:`<p class="muted">Los archivos se validan antes de poder seleccionarlos. Los videos pueden tardar en estar listos.</p><ul class="list section-space">${files.map(f=>`<li><strong>${esc(f.name)}</strong><small>${bytes(f.size)}</small></li>`).join('')}</ul><div class="fields section-space">${inputField('category','Categoría','sin-clasificar','text','maxlength="100" list="upload-categories"')}${inputField('tags','Etiquetas, separadas por comas','','text','maxlength="400"')}</div><datalist id="upload-categories">${['Cervezas','Cocina','Barra y lugar','Elaboración','Comunidad','Eventos','Marca'].map(v=>`<option value="${v}"></option>`).join('')}</datalist>`,submit:'Subir a MediaHub',onSubmit:async form=>{
      const metadata={category:fieldValue(form,'category')||'sin-clasificar',tags:fieldValue(form,'tags').split(',').map(s=>s.trim()).filter(Boolean),source:'equipo'};
      state.uploads.push(...files.map(file=>({file,metadata:clone(metadata),status:'queued'})));runUploads();
    }});
  }
  async function runUploads() {
    if(state.uploading)return;state.uploading=true;const epoch=state.uploadEpoch;
    try { for(const job of state.uploads){if(epoch!==state.uploadEpoch)break;if(job.status!=='queued')continue;job.status='uploading';renderUploadQueue();const fd=new FormData();fd.append('file',job.file);fd.append('metadata',JSON.stringify(job.metadata));
      try {state.uploadController=new AbortController();const result=await api('/media',{method:'POST',body:fd,signal:state.uploadController.signal});if(epoch!==state.uploadEpoch)break;const item=result.item||result.media||result;job.status='done';job.message=result.duplicate?'Ya existía en la biblioteca':item.status==='processing'?'Recibido · procesando':'Recibido';if(item.id)state.mediaCache.set(String(item.id),item);}
      catch(e){if(epoch!==state.uploadEpoch)break;job.status='error';job.error=e.message;}renderUploadQueue();
    }} finally{state.uploading=false;state.uploadController=null;if(epoch!==state.uploadEpoch)return;if(state.route==='media')await loadMediaGrid();toast(state.uploads.some(u=>u.status==='error')?'Hay archivos que necesitan un reintento.':'Carga completada. Revisa los archivos en la biblioteca.',state.uploads.some(u=>u.status==='error'));}
  }
  function mediaPicker(kind='image') {
    return new Promise(resolve=>{
      let selected=false,filters={kind,page:1,q:'',category:'',archived:false},request=0,timer=null,pollTimer=null;
      const d=dialog({title:kind==='video'?'Elegir un video':'Elegir una imagen',width:true,submit:null,body:`<p class="muted">Selecciona un archivo listo de tu biblioteca.</p><div class="toolbar section-space"><label class="sr-only" for="picker-search">Buscar en la biblioteca</label><input id="picker-search" type="search" placeholder="Buscar por nombre o etiquetas…"><label class="sr-only" for="picker-category">Categoría</label><select id="picker-category"><option value="">Todas las categorías</option></select></div><div id="picker-results"><p class="muted">Cargando archivos…</p></div>`});
      const load=async()=>{clearTimeout(pollTimer);const id=++request;try{const data=await getMedia(filters);if(id!==request||!d.el.isConnected)return;$('#picker-results',d.el).innerHTML=mediaCards(data.items||[],true)+pager(data,'picker');$('#picker-category',d.el).innerHTML=categoryOptions(data.categories,filters.category);if((data.items||[]).some(item=>item.status==='processing'))pollTimer=setTimeout(load,6000);}catch(e){if(d.el.isConnected)$('#picker-results',d.el).innerHTML=empty('No pudimos cargar los archivos',e.message)+'<button type="button" class="button secondary" data-picker-retry>Reintentar</button>';}};
      d.el.addEventListener('close',()=>{request++;clearTimeout(timer);clearTimeout(pollTimer);if(!selected)resolve(null);});
      $('#picker-search',d.el).addEventListener('input',e=>{filters.q=e.target.value;filters.page=1;clearTimeout(timer);timer=setTimeout(load,300);});
      $('#picker-category',d.el).addEventListener('change',e=>{filters.category=e.target.value;filters.page=1;load();});
      d.el.addEventListener('click',e=>{const pick=e.target.closest('[data-select-media]');if(pick){const item=state.mediaCache.get(String(pick.dataset.selectMedia));if(item&&(!item.status||item.status==='ready')&&!item.archived){selected=true;resolve(item);d.close(true);}}const page=e.target.closest('[data-picker-page]');if(page){filters.page=Number(page.dataset.pickerPage);load();}if(e.target.closest('[data-picker-retry]'))load();});load();
    });
  }
  async function mediaDetail(id) {
    const item=state.mediaCache.get(String(id));if(!item)return;
    const url=safeURL(item.url),preview=safeURL(item.thumbnail||item.url);
    const d=dialog({title:item.title||item.name||'Detalle del archivo',width:true,body:`<div class="media-detail"><div class="media-detail-preview">${item.kind==='video'?`<video src="${esc(url)}" ${safeURL(item.thumbnail)?`poster="${esc(item.thumbnail)}"`:''} controls playsinline preload="metadata"></video>`:`<img src="${esc(preview)}" alt="${esc(item.alt||item.title||'Imagen seleccionada')}">`}<p class="fine">${esc(item.name)} · ${bytes(item.size)}${item.width?' · '+Number(item.width)+' × '+Number(item.height):''}</p><p class="section-space"><span class="badge ${item.status==='error'?'danger':'gray'}">${mediaStatus(item)}</span></p>${item.error?`<p class="form-error">${esc(item.error)}</p>`:''}<div class="section-space"><h3>Dónde se utiliza</h3><div id="media-uses"><p class="fine">Consultando referencias…</p></div></div><div class="danger-zone"><button class="button ${item.archived?'secondary':'danger'} small" type="button" id="archive-media">${item.archived?'Recuperar archivo':'Archivar archivo'}</button><p class="field-help">Archivar lo retira del selector. Las publicaciones existentes conservan sus referencias.</p></div></div><div>${inputField('title','Título',item.title||item.name,'text','maxlength="180"')}${inputField('alt','Texto alternativo',item.alt||'','text','maxlength="400"')}${inputField('caption','Descripción',item.caption||'','textarea','maxlength="3000"')}${inputField('category','Categoría',item.category||'sin-clasificar','text','maxlength="100"')}${inputField('tags','Etiquetas, separadas por comas',Array.isArray(item.tags)?item.tags.join(', '):item.tags||'')}${inputField('source','Origen',item.source||'')}${inputField('source_url','Enlace de origen',item.source_url||'','url')}${inputField('date','Fecha conocida',item.date?item.date.slice(0,10):'','date')}</div></div>`,submit:'Guardar información',onSubmit:async form=>{
      const metadata={};['title','alt','caption','category','source','source_url','date'].forEach(k=>metadata[k]=fieldValue(form,k));metadata.tags=fieldValue(form,'tags').split(',').map(v=>v.trim()).filter(Boolean);
      const patch={};Object.entries(metadata).forEach(([key,value])=>{const before=key==='tags'?(Array.isArray(item.tags)?item.tags:String(item.tags||'').split(',').map(x=>x.trim()).filter(Boolean)):key==='date'?(item.date||'').slice(0,10):item[key]||'';if(json(before)!==json(value))patch[key]=value;});if(Object.keys(patch).length)await api('/media/'+encodeURIComponent(id),{method:'PATCH',body:patch});toast('Información del archivo guardada.');if(state.route==='media')await loadMediaGrid();
    }});
    api('/media/'+encodeURIComponent(id)+'/usage').then(data=>{if(!d.el.isConnected)return;const uses=data.uses||[];$('#media-uses',d.el).innerHTML=uses.length?`<ul class="usage-list">${uses.map(u=>`<li>${esc(typeof u==='string'?u:u.label||u.path||u.key||u.title||'Contenido publicado')}</li>`).join('')}</ul>`:'<p class="fine">Sin referencias registradas.</p>';}).catch(e=>{if(d.el.isConnected)$('#media-uses',d.el).textContent=e.message;});
    $('#archive-media',d.el).addEventListener('click',async e=>{if(!confirm(item.archived?'¿Recuperar este archivo para poder seleccionarlo? Los cambios de información sin guardar se descartarán.':'¿Archivar este archivo? Dejará de aparecer en el selector. Los cambios de información sin guardar se descartarán.'))return;e.currentTarget.disabled=true;try{await api('/media/'+encodeURIComponent(id)+'/archive',{method:'POST',body:{archived:!item.archived}});d.close(true);toast(item.archived?'Archivo recuperado.':'Archivo archivado.');if(state.route==='media')await loadMediaGrid();}catch(error){toast(error.message,true);if(d.el.isConnected)$('#archive-media',d.el).disabled=false;}});
  }
  async function renderRevisions() {
    const token=state.viewToken;setView(pageHeading('Publicaciones','Cada publicación cuenta una versión de la historia. El Pasaporte conserva su operación independiente.')+'<div class="loading-screen"><span class="spinner" aria-hidden="true"></span><p>Buscando versiones…</p></div>');
    const data=await api('/revisions');if(token!==state.viewToken)return;
    const changes=diff(state.publicBaseline,state.document);
    setView(pageHeading('Publicaciones','Revisa tus cambios y el historial de contenido. Restaurar prepara un borrador; no publica ni modifica socios o canjes.',owner()?'<button class="button primary" data-action="publish">Publicar versión</button>':'')+`<section class="card"><div class="card-head"><h2>Cambios por publicar</h2><span class="badge ${changes.length?'':'green'}">${changes.length} cambios frente a la web</span></div>${diffHTML(changes)}<p class="field-help section-space">Comparación entre la versión publicada y el borrador, incluidos tus cambios sin guardar.</p></section><section class="card section-space"><div class="card-head"><h2>Historial de versiones</h2><span class="count">${(data.items||[]).length} registros</span></div>${data.items?.length?`<ol class="timeline-list">${data.items.map(r=>`<li class="revision"><span class="avatar">${esc(r.id)}</span><div><strong>${esc(r.note||'Publicación de contenido')} ${r.current?'<span class="badge green">Actual</span>':''}</strong><p>${esc(date(r.created_at))} · ${esc(typeof r.author==='object'?r.author.name:r.author||'Equipo Cisne')}</p></div>${owner()?`<button class="button ghost small" data-restore="${esc(r.id)}">Restaurar borrador</button>`:''}</li>`).join('')}</ol>`:empty('La primera publicación está por venir','Las versiones aparecerán aquí después de publicar contenido.')}</section><section id="activity-card" class="card section-space" hidden><div class="card-head"><h2>Actividad del equipo</h2></div><ul class="list" id="activity-list"></ul></section>`);
    if(owner())api('/activity').then(a=>{if(token!==state.viewToken||!$('#activity-list'))return;$('#activity-card').hidden=false;$('#activity-list').innerHTML=(a.items||[]).slice(0,30).map(i=>`<li><strong>${esc(i.action)}</strong><small>${esc(typeof i.actor==='object'?i.actor.name:i.actor||'Equipo')} · ${esc(date(i.created_at))}</small></li>`).join('')||'<li class="muted">Sin actividad registrada.</li>';}).catch(e=>toast('No se pudo cargar la actividad: '+e.message,true));
  }
  async function restoreRevision(id) {
    if(!owner()||state.busy)return;if(!confirm('Esta versión sustituirá el borrador actual'+(state.dirty?' y los cambios sin guardar':'')+'. La web publicada y los movimientos del Pasaporte no cambiarán. ¿Continuar?'))return;
    state.busy=true;$('#app').inert=true;status();let restored=false;try{await api('/restore',{method:'POST',body:{id,version:state.version}});restored=true;await loadState();toast('Versión recuperada como borrador. Revísala antes de publicar.');}catch(e){if(restored)message('La versión se restauró en el servidor. Recarga el borrador para continuar con ella.',true);throw e;}finally{state.busy=false;$('#app').inert=false;status();}
  }
  async function renderUsers() {
    if(!owner()){location.hash='inicio';return;}const token=state.viewToken;setView(pageHeading('El equipo del Cisne','Accesos individuales y permisos adecuados para cada persona.')+'<div class="loading-screen"><span class="spinner" aria-hidden="true"></span></div>');
    const data=await api('/users');if(token!==state.viewToken)return;state.users=data.items||[];
    setView(pageHeading('El equipo del Cisne','Los editores administran contenido. La publicación y la operación del Pasaporte corresponden al propietario.','<button class="button primary" data-action="new-user">+ Invitar al equipo</button>')+`<div class="table-wrap" tabindex="0" role="region" aria-label="Cuentas del equipo"><table><thead><tr><th scope="col">Persona</th><th scope="col">Permiso</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead><tbody>${state.users.map((u,i)=>`<tr><td><div class="table-item"><span class="avatar">${esc((u.name||u.username).slice(0,2).toUpperCase())}</span><div><strong>${esc(u.name||u.username)}</strong><small>${esc(u.username)}</small></div></div></td><td>${u.role==='owner'?'Propietario':'Editor'}</td><td><span class="badge ${(u.active===false||u.active===0)?'gray':'green'}">${(u.active===false||u.active===0)?'Desactivada':'Activa'}</span></td><td><button class="button secondary small" data-edit-user="${i}">Editar acceso</button></td></tr>`).join('')}</tbody></table></div>`);
  }
  function userDialog(index=null) {
    if(!owner())return;const user=index==null?null:state.users[index];
    dialog({title:user?'Editar acceso':'Una persona más en el equipo',body:`<div class="fields">${inputField('name','Nombre',user?.name||'','text','required maxlength="100"')}${inputField('username','Usuario',user?.username||'','text',`required autocomplete="off" autocapitalize="none" maxlength="80" ${user?'readonly':''}`)}<div class="field"><label for="user-role-select">Permiso</label><select id="user-role-select" name="role">${optionsHTML([{value:'editor',label:'Editor · contenido y biblioteca'},{value:'owner',label:'Propietario · publicación y Pasaporte'}],user?.role||'editor')}</select></div>${inputField('password',user?'Nueva contraseña (opcional)':'Contraseña inicial','','password',`${user?'':'required'} minlength="12" autocomplete="new-password"`)}${user?`<label class="check"><input name="active" type="checkbox" ${user.active!==false&&user.active!==0?'checked':''}>Cuenta activa</label>`:''}</div><p class="field-help">Usa al menos 12 caracteres. ${user?'Deja la contraseña vacía para conservar la actual. Desactivar una cuenta revoca sus sesiones.':'Comparte el acceso por el canal acordado con esa persona.'}</p>`,submit:user?'Guardar permisos':'Crear cuenta',onSubmit:async form=>{
      const body={name:fieldValue(form,'name'),role:fieldValue(form,'role')};const password=form.elements.password.value;if(password)body.password=password;
      if(user)body.active=form.elements.active.checked;else body.username=fieldValue(form,'username');
      await api(user?'/users/'+encodeURIComponent(user.id):'/users',{method:user?'PATCH':'POST',body});toast(user?'Permisos actualizados.':'Cuenta creada.');if(user?.id===state.user.id){state.interrupted={user:state.user.id,document:clone(state.document),baseline:clone(state.baseline),version:state.version,dirty:state.dirty};await loadState(true);}else await renderUsers();
    }});
  }
  function closeSidebar() { $('#sidebar').classList.remove('open'); $('#sidebar-backdrop').hidden=true; $('#menu-toggle').setAttribute('aria-expanded','false'); }
  $('#menu-toggle').addEventListener('click',()=>{const open=!$('#sidebar').classList.contains('open');$('#sidebar').classList.toggle('open',open);$('#sidebar-backdrop').hidden=!open;$('#menu-toggle').setAttribute('aria-expanded',String(open));if(open)$('.nav-item',$('#sidebar'))?.focus();});
  $('#sidebar-backdrop').addEventListener('click',closeSidebar);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#sidebar').classList.contains('open')){closeSidebar();$('#menu-toggle').focus();}});
  $('#login-form').addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget,b=$('[type=submit]',form);if(!form.reportValidity())return;b.disabled=true;$('#login-error').hidden=true;
    try{const data=await api('/login',{method:'POST',body:{username:form.elements.username.value.trim(),password:form.elements.password.value}});state.user=data.user;state.csrf=data.csrf;form.elements.password.value='';
      if(new URLSearchParams(location.search).get('next')==='/admin/'&&owner()){location.assign('/admin/');return;}await loadState(true);
    }catch(error){$('#login-error').textContent=error.message;$('#login-error').hidden=false;}finally{b.disabled=false;}
  });
  $('#logout').addEventListener('click',async()=>{
    if(state.agentBusy)return;
    if((state.dirty||state.uploading)&&!confirm('Hay cambios sin guardar o archivos en carga. ¿Cerrar sesión de todos modos?'))return;
    stopUploads();try{await api('/logout',{method:'POST',body:{}});state.user=null;state.csrf='';state.document=null;state.baseline=null;state.interrupted=null;state.dirty=false;state.uploads=[];state.mediaCache.clear();showLogin();}catch(e){toast(e.message,true);}
  });
  $('#save-draft').addEventListener('click',()=>saveDraft().catch(e=>toast(e.message,true)));
  $('#publish').addEventListener('click',publishDialog);
  document.addEventListener('input',e=>{
    const input=e.target.closest('[data-doc-path]');if(input){
      const type=input.dataset.type;let value=type==='boolean'?input.checked:type==='number'?(input.value===''?null:Number(input.value)):type==='multiselect'?Array.from(input.selectedOptions).map(o=>o.value):input.value;
      setPath(state.document,input.dataset.docPath,value);changed();
    }
    if(e.target.id==='menu-search'){$$('[data-search]',$('#workspace')).forEach(row=>row.hidden=!row.dataset.search.includes(e.target.value.toLowerCase().trim()));}
  });
  document.addEventListener('change',e=>{
    const input=e.target.closest('[data-doc-path]');if(input&&(input.tagName==='SELECT'||input.type==='checkbox'))input.dispatchEvent(new Event('input',{bubbles:true}));
  });
  document.addEventListener('click',async e=>{
    const button=e.target.closest('button');if(!button||button.disabled)return;
    try{
      if(button.dataset.menuTab){state.menuTab=button.dataset.menuTab;renderMenu();return;}
      if(button.dataset.contentTab){state.contentTab=button.dataset.contentTab;renderEvents();return;}
      if(button.dataset.pickPath){const key=button.dataset.pickPath;const item=await mediaPicker(button.dataset.kind||'image');if(item){setPath(state.document,key,item.url);changed();if(state.route==='editor')renderEditor();else if(state.route==='negocio')renderBusiness();else if(state.route==='menu')renderMenu();}return;}
      if(button.dataset.clearPath){setPath(state.document,button.dataset.clearPath,'');changed();if(state.route==='editor')renderEditor();else if(state.route==='negocio')renderBusiness();else renderMenu();return;}
      if(button.dataset.previewSize){$('#preview-wrap').classList.toggle('mobile',button.dataset.previewSize==='mobile');$$('[data-preview-size]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));return;}
      if(button.dataset.mediaEdit){await mediaDetail(button.dataset.mediaEdit);return;}
      if(button.dataset.mediaPage){state.media.page=Number(button.dataset.mediaPage);await loadMediaGrid();return;}
      if(button.dataset.retryUpload!=null){const job=state.uploads[Number(button.dataset.retryUpload)];if(job){job.status='queued';runUploads();}return;}
      if(button.dataset.restore){await restoreRevision(button.dataset.restore);return;}
      if(button.dataset.editUser!=null){userDialog(Number(button.dataset.editUser));return;}
      const action=button.dataset.action;if(!action)return;
      const kind=button.dataset.kind,index=Number(button.dataset.index),category=button.dataset.category;
      if(action==='retry-view')await route();
      else if(action==='refresh-preview'){if(state.dirty)toast('Guarda el borrador para ver tus últimos cambios.');refreshPreview();}
      else if(action==='publish')await publishDialog();
      else if(action==='new-product')productDialog(kind,category);
      else if(action==='edit-product')productDialog(kind,category,index);
      else if(action==='move-product'){moveItem(menuList(kind,category),index,Number(button.dataset.direction));renderMenu();}
      else if(action==='delete-product'){
        const list=menuList(kind,category),item=list[index];if(!confirm(`¿Eliminar «${item.nombre}» del borrador?${kind==='comida'?' También se quitará de los maridajes.':''}`))return;
        if(kind==='comida')removePairings([item.id]);list.splice(index,1);changed();renderMenu();
      }
      else if(action==='new-category')categoryDialog();
      else if(action==='edit-category')categoryDialog(Number(category));
      else if(action==='move-category'){moveItem(state.document.menu.comida,Number(category),Number(button.dataset.direction));renderMenu();}
      else if(action==='delete-category'){
        const list=state.document.menu.comida,item=list[Number(category)];if(!confirm(`¿Eliminar la categoría «${item.seccion}» y sus ${item.items.length} productos del borrador? Sus maridajes también se actualizarán.`))return;
        removePairings(item.items.map(p=>p.id));list.splice(Number(category),1);changed();renderMenu();
      }
      else if(action==='new-content')contentDialog();
      else if(action==='edit-content')contentDialog(index);
      else if(action==='move-content'){moveItem(state.document[state.contentTab],index,Number(button.dataset.direction));renderEvents();}
      else if(action==='delete-content'){if(confirm('¿Retirar este elemento del borrador? El archivo original permanece en MediaHub.')){state.document[state.contentTab].splice(index,1);changed();renderEvents();}}
      else if(action==='reload-media')await loadMediaGrid();
      else if(action==='new-user')userDialog();
    }catch(error){toast(error.message,true);}
  });
  window.addEventListener('message',async event=>{
    const frame=$('#preview-frame');if(!frame||event.source!==frame.contentWindow||event.origin!==location.origin||event.data?.type!=='cms-select'||typeof event.data.key!=='string')return;
    const key=event.data.key;if(!state.schema.some(s=>s.key===key))return;
    if(key.startsWith('page.')){
      const field=$('[data-field-key="'+CSS.escape(key)+'"]');if(field){$$('.field.is-focused').forEach(f=>f.classList.remove('is-focused'));field.classList.add('is-focused');const section=field.closest('details');if(section)section.open=true;field.scrollIntoView({behavior:'smooth',block:'center'});$('input,textarea,select,button',field)?.focus({preventScroll:true});}return;
    }
    if(key.startsWith('menu.negocio.')){location.hash='negocio';await route();}
    else if(key.startsWith('menu.vuelo.')){state.menuTab='vuelo';location.hash='menu';await route();}
    else {
      let match=key.match(/^menu\.(barril|latas|sin_alcohol)\.(\d+)\./);if(match){state.menuTab=match[1];location.hash='menu';await route();productDialog(match[1],null,Number(match[2]));return;}
      match=key.match(/^menu\.comida\.(\d+)\.items\.(\d+)\./);if(match){state.menuTab='comida';location.hash='menu';await route();productDialog('comida',Number(match[1]),Number(match[2]));return;}
      match=key.match(/^(events|gallery)\.(\d+)\./);if(match){state.contentTab=match[1];location.hash='eventos';await route();contentDialog(Number(match[2]));return;}
    }
    const field=$('[data-field-key="'+CSS.escape(key)+'"]');if(field){field.scrollIntoView({behavior:'smooth',block:'center'});$('input,textarea,select,button',field)?.focus({preventScroll:true});}
  });
  window.addEventListener('hashchange',route);
  window.addEventListener('beforeunload',e=>{if(state.dirty||state.uploading||state.agentBusy||$('dialog[open][data-edited=true]')){e.preventDefault();e.returnValue='';}});
  async function boot(){try{const data=await api('/session');state.user=data.user;state.csrf=data.csrf;if(new URLSearchParams(location.search).get('next')==='/admin/'&&owner()){location.assign('/admin/');return;}await loadState();}catch(e){if(e.status===401)showLogin();else{$('#boot').innerHTML='<p>No pudimos abrir el panel.</p><p class="muted" id="boot-error"></p><button class="button primary" id="boot-retry">Volver a intentar</button>';$('#boot-error').textContent=e.message;$('#boot-retry').addEventListener('click',boot);}}}
  boot();
})();
