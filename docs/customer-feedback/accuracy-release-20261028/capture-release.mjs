import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../../web/node_modules/playwright/index.mjs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const mode=process.argv[2]
assert(['memo-scoreboard','approved'].includes(mode))
const base='https://speccheck-wongywrongys-projects.vercel.app'
const out=process.env.SPECCHECK_EVIDENCE_DIR
const recording=process.env.EXPECTED_RECORDING
assert(out&&recording)
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.SPECCHECK_CHROMIUM_PATH})
const context=await browser.newContext({viewport:{width:1440,height:1000}})
const page=await context.newPage();page.setDefaultTimeout(30000)
const errors=[];page.on('pageerror',e=>errors.push(e.message))
const get=async route=>{const r=await context.request.get(base+route);assert(r.ok(),`${route}: ${r.status()}`);return r.json()}
const proof={url:base,recording,captured_at:new Date().toISOString(),mode}
const save=()=>fs.writeFileSync(path.join(out,mode==='approved'?'check-approved.json':'memo-scoreboard.json'),JSON.stringify(proof,null,2)+'\n')
try {
 proof.before=await get('/api/health');assert(!proof.before.today.blocked&&!proof.before.today.held_usd&&!proof.before.today.held_credits)
 assert.equal(proof.before.recorded,recording)
 if(mode==='memo-scoreboard') {
  proof.package=await get(`/api/runs/${recording}/package`);assert.equal(proof.package.rows.length,10)
  await page.goto(`${base}/memo/${recording}`)
  await page.getByRole('button',{name:'Print or save as PDF',exact:true}).waitFor()
  await page.getByText(`run ${recording}`,{exact:false}).first().waitFor()
  await page.screenshot({path:path.join(out,'memo.png'),fullPage:true})
  await page.pdf({path:path.join(out,'memo.pdf'),format:'Letter',printBackground:true})
  assert(fs.readFileSync(path.join(out,'memo.pdf')).subarray(0,4).equals(Buffer.from('%PDF')))
  proof.memo_printed=true
  proof.scores=await get('/api/scores');assert.equal(proof.scores.run_id,recording);assert.equal(proof.scores.mode,'live')
  await page.goto(base+'/#scoreboard');await page.getByRole('heading',{name:'Scoreboard',exact:true}).waitFor()
  for(const [label,key] of [['Right call','right_call'],['Planted problems caught','caught'],['Major false alarms on clean packages','false_alarms'],['Fixes that pass the spec','fixes_passing']]) {
   const text=await page.locator('dl > div').filter({has:page.getByText(label,{exact:true})}).innerText()
   assert(new RegExp(`${proof.scores[key].n}\\s+of\\s+${proof.scores[key].of}`).test(text),text)
  }
  await page.screenshot({path:path.join(out,'scoreboard.png'),fullPage:true});proof.scoreboard=true
 } else {
  await page.goto(base)
  await page.getByRole('heading',{name:'Sample submittals',exact:true}).waitFor()
  const added=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/inbox'&&r.request().method()==='POST')
    .then(async response=>{assert(response.ok());return response.json()})
  await page.locator('input[type=file][multiple]').first().setInputFiles({name:'off-topic.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(path.join(root,'tests/data/off-topic.pdf'))})
  proof.input=await added
  const started=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/scan'&&r.request().method()==='POST')
  await page.getByRole('button',{name:'Scan 1 submittal',exact:true}).click()
  const first=await started;assert(first.ok());proof.setup_run=await first.json()
  await page.getByRole('button',{name:'Start review',exact:true}).waitFor({timeout:900000});await page.getByRole('button',{name:'Start review',exact:true}).click()
  await page.getByRole('button',{name:'Mark as not checked',exact:true}).click()
  await page.getByRole('heading',{name:'Outcome',exact:true}).waitFor()
  const recheck=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/scan'&&r.request().method()==='POST')
  await page.getByRole('button',{name:'Check approved now',exact:true}).click()
  const response=await recheck;assert(response.ok(),await response.text());proof.request=response.request().postDataJSON();proof.run=await response.json();save()
  assert.equal(proof.request.refresh_web,true);assert.deepEqual(proof.request.ids,['c07']);assert(!proof.run.replay_of)
  const deadline=Date.now()+900000
  for(;;){const data=await get(`/api/runs/${proof.run.run_id}/results`);if(data.done){proof.results=data.results;break}assert(Date.now()<deadline);await page.waitForTimeout(1000)}
  assert.equal(proof.results.length,1)
  const result=proof.results[0];assert.equal(result.mode,'live');assert.equal(result.validity,'valid');assert(!result.replayed_from)
  assert(result.findings.some(f=>f.id==='status-discontinued'&&f.verdict==='fail'&&f.quote&&f.evidence.length))
  assert(result.fresh_web_credits>0)
  await page.getByRole('button',{name:'Check approved now',exact:true}).waitFor()
  await page.getByText(/is no longer made|no longer made|discontinued/i).first().waitFor({timeout:30000})
  await page.screenshot({path:path.join(out,'check-approved.png'),fullPage:true})
 }
 assert.deepEqual(errors,[]);proof.passed=true
} catch(e){proof.passed=false;proof.error=String(e);proof.error_stack=e.stack;await page.screenshot({path:path.join(out,mode+'-failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1}
finally {proof.after=await get('/api/health').catch(()=>null);proof.browser_errors=errors;if(proof.after)proof.cost={usd:+(proof.after.today.total_usd-proof.before.today.total_usd).toFixed(9),credits:proof.after.today.total_credits-proof.before.today.total_credits};save();console.log(JSON.stringify({mode,passed:proof.passed,error:proof.error,cost:proof.cost}));await browser.close()}
