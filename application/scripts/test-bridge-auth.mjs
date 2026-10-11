import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import ts from 'typescript'
import { chromium, devices } from 'playwright'
const source=await fs.readFile(new URL('../src/utils/bridgeAuth.ts',import.meta.url),'utf8')
const script=ts.transpileModule(source.replace(/^import .*$/m,"function getBridgeUrl(){return ''}").replace(/export /g,'')+'\nwindow.qa={bridgeFetch,saveBridgeKey};',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const browser=await chromium.launch()
try{
 for(const name of ['Pixel 7','iPhone 13','Desktop Chrome']){
  const context=await browser.newContext({...devices[name]});const page=await context.newPage();page.setDefaultTimeout(5000);page.on('pageerror',e=>console.log(e.message));let executions=0,attempts=0;let leaked=false
  await page.route('**/*',async route=>{
   const req=route.request();const url=new URL(req.url());const auth=req.headers().authorization
   if(url.hostname==='external.test'){leaked=!!auth;return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},body:'external'})}
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:`<meta charset="utf-8"><textarea>brouillon</textarea><script>${script}</script>`})
   if(url.pathname.endsWith('/run-async'))attempts++
   if(auth!=='Bearer fixture-good')return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:'forbidden_public'})})
   if(url.pathname.endsWith('/run-async'))executions++
   await route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,jobId:'one',events:[]})})
  })
  await page.goto('http://fixture.test/');await page.locator('textarea').fill('generation conservee')
  await page.evaluate(()=>{window.result=window.qa.bridgeFetch('/api/python/run-async',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scriptPath:'fixture.py',args:[]})}).then(r=>r.json())})
  const dialog=page.getByRole('dialog',{name:'Connexion Aurora'});await dialog.waitFor()
  await dialog.getByLabel('Clé d’accès Aurora').fill('bad')
  await dialog.getByRole('button',{name:'Connecter et continuer'}).click();await page.waitForTimeout(100)
  assert.equal(executions,0)
  await dialog.getByLabel('Clé d’accès Aurora').fill('fixture-good');await dialog.getByRole('button',{name:'Connecter et continuer'}).click()
  assert.equal((await page.evaluate(()=>Promise.race([window.result,new Promise((_,r)=>setTimeout(()=>r(Error('probe timeout')),5000))]))).jobId,'one');assert.equal(executions,1);assert.equal(attempts,2)
  await page.evaluate(async()=>{await window.qa.bridgeFetch('/api/python/job/one');await window.qa.bridgeFetch('http://external.test/api/check')})
  assert.equal(leaked,false);assert.equal(await page.locator('textarea').inputValue(),'generation conservee')
  await context.close();console.log(name+': login, retained draft, one execution, authenticated polling, no external credential leak')
 }
}finally{await browser.close()}
