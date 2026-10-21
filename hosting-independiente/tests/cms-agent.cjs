/* UI real con API simulada. Servir sitio/ y ejecutar con Playwright en NODE_PATH.
   CISNE_UI_BASE=http://127.0.0.1:8661 node tests/cms-agent.cjs
   No utiliza cuentas, proveedores ni contenido operativo. */
'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require('playwright');
const origin=process.env.CISNE_UI_BASE||'http://127.0.0.1:8661';
const root=path.resolve(__dirname,'..');
let checks=0;
const check=(message,fn)=>{fn();checks++;console.log('✓ '+message);};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    let configured=false, version=8, conflict=false, longReply=false, jobCreated=false;
    let document={menu:JSON.parse(fs.readFileSync(path.join(root,'sitio/data/menu.json'),'utf8')),page:{},events:[],gallery:[]};
    const calls=[];
    const media={id:'test-label',kind:'image',status:'ready',url:'/assets/img/marca/favicon-192.png',title:'Etiqueta de prueba'};
    await page.route('**/cms/api/**',async route=>{
      const request=route.request(),url=new URL(request.url()),endpoint=url.pathname.replace('/cms/api','');
      let body;try{body=request.postDataJSON();}catch{body=request.postData();}
      calls.push({endpoint,method:request.method(),headers:request.headers(),body});
      const respond=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
      if(endpoint==='/session')return respond({user:{id:1,name:'Equipo de prueba',username:'prueba',role:'owner'},csrf:'test-csrf'});
      if(endpoint==='/state')return respond({document,version,published_document:document,published_version:8,schema:[],summary:{},user:{id:1,name:'Equipo de prueba',username:'prueba',role:'owner'}});
      if(endpoint==='/agent/config')return respond({configured,image_configured:configured,model:configured?'mock':null});
      if(endpoint==='/agent/chat')return respond({reply:longReply?'x'.repeat(7000):'<img src=x onerror="alert(1)">\nTexto seguro',version,changes:[],image_jobs:[],preview_url:'/cms/preview/menu/'});
      if(endpoint==='/media'&&request.method()==='POST')return respond({item:media},201);
      if(endpoint==='/media')return respond({items:[media],categories:[],page:1,pages:1,total:1});
      if(endpoint==='/draft'){document=body.document;version++;return respond({version});}
      if(endpoint==='/agent/images'&&request.method()==='POST'){jobCreated=true;return respond({id:'job-1',status:'queued',product:{collection:body.collection,id:body.id},version},202);}
      if(endpoint==='/agent/images')return respond({items:jobCreated?[{id:'job-1',status:'ready',product:{collection:'barril',id:document.menu.barril[0].id},media:{...media,id:'test-result'},version}]:[]});
      if(endpoint==='/agent/images/job-1')return respond({id:'job-1',status:'ready',product:{collection:'barril',id:document.menu.barril[0].id},media:{...media,id:'test-result'},version});
      if(endpoint==='/agent/content'){
        if(conflict){version++;return respond({error:'Otra persona actualizó el borrador.'},409);}
        const product=document.menu[body.operation.collection].find(p=>p.id===body.operation.id);product.img=body.operation.data.img;version++;return respond({version,changes:[body.operation]});
      }
      if(endpoint==='/logout')return respond({ok:true});
      return respond({error:'Ruta simulada no encontrada: '+endpoint},404);
    });
    await page.goto(origin+'/cms/#agente');
    await page.getByText('El agente todavía no está conectado',{exact:true}).waitFor();
    check('Estado sin proveedor y controles deshabilitados',()=>assert.ok(true));
    assert.equal(await page.getByRole('button',{name:'Enviar',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Crear imagen desde la etiqueta',exact:true}).isDisabled(),true);
    configured=true; await page.reload(); await page.getByText('Agente conectado',{exact:true}).waitFor();
    await page.locator('#agent-message').fill('Hola Cisne');await page.getByRole('button',{name:'Enviar',exact:true}).click();
    await page.locator('.agent-message.is-agent').waitFor();
    check('Chat renderiza texto y no ejecuta HTML de respuestas',()=>assert.ok(true));
    assert.equal(await page.locator('.agent-message.is-agent img').count(),0);
    assert.match(await page.locator('.agent-message.is-agent').innerText(),/<img src=x/);
    const chat=calls.find(call=>call.endpoint==='/agent/chat');
    check('Chat envía CSRF, versión y contexto acotado',()=>{assert.equal(chat.headers['x-csrf-token'],'test-csrf');assert.equal(chat.body.version,8);assert.equal(chat.body.message,'Hola Cisne');assert.deepEqual(chat.body.history,[]);});
    await page.evaluate(()=>{location.hash='menu';});await page.locator('[data-action="edit-product"][data-kind="barril"]').first().click();
    await page.locator('dialog input[name="nombre"]').fill('Cerveza editada localmente');await page.locator('dialog button[type="submit"]').click();
    await page.evaluate(()=>{location.hash='agente';});await page.getByText('Tienes cambios sin guardar en el CMS.',{exact:false}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Enviar',exact:true}).isDisabled(),true);
    assert.equal(calls.filter(call=>call.endpoint==='/draft').length,0);
    await page.getByRole('button',{name:'Guardar borrador y continuar',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('.agent-notice'));
    check('Conserva cambios locales y exige guardarlos antes de mutar',()=>{assert.equal(version,9);assert.equal(document.menu.barril[0].nombre,'Cerveza editada localmente');});
    await page.locator('#agent-label-file').setInputFiles(path.join(root,'sitio/assets/img/marca/favicon-192.png'));
    await page.getByText('Referencia lista',{exact:true}).waitFor();
    check('Etiqueta se carga a MediaHub con CSRF y metadatos',()=>{const upload=calls.find(call=>call.endpoint==='/media'&&call.method==='POST');assert.equal(upload.headers['x-csrf-token'],'test-csrf');assert.match(upload.body,/"category":"Cervezas"/);});
    const productId=document.menu.barril[0].id;
    await page.locator('#agent-product').selectOption('barril:'+productId);
    await page.getByRole('button',{name:'Crear imagen desde la etiqueta',exact:true}).click();
    await page.getByText('En cola',{exact:true}).waitFor();
    await page.locator('#agent-message').fill('Texto sin enviar mientras se genera la imagen');
    await page.locator('#agent-message').focus();
    await page.getByRole('button',{name:'Usar imagen en el borrador',exact:true}).waitFor();
    assert.equal(await page.locator('#agent-message').inputValue(),'Texto sin enviar mientras se genera la imagen');
    assert.equal(await page.locator('#agent-message').evaluate(el=>el===document.activeElement),true);
    check('Generación usa etiqueta/producto y preserva escritura al consultar avance',()=>{const job=calls.find(call=>call.endpoint==='/agent/images'&&call.method==='POST');assert.deepEqual(job.body,{collection:'barril',id:productId,reference_media_id:'test-label',version:9});});
    conflict=true;await page.getByRole('button',{name:'Usar imagen en el borrador',exact:true}).click();
    await page.getByText('El borrador cambió mientras trabajábamos. Cargamos la versión actual; revisa los cambios antes de volver a intentarlo.',{exact:true}).waitFor();
    check('Conflicto 409 refresca sin reintentar ni sobrescribir',()=>{assert.equal(calls.filter(call=>call.endpoint==='/agent/content').length,1);assert.equal(version,10);assert.equal(calls.filter(call=>call.endpoint==='/publish').length,0);});
    conflict=false;
    await page.getByRole('button',{name:'Usar imagen en el borrador',exact:true}).click();
    await page.getByRole('button',{name:'Imagen añadida al borrador',exact:true}).waitFor();
    check('Imagen se asigna explícitamente con versión actual y refresca CMS',()=>{const update=calls.filter(call=>call.endpoint==='/agent/content').at(-1);assert.equal(update.body.version,10);assert.equal(update.headers['x-csrf-token'],'test-csrf');assert.deepEqual(update.body.operation,{action:'update',collection:'barril',id:productId,data:{img:media.url}});assert.equal(version,11);});
    assert.equal(await page.locator('a[href="/cms/preview/menu/"]').count(),1);
    check('Vista previa interna y ninguna publicación automática',()=>assert.equal(calls.filter(call=>call.endpoint==='/publish').length,0));
    await page.evaluate(()=>{document.activeElement.blur();window.scrollTo(0,0);});
    await page.screenshot({path:'/tmp/cisne-agent-desktop.png',animations:'disabled'});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.waitForFunction(()=>new DOMMatrix(getComputedStyle(document.querySelector('#sidebar')).transform).m41<=-249);
    await page.evaluate(()=>window.scrollTo(0,0));
    assert.equal(await page.locator('.agent-chat').evaluate(el=>el.getBoundingClientRect().right<=innerWidth),true);
    check('Interfaz móvil sin desborde horizontal',()=>assert.ok(true));
    longReply=true;
    for(let i=0;i<8;i++){
      await page.locator('#agent-message').fill('Turno '+i);await page.getByRole('button',{name:'Enviar',exact:true}).click();
      await page.waitForFunction(()=>!document.querySelector('#agent-message').disabled);
    }
    check('Historial de 12 mensajes y respuestas de hasta 6000 caracteres',()=>{
      const chats=calls.filter(call=>call.endpoint==='/agent/chat');assert.equal(chats.at(-1).body.history.length,12);
      chats.forEach(call=>{assert(call.body.history.length<=12);call.body.history.forEach(entry=>assert(entry.content.length<=6000));});
    });
    assert.equal(await page.evaluate(()=>Object.keys(localStorage).length),0);
    await page.reload();await page.getByRole('button',{name:'Imagen añadida al borrador',exact:true}).waitFor();
    check('Recargar recupera imágenes y reconoce la ya aplicada al producto',()=>assert.ok(true));
    assert.deepEqual(await page.evaluate(()=>Array.from(document.querySelectorAll('#workspace *')).filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>innerWidth+1;}).map(el=>el.className)),[]);
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:'/tmp/cisne-agent-mobile.png',animations:'disabled'});
    await page.setViewportSize({width:1440,height:1050});await page.locator('#logout').click();await page.locator('#login-screen').waitFor({state:'visible'});
    check('Conversación y etiquetas no persisten en localStorage',()=>assert.ok(true));
    check('Ningún error JavaScript en navegación y operaciones',()=>assert.deepEqual(errors,[]));
    console.log('\n'+checks+' verificaciones de interfaz aprobadas. Capturas en /tmp/cisne-agent-{desktop,mobile}.png');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
