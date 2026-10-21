/* Agente Cisne · conversación en memoria; autorización y edición residen en el servidor. */
(function () {
  'use strict';
  let host = null, bridge = null, epoch = 0, pollTimer = null;
  const fresh = () => ({config:null, loading:false, configError:'', messages:[], history:[], label:null, input:'', selection:'', busy:false, error:'', jobsLoaded:false, loadingJobs:false, jobs:new Map()});
  let state = fresh();
  const ready = item => item?.kind === 'image' && (!item.status || item.status === 'ready') && !item.archived;
  const mediaURL = value => /^\/(?:cms\/media\/|assets\/)[^\s\\]*$/.test(String(value || '')) ? value : '';
  const el = (tag, className = '', text = '') => { const node=document.createElement(tag); node.className=className; if(text)node.textContent=text; return node; };
  const button = (text, fn, className='button secondary small', disabled=false) => {
    const node=el('button',className,text); node.type='button'; node.disabled=disabled; node.addEventListener('click',fn); return node;
  };
  const link = (text, href) => { const node=el('a','button ghost small',text); node.href=href; node.target='_blank'; node.rel='noopener'; return node; };
  const validProduct = p => p && ['barril','latas'].includes(p.collection) && typeof p.id === 'string' && p.id.length > 0;
  const activeJobs = () => [...state.jobs.values()].filter(job=>['queued','running'].includes(job.status));
  const clean = () => !bridge.snapshot().dirty;
  const canAct = () => !state.busy && clean();
  function image(item, alt) { const src=mediaURL(item?.url || item?.thumbnail); if(!src)return null; const img=el('img'); img.src=src; img.alt=alt; img.loading='lazy'; return img; }
  function errorText(error) { return error.status===409 ? 'El borrador cambió mientras trabajábamos. Usa «Recargar borrador del servidor» y revisa los cambios antes de volver a intentarlo.' : error.message || 'No pudimos completar la operación. Intenta de nuevo.'; }
  function renderMessages(target) {
    if (!state.messages.length) {
      const welcome=el('div','agent-welcome'); welcome.append(el('span','agent-mark','CN'),el('h2','','Detrás de una buena cerveza,\nuna buena historia.'),el('p','muted','Pídeme que revise la carta, prepare contenido o te ayude con el diseño de la página. Si editamos contenido, quedará en el borrador para revisarlo.')); target.append(welcome);
      return;
    }
    for(const entry of state.messages) {
      const article=el('article','agent-message '+(entry.role==='user'?'is-user':'is-agent'));
      article.append(el('strong','agent-speaker',entry.role==='user'?'Tú':'Agente Cisne'),el('p','agent-message-text',entry.content));
      if(entry.changes?.length) {
        const details=el('details','agent-changes'); details.append(el('summary','',entry.changes.length+' cambios guardados en el borrador'));
        const list=el('ul'); entry.changes.forEach(change=>list.append(el('li','',({create:'Creado',update:'Actualizado',delete:'Eliminado'}[change.action]||'Cambio')+' · '+String(change.collection||'contenido')+' · '+String(change.id||'')))); details.append(list); article.append(details);
      }
      target.append(article);
    }
    if(state.busy) { const pending=el('p','agent-pending','El Cisne está trabajando…'); pending.setAttribute('role','status'); target.append(pending); }
  }
  function renderJobs(target) {
    if(!state.jobs.size)return;
    const section=el('section','agent-jobs'); section.append(el('h3','','Tus imágenes'));
    for(const job of state.jobs.values()) {
      const card=el('article','agent-job'); const title=job.product?.id || 'Imagen para la carta';
      card.append(el('strong','',title),el('span','badge '+(job.status==='ready'?'green':job.status==='failed'?'danger':''),({queued:'En cola',running:'Creando imagen',ready:'Lista para revisar',failed:'No se pudo generar'}[job.status]||'Consultando')));
      if(job.status==='ready') {
        const img=image(job.media,'Propuesta generada para '+title); if(img)card.append(img);
        card.append(el('p','fine','Revisa que nombre, etiqueta y presentación correspondan a la cerveza.'));
        card.append(button(job.applied?'Imagen añadida al borrador':'Usar imagen en el borrador',()=>applyImage(job), 'button primary small',!canAct()||job.applied||!ready(job.media)||!mediaURL(job.media?.url)||!validProduct(job.product)));
      } else if(job.status==='failed') card.append(el('p','form-error',job.error||'Vuelve a intentarlo con una etiqueta legible.'));
      if(job.pollError) card.append(el('p','fine',job.pollError));
      section.append(card);
    }
    target.append(section);
  }
  function render() {
    if(!host?.isConnected||!bridge)return;
    const focused=host.contains(document.activeElement)?document.activeElement:null;
    const focusId=focused?.id, selection=focusId==='agent-message'?[focused.selectionStart,focused.selectionEnd]:null;
    const snapshot=bridge.snapshot(); host.replaceChildren();
    if(snapshot.dirty) {
      const pending=el('div','agent-notice'); pending.setAttribute('role','status');
      pending.append(el('p','','Tienes cambios sin guardar en el CMS. Guárdalos para que el agente trabaje sobre la versión actual.'),button('Guardar borrador y continuar',saveLocal,'button secondary small',state.busy||snapshot.busy));host.append(pending);
    }
    const layout=el('div','agent-layout'), chat=el('section','card agent-chat'), studio=el('aside','agent-studio');
    chat.setAttribute('aria-label','Conversación con el agente');
    const top=el('div','agent-chat-heading'); top.append(el('h2','','Hablemos del Cisne'),button('Nueva conversación',clearChat,'button ghost small',state.busy)); chat.append(top);
    const availability=el('div','agent-availability'); availability.setAttribute('role','status');
    if(state.loading||!state.config&&!state.configError) availability.textContent='Conectando con el agente…';
    else if(state.configError) availability.append(el('p','',state.configError),button('Revisar conexión',loadConfig));
    else if(!state.config.configured) availability.append(el('strong','','El agente todavía no está conectado'),el('p','','El administrador debe configurar el proveedor de IA en el servidor. Tu CMS y MediaHub siguen disponibles.'));
    else availability.append(el('span','badge green','Agente conectado'),el('span','fine','Conoce el contenido y la identidad de Cisne Negro.'));
    chat.append(availability);
    const messages=el('div','agent-messages'); messages.setAttribute('role','log'); messages.setAttribute('aria-live','polite'); messages.setAttribute('aria-label','Mensajes'); renderMessages(messages); chat.append(messages);
    const suggestions=el('div','agent-suggestions');
    [['Carta','Ayúdame a crear una cerveza nueva en el borrador. Pídeme los datos que te falten.'],['Diseño','Revisa el diseño actual y propón tres mejoras coherentes con la identidad de Cisne Negro.'],['Contenido','Propón una historia para presentar las cervezas actuales y atraer visitas a la cervecería.']].forEach(([title,prompt])=>suggestions.append(button(title,()=>{state.input=prompt;const field=host.querySelector('#agent-message');field.value=prompt;field.focus();},'button ghost small',state.busy)));
    chat.append(suggestions);
    const form=el('form','agent-composer'); const label=el('label','sr-only','Tu mensaje para el agente');label.htmlFor='agent-message'; const textarea=el('textarea'); textarea.id='agent-message';textarea.name='message';textarea.rows=3;textarea.maxLength=6000;textarea.required=true;textarea.placeholder='Por ejemplo: agrega una IPA de temporada y ayúdame con su descripción…';textarea.value=state.input;textarea.disabled=state.busy;textarea.addEventListener('input',()=>{state.input=textarea.value;});
    textarea.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();form.requestSubmit();}});
    const actions=el('div','agent-composer-actions');actions.append(el('span','fine',state.label?'Etiqueta adjunta: '+(state.label.title||state.label.name||'imagen'):'Los cambios se guardan como borrador.'));const submit=el('button','button primary',state.busy?'Trabajando…':'Enviar');submit.type='submit';submit.disabled=!state.config?.configured||!canAct();actions.append(submit);
    form.append(label,textarea,actions);form.addEventListener('submit',sendMessage);chat.append(form);
    if(state.error){const error=el('p','form-error agent-error',state.error);error.setAttribute('role','alert');chat.append(error);}
    const step=el('section','card agent-label-card');step.append(el('p','eyebrow','De la etiqueta a la carta'),el('h2','','Una nueva cerveza.\nSu propia imagen.'),el('p','muted','Sube una fotografía clara de la etiqueta o elígela en MediaHub. La usaremos como referencia para crear su imagen del menú.'));
    const labelBox=el('div','agent-label-preview'); if(state.label) {const img=image(state.label,'Etiqueta seleccionada como referencia');if(img)labelBox.append(img);labelBox.append(el('strong','',state.label.title||state.label.name||'Etiqueta seleccionada'),el('span','fine',ready(state.label)?'Referencia lista':'El archivo aún no está listo. Selecciónalo desde MediaHub cuando termine de procesarse.'));} else labelBox.append(el('span','agent-step','01'),el('p','','Elige la etiqueta de la cerveza')); step.append(labelBox);
    const labelActions=el('div','button-row');const file=el('input','sr-only');file.type='file';file.id='agent-label-file';file.accept='image/jpeg,image/png,image/webp';file.addEventListener('change',()=>{if(file.files[0])uploadLabel(file.files[0]);});labelActions.append(button('Subir etiqueta',()=>file.click(),'button secondary small',!canAct()),button('MediaHub',pickLabel,'button ghost small',state.busy));if(state.label)labelActions.append(button('Quitar',()=>{state.label=null;render();},'button ghost small',state.busy));step.append(file,labelActions);
    const productLabel=el('label','','02 · Elige la cerveza');productLabel.htmlFor='agent-product';const select=el('select');select.id='agent-product';select.disabled=state.busy;const placeholder=el('option','','Selecciona una cerveza del borrador');placeholder.value='';select.append(placeholder);
    for(const collection of ['barril','latas']) {const group=el('optgroup');group.label=collection==='barril'?'De barril':'Latas y botellas';(snapshot.menu[collection]||[]).forEach(product=>{const option=el('option','',product.nombre+(product.visible===false?' · oculta':''));option.value=collection+':'+product.id;group.append(option);});select.append(group);}
    select.value=state.selection;if(select.value!==state.selection)state.selection='';select.addEventListener('change',()=>{state.selection=select.value;render();});step.append(productLabel,select,el('p','field-help','Si todavía no existe, pídele al agente que la cree primero.'));
    step.append(button('Crear imagen desde la etiqueta',generateImage,'button primary',!canAct()||!state.config?.image_configured||!ready(state.label)||!state.selection));
    if(state.config&&!state.config.image_configured)step.append(el('p','fine','La generación de imágenes todavía no está configurada en el servidor.'));
    step.append(el('p','fine agent-image-note','La generación utiliza IA y puede tardar unos minutos. Revisa el resultado antes de usarlo; la imagen no se publica automáticamente.'));studio.append(step);renderJobs(studio);layout.append(chat,studio);host.append(layout);
    if(state.messages.length)messages.scrollTop=messages.scrollHeight;
    if(focusId){const replacement=host.querySelector('#'+focusId);if(replacement&&!replacement.disabled){replacement.focus({preventScroll:true});if(selection)replacement.setSelectionRange(...selection);}}
  }
  async function loadConfig() {
    if(state.loading)return;const current=epoch;state.loading=true;state.configError='';render();
    try {const config=await bridge.api('/agent/config');if(current===epoch)state.config=config;}
    catch(error){if(current===epoch)state.configError=error.status===404?'El módulo del agente aún no está habilitado en este servidor.':errorText(error);}
    finally{if(current===epoch){state.loading=false;render();}}
  }
  async function saveLocal() {if(state.busy)return;state.busy=true;state.error='';render();try{await bridge.save();}catch(error){state.error=errorText(error);}finally{state.busy=false;render();}}
  function clearChat(){if(state.messages.length&&!confirm('¿Empezar una conversación nueva? El contenido guardado y las imágenes de MediaHub se conservan.'))return;state.messages=[];state.history=[];state.input='';state.error='';render();}
  async function run(task) {
    if(!canAct())return;const current=epoch;state.busy=true;state.error='';render();
    try{await bridge.run(()=>task(current));}catch(error){
      if(current===epoch){
        state.error=errorText(error);
        if(error.status===409&&clean()){
          try{await bridge.refresh();if(current===epoch)state.error='El borrador cambió mientras trabajábamos. Cargamos la versión actual; revisa los cambios antes de volver a intentarlo.';}
          catch(_){/* Se conserva el aviso y la opción de recargar del CMS. */}
        }
      }
    }
    finally{if(current===epoch){state.busy=false;render();schedulePoll();}}
  }
  async function sendMessage(event) {
    event.preventDefault();const message=state.input.trim();if(!message||!state.config?.configured)return;
    await run(async current=>{
      const body={message,history:state.history.slice(-12),version:bridge.snapshot().version};if(ready(state.label))body.label_media_id=state.label.id;
      state.messages.push({role:'user',content:message});state.input='';render();
      const result=await bridge.api('/agent/chat',{method:'POST',body});if(current!==epoch)return;
      const reply=String(result.reply||'La solicitud se completó. Revisa el borrador.');state.history.push({role:'user',content:message},{role:'assistant',content:reply.slice(0,6000)});state.history=state.history.slice(-12);
      state.messages.push({role:'assistant',content:reply,changes:result.changes||[]});state.messages=state.messages.slice(-40);
      (result.image_jobs||[]).forEach(job=>{if(job.id)state.jobs.set(String(job.id),job);});
      if(result.changes?.length||result.version!==undefined&&result.version!==bridge.snapshot().version)await bridge.refresh();
    });
  }
  async function pickLabel() {if(state.busy)return;const current=epoch;const item=await bridge.mediaPicker('image');if(current===epoch&&item){state.label=item;state.error='';render();}}
  async function uploadLabel(file) {
    if(!/^image\/(jpeg|png|webp)$/.test(file.type)){state.error='Usa una etiqueta en JPG, PNG o WebP.';render();return;}
    if(file.size>20*1024*1024){state.error='La etiqueta debe pesar menos de 20 MB.';render();return;}
    await run(async current=>{const data=new FormData();data.append('file',file);data.append('metadata',JSON.stringify({category:'Cervezas',tags:['etiqueta','referencia'],source:'equipo'}));const result=await bridge.api('/media',{method:'POST',body:data});if(current!==epoch)return;state.label=result.item||result.media||result;bridge.toast('Etiqueta guardada en MediaHub.');});
  }
  async function generateImage() {
    const split=state.selection.indexOf(':');const product={collection:state.selection.slice(0,split),id:state.selection.slice(split+1)};
    if(!state.config?.image_configured||!ready(state.label)||!validProduct(product))return;
    await run(async current=>{const result=await bridge.api('/agent/images',{method:'POST',body:{...product,reference_media_id:state.label.id,version:bridge.snapshot().version}});if(current!==epoch)return;if(!result.id)throw new Error('No recibimos el identificador de la imagen. Revisa MediaHub antes de volver a generarla.');state.jobs.set(String(result.id),{...result,product:result.product||product});});
  }
  async function applyImage(job) {
    if(job.status!=='ready'||!ready(job.media)||!validProduct(job.product)||!mediaURL(job.media.url))return;
    await run(async current=>{await bridge.api('/agent/content',{method:'POST',body:{version:bridge.snapshot().version,operation:{action:'update',...job.product,data:{img:job.media.url}}}});if(current!==epoch)return;job.applied=true;await bridge.refresh();bridge.toast('Imagen añadida al borrador. Revísala antes de publicar.');});
  }
  function mergeJob(job) {
    if(!job?.id)return;
    const existing=state.jobs.get(String(job.id));const next={...existing,...job};
    const product=validProduct(next.product)?bridge.snapshot().menu[next.product.collection]?.find(item=>item.id===next.product.id):null;
    next.applied=Boolean(existing?.applied || next.status==='ready'&&next.media?.url&&product?.img===next.media.url);
    state.jobs.set(String(job.id),next);
  }
  async function loadJobs() {
    if(state.loadingJobs||state.jobsLoaded)return;
    const current=epoch;state.loadingJobs=true;
    try{const result=await bridge.api('/agent/images');if(current!==epoch)return;(result.items||[]).forEach(mergeJob);state.jobsLoaded=true;}
    catch(error){if(current===epoch&&error.status===404)state.jobsLoaded=true;}
    finally{if(current===epoch){state.loadingJobs=false;render();schedulePoll();}}
  }
  function schedulePoll() {clearTimeout(pollTimer);if(host?.isConnected&&activeJobs().length)pollTimer=setTimeout(pollJobs,3500);}
  async function pollJobs() {
    const current=epoch;if(!host?.isConnected)return;
    await Promise.allSettled(activeJobs().map(async job=>{try{const result=await bridge.api('/agent/images/'+encodeURIComponent(job.id));if(current===epoch)mergeJob({...job,...result,pollError:''});}catch(error){if(current!==epoch)return;if([400,403,404].includes(error.status))state.jobs.set(String(job.id),{...job,status:'failed',error:errorText(error)});else job.pollError='No pudimos consultar el avance. Volveremos a intentar en unos segundos.';}}));
    if(current===epoch){render();schedulePoll();}
  }
  window.CisneAgent = {
    mount: async (element, apiBridge) => {host=element;bridge=apiBridge;render();await Promise.all([!state.config&&!state.loading&&!state.configError?loadConfig():null,loadJobs()]);schedulePoll();},
    unmount: () => {host=null;clearTimeout(pollTimer);},
    reset: () => {epoch++;host=null;bridge=null;clearTimeout(pollTimer);state=fresh();}
  };
})();
