// Run: PLAYWRIGHT_PATH=/tmp/cisne-qa/node_modules/playwright node tests/experiencia.cjs
// Requires existing local server; BASE_URL defaults to http://127.0.0.1:8093.
const {chromium} = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.env.BASE_URL || 'http://127.0.0.1:8093';
const out = process.env.EVIDENCE_DIR || '/tmp/cisne-experiencia-evidence';
(async () => {
  await fs.mkdir(out, {recursive:true});
  const browser = await chromium.launch({headless:true});
  const results=[];
  try {
    const menu = await (await fetch(base+'/data/menu.json')).json();
    for (const config of [
      {name:'desktop',viewport:{width:1440,height:1000}},
      {name:'mobile',viewport:{width:390,height:844},isMobile:true,hasTouch:true},
      {name:'small-mobile',viewport:{width:320,height:740},isMobile:true,hasTouch:true},
      {name:'reduced-motion',viewport:{width:1440,height:900},reducedMotion:'reduce'}
    ]) {
      const {name,...options}=config;
      const context=await browser.newContext(options);
      const page=await context.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
      await page.goto(base+'/experiencia/');
      await page.getByRole('radio').first().waitFor();
      assert.equal(await page.getByRole('radio').count(),2);
      const themes=[];
      for(const id of ['alarma','agua-puerca']){
        const beer=menu.barril.find(b=>b.id===id);
        await page.getByRole('radio',{name:beer.nombre,exact:true}).check();
        assert.equal(await page.getByRole('heading',{level:3}).textContent(),beer.nombre);
        assert.equal(await page.locator('.beer-notes').textContent(),beer.notas);
        assert.ok((await page.locator('.beer-meta').textContent()).includes(beer.abv.toFixed(1)));
        for(const price of beer.precios)assert.ok((await page.locator('.prices').textContent()).includes(String(price.precio)));
        assert.equal(await page.locator('#barra').getAttribute('data-beer'),id);
        const art=page.locator('.art-frame img:visible');
        assert.equal(await art.count(),1);
        assert.equal(await art.getAttribute('data-art'),id);
        assert.equal(await art.getAttribute('src'),'../assets/img/cervezas/'+id+'.jpg');
        await art.evaluate(img=>img.decode());
        assert.ok(await art.evaluate(img=>img.complete&&img.naturalWidth>0));
        assert.ok((await art.getAttribute('alt')).includes(beer.nombre));
        assert.ok((await page.locator('#art-caption').textContent()).includes(beer.nombre));
        themes.push(await page.locator('#barra').evaluate(el=>({
          background:getComputedStyle(el).backgroundColor,
          ink:getComputedStyle(el).color,
          accent:getComputedStyle(el).getPropertyValue('--accent'),
          title:getComputedStyle(el.querySelector('.beer-name')).fontFamily
        })));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        await page.locator('#barra').evaluate(el=>el.scrollIntoView({behavior:'instant'}));
        // ponytail: viewport capture avoids Chromium resetting touch emulation when resizing for tall captures.
        await page.screenshot({path:path.join(out,name+'-'+id+'.png'),fullPage:false});
      }
      for(const token of ['background','ink','accent','title'])assert.notEqual(themes[0][token],themes[1][token],token+' must change with beer');
      await page.getByRole('radio').first().focus();
      await page.keyboard.press('ArrowRight');
      assert.ok(await page.getByRole('radio').nth(1).isChecked());
      assert.equal(await page.locator('#barra').getAttribute('data-beer'),'agua-puerca');
      await page.keyboard.press('ArrowLeft');
      assert.equal(await page.locator('#barra').getAttribute('data-beer'),'alarma');
      assert.equal(await page.locator('.art-frame img:visible').getAttribute('data-art'),'alarma');
      await page.getByRole('radio').first().check();
      await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
      await page.screenshot({path:path.join(out,name+'-portada.png'),fullPage:false});
      await page.getByRole('link',{name:'Explorar la barra'}).click();
      await page.waitForFunction(()=>location.hash==='#barra');
      // End smooth scroll deterministically before geometry assertions/screenshots.
      await page.evaluate(()=>document.querySelector('#barra').scrollIntoView({behavior:'instant'}));
      await page.screenshot({path:path.join(out,name+'-barra.png'),fullPage:false});
      assert.ok(await page.getByRole('link',{name:'Ver menú'}).isVisible());
      const navRect=await page.getByRole('navigation').boundingBox();
      assert.ok(navRect.y>=0 && navRect.y<100);
      const links=await page.locator('a').evaluateAll(as=>as.map(a=>({href:a.href,target:a.target,rel:a.rel})));
      for(const a of links){
        if(a.href.startsWith(base)){
          const u=new URL(a.href);assert.equal((await fetch(u.origin+u.pathname)).status,200);
          if(u.pathname==='/experiencia/'&&u.hash)assert.equal(await page.locator(u.hash).count(),1);
        }else{assert.ok(a.href.startsWith('https://www.google.com/maps/'));assert.ok(a.rel.includes('noopener'));}
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.ok(await page.locator('img').evaluateAll(imgs=>imgs.every(i=>i.complete&&i.naturalWidth>0)));
      if(name!=='desktop'){
        assert.equal(await page.locator('html').getAttribute('data-motion'),'off',name);
        assert.ok(await page.locator('[data-parallax]').evaluateAll(es=>es.every(e=>!e.style.getPropertyValue('--shift'))));
        assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
      }else{
        assert.equal(await page.locator('html').getAttribute('data-motion'),'subtle');
        await page.emulateMedia({reducedMotion:'reduce'});
        await page.waitForFunction(()=>document.documentElement.dataset.motion==='off');
        assert.ok(await page.locator('[data-parallax]').evaluateAll(es=>es.every(e=>!e.style.getPropertyValue('--shift'))));
      }
      assert.deepEqual(errors,[]);
      results.push({name,status:'PASS',overflow:false,jsErrors:errors});
      await context.close();
    }
    const nojs=await browser.newContext({javaScriptEnabled:false});
    const p=await nojs.newPage();await p.goto(base+'/experiencia/');
    assert.ok(await p.getByRole('heading',{level:1}).isVisible());
    assert.ok(await p.getByRole('link',{name:'Ver la carta completa'}).isVisible());
    assert.ok(await p.locator('noscript p').isVisible());
    assert.ok((await p.locator('noscript p').textContent()).includes('Activa JavaScript'));
    assert.ok(await p.locator('[data-art="alarma"]').isVisible());
    assert.ok(await p.locator('[data-art="alarma"]').evaluate(img=>img.complete&&img.naturalWidth>0));
    assert.equal(await p.locator('#barra').getAttribute('data-beer'),'alarma');
    assert.equal(await p.getByRole('radio').count(),0);
    results.push({name:'no-javascript',status:'PASS'});await nojs.close();
    const errorContext=await browser.newContext();const e=await errorContext.newPage();
    await e.route('**/data/menu.json',route=>route.fulfill({status:503,body:'unavailable'}));
    await e.goto(base+'/experiencia/');await e.getByRole('button',{name:'Volver a intentar'}).waitFor();
    assert.ok((await e.getByRole('status').textContent()).includes('No pudimos'));
    await e.unroute('**/data/menu.json');await e.getByRole('button',{name:'Volver a intentar'}).click();
    await e.getByRole('radio').first().waitFor();assert.equal(await e.getByRole('radio').count(),2);
    results.push({name:'fetch-failure-and-retry',status:'PASS'});await errorContext.close();
    await fs.writeFile(path.join(out,'results.json'),JSON.stringify(results,null,2));
    console.log(JSON.stringify({results,evidence:out},null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
