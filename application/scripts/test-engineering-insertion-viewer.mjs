import assert from 'node:assert/strict'
import {spawn} from 'node:child_process'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {chromium,devices} from 'playwright'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const server=spawn(process.env.PYTHON||(process.platform==='win32'?'python':'python3'),['-u',path.join(root,'tests_agi/engineering_viewer_fixture.py')],{cwd:root,env:{...process.env,PYTHONPATH:[root,process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)}})
let diagnostics='',browser
server.stderr.on('data',chunk=>{diagnostics=(diagnostics+chunk.toString()).slice(-6000)})
try{
 const url=await new Promise((resolve,reject)=>{
  let buffer='';const timeout=setTimeout(()=>reject(Error('Engineering fixture timed out\n'+diagnostics)),60000)
  server.stdout.on('data',chunk=>{buffer+=chunk;let boundary;while((boundary=buffer.indexOf('\n'))!==-1){const line=buffer.slice(0,boundary);buffer=buffer.slice(boundary+1);try{const data=JSON.parse(line);if(typeof data.url==='string'){clearTimeout(timeout);resolve(data.url);return}}catch{}}})
  server.once('error',error=>{clearTimeout(timeout);reject(error)})
  server.once('exit',code=>{clearTimeout(timeout);reject(Error('Engineering fixture exited: '+code+'\n'+diagnostics))})
 })
 browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
 for(const device of ['Pixel 7','iPhone 13','iPad Mini','Desktop Chrome']){
  const context=await browser.newContext({...devices[device]}),page=await context.newPage(),errors=[],calls=[]
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/insertion'))calls.push(r.postDataJSON())})
  await page.goto(url);await page.waitForFunction(()=>document.body.dataset.ready==='true')
  const toggle=page.getByRole('button',{name:'Réglages / pièces',exact:true});if(await toggle.isVisible())await toggle.click()
  await page.getByRole('button',{name:'Inspecter piece_01',exact:true}).click()
  await page.getByRole('button',{name:'Vérifier l’insertion de la pièce inspectée',exact:true}).click()
  await page.waitForFunction(()=>document.body.dataset.insertionStatus==='clear_path_found',{},{timeout:60000})
  const status=await page.locator('#motion-status').innerText()
  assert.match(status,/trajet droit sans pénétration/);assert.match(status,/Ajustement, efforts et ordre de montage non validés/)
  assert.ok(calls.length>=6&&calls.every(call=>call.part_id==='piece_01'))
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  assert.deepEqual(errors,[]);console.log(device+': actual API, compared swept paths, scoped proof and responsive viewer passed');await context.close()
 }
}finally{await browser?.close();server.kill()}
