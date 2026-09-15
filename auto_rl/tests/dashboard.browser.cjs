/* UI interactions use intercepted control requests: this test never launches GPU work. */
const assert=require('node:assert/strict');
const {chromium}=require('../../application/node_modules/playwright');
const fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1080}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:3001/api/training/ui');
  await page.waitForFunction(()=>document.querySelector('#trainModule').options.length===10);
  assert.equal(await page.locator('#modules tr').count(),10);
  // A clean state may have no candidate after an interrupted run; when one
  // exists, its measured gain is rendered here.
  assert.match(await page.locator('#candidateResult').innerText(),/-0[.,]10 pt|prochain entraînement|Gain non confirmé/);
  assert.equal(await page.locator('#useValidated').isDisabled(),true);
  await page.screenshot({path:'Outputs/auto_rl/diagnostics/training-dashboard-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'Outputs/auto_rl/diagnostics/training-dashboard-mobile.png',fullPage:true});
  await page.setViewportSize({width:1360,height:1080});
  const fixture=await (await page.request.get('http://127.0.0.1:3001/api/training/status')).json();
  let session={},posted=[];
  await page.route('**/api/training/status',async route=>{
   const server_time=Date.now()/1000;
   await route.fulfill({json:{...fixture,server_time,controller:session,cycle:session.active?{pid:555001,module:session.module,active:true,phase:'cloud_training',status:'Optimisation Kaggle',epoch:12,loss:.69,autonomous_elapsed_seconds:45}:fixture.cycle}});
  });
  await page.route('**/api/training/control/*',async route=>{
   const action=route.request().url().split('/').pop(),body=route.request().postDataJSON();posted.push({action,body});
   assert.ok(route.request().headers()['x-aurora-control']);
   if(action==='start')session={...body,session_id:'browser-test',active:true,phase:'running',started_at:Date.now()/1000-60,cycle_started_at:Date.now()/1000-40,completed_cycles:0,child_pid:555001};
   else session={...session,phase:action==='stop'?'stop_requested':'switch_requested',requested:{...body,action}};
   await route.fulfill({status:202,json:session});
  });
  await page.selectOption('#trainMode','continuous');
  await page.click('#start');
  await page.waitForFunction(()=>document.querySelector('#sessionMode').textContent==='Continu');
  assert.equal(posted[0].body.mode,'continuous');
  assert.equal(await page.locator('#start').isDisabled(),true);
  const elapsed=await page.locator('#elapsed').innerText();
  await page.waitForTimeout(2200);
  assert.notEqual(await page.locator('#elapsed').innerText(),elapsed);
  await page.selectOption('#trainModule','video');
  await page.selectOption('#trainMinutes','10');
  await page.click('#switch');
  await page.waitForFunction(()=>document.querySelector('#pending').textContent.includes('Vidéo'));
  assert.equal(posted[1].body.module,'video');assert.equal(posted[1].body.training_minutes,10);
  await page.click('#stop');
  await page.waitForFunction(()=>document.querySelector('#phase').textContent.includes('Arrêt propre demandé'));
  assert.equal(session.active,true);assert.match(await page.locator('#pending').innerText(),/Sauvegarde et audit/);
  await page.screenshot({path:'Outputs/auto_rl/diagnostics/training-dashboard-stop-test.png',fullPage:true});
  session={...session,phase:'stopped',active:false,finished_at:Date.now()/1000,elapsed_seconds:90,child_pid:null};
  await page.waitForFunction(()=>document.querySelector('#phase').textContent==='Session arrêtée proprement');
  const stopped=await page.locator('#elapsed').innerText();await page.waitForTimeout(1300);
  assert.equal(await page.locator('#elapsed').innerText(),stopped);
  assert.equal(await page.locator('#start').isEnabled(),true);
  assert.deepEqual(errors,[]);
  console.log('Dashboard: 10 modules, responsive layout, continuous start, live clock, deferred switch, graceful stop, frozen finished clock: PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
