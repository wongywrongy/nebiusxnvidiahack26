import { forwardRef, Fragment, useEffect, useImperativeHandle, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, getCaseText, getDocPages, getMode, getProject, getResult, getScores, pageUrl, runScores,
  startReplay, startRun, streamEvents, uploadPdf,
  type Case, type Compare, type CompareRow, type Decision, type DocPages, type Event, type Finding, type Fix, type Mark,
  type Project, type Result, type Scores, type Stage, type TextPage, type Tone, type Value,
} from './api'

// Five screens, one question each. Log: what came in and what needs me? Live run: what is it doing now?
// Review: what's wrong, and what's the fix? Alert: what changed since approval? Results: how good is it?
type View = 'log' | 'live' | 'review' | 'alert' | 'results'
type Tab = 'all' | 'action' | 'watch'
type Act = 'forward' | 'note' | 'return'
// What each pipeline step found, carried on the next step's event (see api/pipeline/runner.py).
type Info = {
  spec?: { pass: number; fail: number; unverified: number }
  web?: { sheet: string; verdict: string; sources: { url: string; tier: string }[] }
  fix?: string
}
type CaseState = { stage: Stage; message: string; models: string[]; decision?: Decision; summary?: string; info: Info; run: string }
// docs: page sizes of each downloaded submittal PDF; null when one is missing, then text holds the fixture pages.
type Loaded = { result: Result; docs: DocPages[] | null; text: TextPage[] | null }

const STEPS = ['Read', 'Compare to spec', 'Check the maker online', 'Find the fix', 'Write it up']
const STEP_OF: Partial<Record<Stage, number>> = {
  ingest: 0, triage: 0, extract: 1, spec_check: 1, verify: 2, reconcile: 2, fix: 3, report: 4, done: 5,
}
const REC: Record<Decision, Act> = { approve: 'forward', approve_with_note: 'note', send_back: 'return' }
const ACT: Record<Act, { label: string; short: string; done: string }> = {
  forward: { label: 'Stamp and forward', short: 'Approve instead', done: 'Forwarded' },
  note: { label: 'Forward with note', short: 'Approve with note', done: 'Forwarded with note' },
  return: { label: 'Send back with fix', short: 'Send back', done: 'Sent back' },
}
const NBSP = ' '
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
const fixOf = (r?: Result) => r?.findings.find((f) => f.fix)?.fix ?? null

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [view, setView] = useState<View>('log')
  const [tab, setTab] = useState<Tab>('all')
  const [states, setStates] = useState<Record<string, CaseState>>({})
  const [loaded, setLoaded] = useState<Record<string, Loaded>>({})
  const [current, setCurrent] = useState<string | null>(null)
  const [uploads, setUploads] = useState<Case[]>([])
  const [acts, setActs] = useState<Record<string, Act>>({}) // the reviewer's call on each item
  const [handled, setHandled] = useState<Record<string, boolean>>({}) // alerts dealt with
  const [lastRun, setLastRun] = useState<string | null>(null)
  const files = useRef<Record<string, string[]>>({})

  useEffect(() => {
    getProject().then((p) => {
      for (const c of p.cases) files.current[c.id] = c.submittal.map((d) => d.file)
      setProject(p)
      // Intake is on: in mock mode the sample submittals check themselves as soon as the log opens.
      getMode().then((m) => { if (m === 'mock') check(p.cases.filter((c) => !c.watch).map((c) => c.id), true) })
    }, () => setLoadFailed(true))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const watched = (project?.cases ?? []).filter((c) => c.watch)
  const intake = [...(project?.cases ?? []).filter((c) => !c.watch), ...uploads]
  const queue = intake.filter((c) => states[c.id]?.stage === 'done' && loaded[c.id])
  const caseOf = (id: string | null) => [...intake, ...watched].find((c) => c.id === id)

  async function load(run: string, caseId: string) {
    const fs = files.current[caseId] ?? []
    const [result, ...found] = await Promise.all([getResult(run, caseId), ...fs.map((f) => getDocPages(caseId, f))])
    const docs = found.length && found.every(Boolean) ? (found as DocPages[]) : null
    const l = { result: result as Result, docs, text: docs ? null : await getCaseText(caseId) }
    setLoaded((m) => ({ ...m, [caseId]: l }))
  }

  function follow(run: string) {
    streamEvents(run, (e: Event) => {
      const id = e.case_id
      if (!id) return
      if (e.stage === 'done') load(run, id) // prefetch, so opening is instant
      setStates((s) => {
        const p = e.stage === 'queued' ? undefined : s[id]
        return {
          ...s, [id]: {
            stage: e.stage, message: e.message, run,
            models: e.model && !p?.models.includes(e.model) ? [...(p?.models ?? []), e.model] : p?.models ?? [],
            decision: (e.data?.decision as Decision) ?? p?.decision,
            summary: (e.data?.summary as string) ?? p?.summary,
            info: { ...p?.info, ...(e.data as Info | null) },
          },
        }
      })
    }, () => {})
  }

  async function check(ids: string[], isIntake: boolean) {
    const run = await startRun(ids)
    if (isIntake) { setLastRun(run); setActs({}) }
    follow(run)
  }

  async function replay() {
    if (lastRun) { setActs({}); follow(await startReplay(lastRun)) }
  }

  async function upload(file: File) {
    const { run_id, case: c } = await uploadPdf(file)
    files.current[c.id] = c.submittal.map((d) => d.file)
    setUploads((u) => [...u, { ...c, number: 'Upload', product: 'Your PDF', from: 'you' }])
    follow(run_id)
  }

  function open(id: string) {
    const s = states[id]
    if (!s) return
    setCurrent(id)
    setView(s.stage !== 'done' || !loaded[id] ? 'live' : caseOf(id)?.watch ? 'alert' : 'review')
    window.scrollTo({ top: 0 })
  }

  // The live run opens the result when it's done.
  useEffect(() => {
    if (view === 'live' && current && states[current]?.stage === 'done' && loaded[current]) open(current)
  }) // eslint-disable-line react-hooks/exhaustive-deps

  function decide(id: string, act: Act) {
    const next = { ...acts, [id]: act }
    setActs(next)
    const i = queue.findIndex((c) => c.id === id)
    const after = [...queue.slice(i + 1), ...queue.slice(0, i)].find((c) => !next[c.id])
    setCurrent(after?.id ?? null) // null: everything reviewed
  }

  function toLog(t: Tab = 'all') { setTab(t); setView('log') }

  const cur = caseOf(current)
  const pos = queue.findIndex((c) => c.id === current)
  const step = (d: number) => { const c = queue[pos + d]; if (c) setCurrent(c.id) }

  const crumbs: [string, (() => void) | null][] =
    view === 'live' ? [['Submittals', () => toLog()], [`${cur?.number ?? ''} ${cur?.title ?? ''}`, null]]
    : view === 'review' ? [['Submittals', () => toLog()], ['Review', null]]
    : view === 'alert' ? [['Watchlist', () => toLog('watch')], [cur?.number ?? '', null]]
    : view === 'results' ? [['Results', null]]
    : [[project?.name ?? NBSP, null]]

  return (
    <div className="flex min-h-screen flex-col font-sans text-sm">
      <header className="flex min-h-[52px] items-center justify-between gap-4 border-b border-line px-4 sm:px-6">
        <nav className="flex min-w-0 items-center gap-2" aria-label="Breadcrumb">
          <button onClick={() => toLog()} className="flex shrink-0 items-center gap-2 font-semibold">
            <span className="h-3 w-3 rounded-sm bg-flare" />SpecCheck
          </button>
          {crumbs.map(([label, go], i) => (
            <Fragment key={i}>
              <span className="text-faint" aria-hidden>/</span>
              {go ? <button onClick={go} className="shrink-0 text-muted hover:text-ink">{label}</button> : <span className="truncate">{label}</span>}
            </Fragment>
          ))}
        </nav>
        {view === 'log' && (
          <span className="flex shrink-0 items-center gap-3 text-xs text-muted">
            <span className="hidden sm:inline">Intake on</span>
            <button onClick={replay} disabled={!lastRun} className="font-mono hover:text-ink disabled:opacity-40">replay</button>
          </span>
        )}
        {view === 'live' && <span className="hidden text-xs text-muted sm:inline">Opens the result when done</span>}
        {view === 'review' && cur && (
          <span className="flex shrink-0 items-center gap-2 font-mono text-xs text-muted">
            <button className="btn w-8 px-0" onClick={() => step(-1)} disabled={pos <= 0} aria-label="Previous submittal"><Chevron dir="left" /></button>
            <span className="tabular-nums">{pos + 1} / {queue.length}</span>
            <button className="btn w-8 px-0" onClick={() => step(1)} disabled={pos >= queue.length - 1} aria-label="Next submittal"><Chevron dir="right" /></button>
          </span>
        )}
      </header>

      {view === 'log' && (loadFailed
        ? <p className="m-6 text-muted">Couldn't load the project. Check that the API is running, then reload.</p>
        : <Log project={project} intake={intake} watched={watched} states={states} loaded={loaded} acts={acts} handled={handled}
            tab={tab} onTab={setTab} onOpen={open} onUpload={upload} onResults={() => setView('results')}
            onCheck={() => check(intake.map((c) => c.id), true)} onWatch={() => check(watched.map((c) => c.id), false)}
            onReview={() => { const c = queue.find((q) => !acts[q.id]) ?? queue[0]; if (c) open(c.id) }} />)}
      {view === 'live' && cur && states[cur.id] && <LiveRun c={cur} s={states[cur.id]} />}
      {view === 'review' && (
        <Review queue={queue} current={cur ?? null} loaded={loaded} states={states} acts={acts}
          onPick={(id) => setCurrent(id)} onDecide={decide} onResults={() => setView('results')} onAgain={() => { setActs({}); setCurrent(queue[0]?.id ?? null) }} />
      )}
      {view === 'alert' && cur && loaded[cur.id] && (
        <Alert c={cur} result={loaded[cur.id].result} onDone={() => { setHandled((h) => ({ ...h, [cur.id]: true })); toLog('watch') }} />
      )}
      {view === 'results' && <Results />}
    </div>
  )
}

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d={dir === 'left' ? 'M10 3 5 8l5 5' : 'm6 3 5 5-5 5'} stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ---------- log: what came in and what needs me? ----------

function Log({ project, intake, watched, states, loaded, acts, handled, tab, onTab, onOpen, onUpload, onResults, onCheck, onWatch, onReview }: {
  project: Project | null; intake: Case[]; watched: Case[]; states: Record<string, CaseState>; loaded: Record<string, Loaded>
  acts: Record<string, Act>; handled: Record<string, boolean>; tab: Tab; onTab: (t: Tab) => void; onOpen: (id: string) => void
  onUpload: (f: File) => Promise<void>; onResults: () => void; onCheck: () => void; onWatch: () => void; onReview: () => void
}) {
  const done = (id: string) => states[id]?.stage === 'done' && !!loaded[id]
  const checking = intake.filter((c) => states[c.id] && !done(c.id) && states[c.id].stage !== 'error').length
  const ready = intake.filter((c) => done(c.id) && !acts[c.id])
  const alerts = watched.filter((c) => done(c.id) && loaded[c.id].result.decision === 'send_back' && !handled[c.id])
  const watching = [...watched, ...intake.filter((c) => acts[c.id] && acts[c.id] !== 'return')]
  const lists: Record<Tab, Case[]> = { all: [...intake, ...watched], action: ready, watch: watching }
  const started = intake.some((c) => states[c.id])
  const headline = !project ? NBSP : checking ? `${checking} checking now`
    : started && !ready.length && intake.every((c) => done(c.id)) ? `All ${intake.length} checked`
    : started ? `${plural(ready.length, 'item')} need your call` : 'New packages are checked as they arrive.'

  const nav: [string, boolean, () => void, ReactNode?][] = [
    ['Submittals', tab !== 'watch', () => onTab('all')],
    ['Watchlist', tab === 'watch', () => onTab('watch'), alerts.length ? <span className="text-bad">{plural(alerts.length, 'alert')}</span> : null],
    ['Results', false, onResults],
  ]
  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <aside className="flex shrink-0 flex-col justify-between gap-4 border-line px-3 py-2 md:w-[180px] md:border-r md:py-5">
        <nav className="flex gap-1 md:flex-col">
          {nav.map(([label, on, go, extra]) => (
            <button key={label} onClick={go} aria-current={on ? 'page' : undefined}
              className={`flex h-9 items-center justify-between gap-2 rounded-md px-3 text-left ${on ? 'bg-selected font-medium text-ink' : 'text-soft hover:bg-raised hover:text-ink'}`}>
              {label}{extra && <span className="text-xs">{extra}</span>}
            </button>
          ))}
        </nav>
        <p className="hidden px-3 text-xs text-faint md:block">
          Specs: {project?.specs.map((s) => s.section).join(', ')}<br />{project?.specs[0]?.owner} standards
        </p>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
        <section className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-bold tracking-tight">Submittals</h1>
            <span className="text-muted">{headline}</span>
          </div>
          <div className="flex gap-2">
            <button className="btn h-10" onClick={onWatch} disabled={!project}>Run nightly watch</button>
            {started
              ? <button className="flare h-10 rounded-lg px-4 font-semibold disabled:opacity-40" onClick={onReview} disabled={!ready.length}>Review {ready.length} ready</button>
              : <button className="flare h-10 rounded-lg px-4 font-semibold disabled:opacity-40" onClick={onCheck} disabled={!project}>Check {intake.length} submittals</button>}
          </div>
        </section>

        <nav className="flex gap-6 border-b border-line" aria-label="Filter">
          {([['all', 'All'], ['action', 'Needs your call'], ['watch', 'Approved, watching']] as [Tab, string][]).map(([k, label]) => (
            <button key={k} onClick={() => onTab(k)} aria-current={tab === k ? 'page' : undefined}
              className={`-mb-px h-10 border-b-2 ${tab === k ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink'}`}>
              {label} <span className="text-faint">{lists[k].length}</span>
            </button>
          ))}
        </nav>

        <section className="flex flex-col">
          {!project && Array.from({ length: 7 }, (_, i) => <div key={i} className="flex h-16 items-center border-b border-line"><div className="h-4 w-1/2 rounded bg-raised" /></div>)}
          {project && !lists[tab].length && <p className="py-8 text-muted">{tab === 'action' ? 'Nothing needs your call right now.' : 'Nothing here yet.'}</p>}
          {lists[tab].map((c) => <LogRow key={c.id} c={c} s={states[c.id]} l={loaded[c.id]} act={acts[c.id]} handled={!!handled[c.id]} onOpen={onOpen} />)}
        </section>

        <Upload onUpload={onUpload} />
      </main>
    </div>
  )
}

function LogRow({ c, s, l, act, handled, onOpen }: {
  c: Case; s?: CaseState; l?: Loaded; act?: Act; handled: boolean; onOpen: (id: string) => void
}) {
  const done = s?.stage === 'done' && !!l
  const running = !!s && !done && s.stage !== 'error'
  let status: ReactNode
  if (s?.stage === 'error') status = <span className="text-bad">Couldn't check this one</span>
  else if (running) {
    status = (
      <span className="flex flex-col gap-2">
        <span className="truncate text-xs text-muted">{s.stage === 'done' ? 'Writing the result' : s.message}</span>
        <span className="h-px bg-line"><span className="block h-px bg-flare transition-[width] duration-300" style={{ width: `${((STEP_OF[s.stage] ?? 0) + 1) / 5 * 100}%` }} /></span>
      </span>
    )
  } else if (done && c.watch) {
    const alert = l.result.decision === 'send_back'
    const fact = l.result.findings.find((f) => f.check === 'status' && f.verdict === 'fail')?.compare?.right_value
    status = alert && !handled
      ? <Status label="Changed since approval" color={DECISION_COLOR.send_back} reason={`${show(fact ?? 'Changed')}${fixOf(l.result)?.suggest ? ' · replacement found' : ''}`} />
      : <Status label={handled ? 'Handled' : 'No change'} reason="Checked nightly" />
  } else if (done) {
    const fix = fixOf(l.result)
    status = act
      ? <Status label={ACT[act].done} reason={l.result.summary} />
      : <Status label={DECISION_LABEL[l.result.decision]} color={DECISION_COLOR[l.result.decision]}
          reason={`${l.result.summary}${fix ? (fix.suggest ? ' · fix ready' : ' · no passing fix') : ''}`} />
  } else status = c.watch ? <Status label="No change" reason={`Approved ${new Date(c.watch.approved).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}`} /> : <span className="text-xs text-faint">Waiting</span>

  return (
    <button onClick={() => onOpen(c.id)} disabled={!s}
      className="arrive grid h-20 w-full md:h-16 grid-cols-[minmax(0,1fr)_16px] items-center gap-4 border-b border-line px-2 text-left enabled:hover:bg-raised md:grid-cols-[104px_minmax(0,1fr)_minmax(0,1.2fr)_16px]">
      <span className="hidden font-mono text-xs text-muted md:block">{c.number}</span>
      <span className="flex min-w-0 flex-col gap-1 max-md:hidden">
        <span className="truncate">{c.title}</span>
        <span className="truncate text-xs text-faint">{c.product}{c.watch ? ` · approved ${new Date(c.watch.approved).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}` : ''}</span>
      </span>
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate md:hidden">{c.title}</span>
        {status}
      </span>
      <span className="text-faint" aria-hidden><Chevron dir="right" /></span>
    </button>
  )
}

function Status({ label, color, reason }: { label: string; color?: string; reason: string }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate font-medium" style={{ color }}>{label}</span>
      <span className="truncate text-xs text-muted" title={reason}>{reason}</span>
    </span>
  )
}

// Drop or choose a PDF: it becomes one more row, checked against this project's specs like the others.
function Upload({ onUpload }: { onUpload: (f: File) => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [over, setOver] = useState(false)
  async function send(f?: File | null) {
    if (!f) return
    setBusy(true); setError(null)
    try { await onUpload(f) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <label onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); send(e.dataTransfer.files[0]) }}
      className={`flex min-h-16 cursor-pointer items-center justify-between gap-4 rounded-xl border border-dashed px-4 transition-colors ${over ? 'border-soft bg-raised' : 'border-edge hover:border-soft'}`}>
      <span className="text-muted">{error ?? 'Try it with your own data sheet. Drop a firestop or lighting PDF here.'}</span>
      <span className="shrink-0 font-medium">{busy ? 'Uploading…' : 'Choose PDF'}</span>
      <input type="file" accept="application/pdf,.pdf" className="sr-only" disabled={busy}
        onChange={(e) => { send(e.target.files?.[0]); e.target.value = '' }} />
    </label>
  )
}

// ---------- live run: what is it doing right now? ----------

const TIER: Record<string, string> = { manufacturer: 'maker', listing_body: 'listing', distributor: 'distributor', agency: 'public copy', archive: 'archive', other: 'other' }

function LiveRun({ c, s }: { c: Case; s: CaseState }) {
  const at = STEP_OF[s.stage] ?? 0
  const [img, setImg] = useState(true)
  const sp = s.info.spec
  const web = s.info.web
  const rows: [string, ReactNode][] = [
    ['Spec items', !sp ? <span className="text-faint">{at >= 1 ? 'checking' : '—'}</span>
      : sp.fail ? <span className="text-bad">{sp.fail} must fix</span>
      : sp.unverified ? <span className="text-fyi">{sp.unverified} couldn't confirm</span> : <span className="text-good">Pass</span>],
    ['Data sheet', !web ? <span className="text-faint">{at >= 2 ? 'checking' : '—'}</span>
      : <span className={web.verdict === 'pass' ? 'text-good' : web.verdict === 'outdated' ? 'text-warn' : web.verdict === 'fail' ? 'text-bad' : 'text-fyi'}>{web.sheet}</span>],
  ]
  if (s.stage === 'fix' || s.info.fix) rows.push(['Fix', s.info.fix ? <span>{s.info.fix}</span> : <span className="text-faint">checking</span>])
  return (
    <div className="flex flex-1 flex-col">
      <nav className="flex gap-6 overflow-x-auto border-b border-line px-4 sm:px-8" aria-label="Steps">
        {STEPS.map((label, i) => (
          <span key={label} className={`flex h-12 shrink-0 items-center gap-2 ${i === at ? 'font-medium text-flare' : i < at ? 'text-muted' : 'text-faint'}`}>
            {i < at ? '✓' : i === at ? <span className="h-2 w-2 rounded-full bg-flare" /> : null}{label}
          </span>
        ))}
      </nav>
      <div className="grid flex-1 gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="relative mx-auto aspect-[8.5/11] w-full max-w-[520px] overflow-hidden rounded-sm bg-paper">
          {img && c.submittal[0] && <img src={pageUrl(c.id, c.submittal[0].file, 1)} alt="" className="absolute inset-0 h-full w-full object-cover object-top" onError={() => setImg(false)} />}
          {!img && <div className="flex flex-col gap-3 p-10">{[60, 88, 80, 84, 70, 76].map((w, i) => <div key={i} className="h-1 bg-paper-rule" style={{ width: `${w}%` }} />)}</div>}
          {at < 5 && <div className="scan absolute inset-x-0 h-0.5 bg-flare" />}
        </div>
        <section className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <span className="text-flare">{s.message}</span>
            <h1 className="text-lg font-semibold">{c.product ?? c.title} against {c.section}</h1>
          </div>
          <div className="flex flex-col border-t border-line">
            {rows.map(([k, v]) => <div key={k} className="flex min-h-12 items-center justify-between gap-4 border-b border-line">{k}<span className="text-right">{v}</span></div>)}
          </div>
          {web && web.sources.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-muted">Where it looked</span>
              {web.sources.map((x) => (
                <span key={x.url} className="flex justify-between gap-4"><span className="truncate">{hostOf(x.url)}</span><span className="font-mono text-xs text-faint">{TIER[x.tier] ?? x.tier}</span></span>
              ))}
            </div>
          )}
          <span className="mt-auto font-mono text-xs text-faint">{s.models.filter((m) => m !== 'code').map((m) => m.replace('tavily + ', '').split('/').pop()).filter((m, i, a) => a.indexOf(m) === i).join(', ')} · Tavily</span>
        </section>
      </div>
    </div>
  )
}


// ---------- the document, with findings drawn on it ----------

const TONE_COLOR: Record<Tone, string> = { red: '#e5534b', amber: '#e5a93b', blue: '#7fa7d9', green: '#2e9e68' }
const TONE_RANK: Record<Tone, number> = { red: 0, amber: 1, blue: 2, green: 3 }
const SEVERITY_RANK: Record<Finding['severity'], number> = { critical: 0, major: 1, minor: 2, info: 3 }
const toneOf = (f: Finding): Tone => (f.verdict === 'fail' ? 'red' : f.verdict === 'outdated' ? 'amber' : 'blue')
const LABEL: Record<Finding['verdict'], string> = {
  fail: 'Must fix', outdated: 'Out of date', note: 'Note', unverified: "Couldn't confirm", pass: 'Passed', not_applicable: 'Not applicable',
}
// A requirement was looked for but no claim was found on any page.
const notFound = (f: Finding) => !!f.requirement_id && f.claim_ids.length === 0


type Placed = Mark & { finding: Finding; tone: Tone }
type PdfPage = { key: string; file: string; n: number; width: number; height: number }

const pageKey = (file: string | null, n: number | null) => `${file}#${n}`
// A finding's page: the first claim that was located, else the first claim with a page.
const firstMark = (f: Finding) => f.highlights.find((h) => h.boxes.length) ?? f.highlights.find((h) => h.page)

function worstTone(ms: Placed[]): Tone | undefined {
  return ms.map((m) => m.tone).sort((a, b) => TONE_RANK[a] - TONE_RANK[b])[0]
}

// "now 17.5 W · 86.4 lm/W": one label per problem finding on a page, under its leftmost box.
function callouts(ms: Placed[], result: Result, selId: string | null) {
  const by = new Map<string, Placed[]>()
  for (const m of ms) if (m.kind === 'problem') by.set(m.finding.id, [...(by.get(m.finding.id) ?? []), m])
  return [...by.values()].flatMap((group) => {
    const rows = group.map((m) => changedRow(result, m.claim_id)).filter((r): r is CompareRow => !!r)
    const boxes = group.flatMap((m) => m.boxes)
    if (!rows.length || !boxes.length) return []
    return [{ finding: group[0].finding, x: Math.min(...boxes.map((b) => b.x0)), y: Math.max(...boxes.map((b) => b.y1)),
      text: [...new Set(rows.map((r) => r.current))].join(' · '), color: TONE_COLOR[group[0].finding.id === selId ? 'red' : group[0].tone] }]
  })
}

function changedRow(result: Result, claimId: string): CompareRow | undefined {
  const claim = result.claims.find((c) => c.id === claimId)
  return claim && result.comparison.find((r) => r.property === claim.property && r.changed)
}

// Real PDF pages in a scrolling column, with every located claim drawn over them.
const PdfPages = forwardRef<{ scrollTo: (key: string) => void }, {
  caseId: string; docs: DocPages[]; marks: Placed[]; selId: string | null; pulse: number; result: Result
  banner: ReactNode; label: string; onPick: (f: Finding) => void
}>(function PdfPages({ caseId, docs, marks, selId, pulse, result, banner, label, onPick }, ref) {
  const pages: PdfPage[] = docs.flatMap((d) => d.pages.map((s, i) => ({ key: pageKey(d.file, i + 1), file: d.file, n: i + 1, ...s })))
  const multi = docs.length > 1
  const sel = marks.find((p) => p.finding.id === selId && p.page)
  const [at, setAt] = useState(sel ? pageKey(sel.doc_file, sel.page) : pages[0]?.key)
  const scroller = useRef<HTMLDivElement>(null)
  const refs = useRef<Record<string, HTMLDivElement | null>>({})
  const byPage = useMemo(() => {
    const m: Record<string, Placed[]> = {}
    for (const p of marks) if (p.boxes.length) (m[pageKey(p.doc_file, p.page)] ??= []).push(p)
    return m
  }, [marks])

  function scrollTo(key: string) {
    setAt(key)
    const el = refs.current[key], box = scroller.current
    if (!el || !box) return
    // The column scrolls on its own; fall back to the window if it ever doesn't.
    if (box.scrollHeight > box.clientHeight + 1) box.scrollTo({ top: el.offsetTop - 4, behavior: 'smooth' })
    else el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  useImperativeHandle(ref, () => ({ scrollTo }))
  useEffect(() => { // open on the selected finding's page
    const m = marks.find((p) => p.finding.id === selId && p.boxes.length)
    if (m) requestAnimationFrame(() => {
      const el = refs.current[pageKey(m.doc_file, m.page)], box = scroller.current
      if (el && box && box.scrollHeight > box.clientHeight + 1) box.scrollTop = el.offsetTop - 4
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="flex shrink-0 items-center justify-between gap-3">
        <span className="truncate text-xs text-muted">{label} · page {pages.findIndex((p) => p.key === at) + 1} of {pages.length}</span>
        <nav className="flex gap-1 font-mono text-xs" aria-label="Pages">
          {pages.map((p, i) => {
            const t = worstTone(byPage[p.key] ?? [])
            return (
              <button key={p.key} onClick={() => scrollTo(p.key)} aria-current={p.key === at ? 'page' : undefined}
                className={`h-6 min-w-6 rounded px-1 tabular-nums ${p.key === at ? 'bg-selected text-ink' : 'text-faint hover:text-ink'}`}
                style={{ boxShadow: t ? `inset 0 -2px 0 ${TONE_COLOR[t]}` : undefined }}>{i + 1}</button>
            )
          })}
        </nav>
      </div>
      {banner && <p className="shrink-0 rounded-md border border-line bg-well px-3 py-2 text-xs text-soft">{banner}</p>}
      <div ref={scroller} className="relative flex max-h-[75vh] min-h-0 flex-1 flex-col gap-4 overflow-y-auto rounded min-[1100px]:max-h-none">
        {pages.map((p) => (
          <div key={p.key} ref={(el) => { refs.current[p.key] = el }}
            className="relative w-full shrink-0 overflow-hidden rounded-sm bg-white shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)]"
            style={{ aspectRatio: `${p.width} / ${p.height}` }}>
            <img src={pageUrl(caseId, p.file, p.n)} alt={`Page ${p.n}`} decoding="async" className="absolute inset-0 h-full w-full" />
            {/* checked first so problems draw on top; the selected finding last of all */}
            {[...(byPage[p.key] ?? [])]
              .sort((a, b) => Number(a.kind === 'problem') - Number(b.kind === 'problem') || Number(a.finding.id === selId) - Number(b.finding.id === selId))
              .map((m) => m.boxes.map((b, i) => {
                const on = m.finding.id === selId
                const c = TONE_COLOR[on ? 'red' : m.tone]
                return (
                  <Fragment key={`${m.finding.id}-${m.claim_id}-${i}`}>
                    <div key={on ? `p${pulse}` : 'still'} title={`${m.kind === 'checked' ? 'Checked' : LABEL[m.finding.verdict]}: ${m.finding.title}`}
                      onClick={m.kind === 'problem' ? () => onPick(m.finding) : undefined}
                      className={`absolute rounded-[2px] ${on ? 'pulse' : ''} ${m.kind === 'problem' ? 'cursor-pointer' : ''}`}
                      style={{
                        left: `calc(${b.x0 * 100}% - 2px)`, top: `calc(${b.y0 * 100}% - 2px)`,
                        width: `calc(${(b.x1 - b.x0) * 100}% + 4px)`, height: `calc(${(b.y1 - b.y0) * 100}% + 4px)`,
                        color: c, background: `${c}${on ? '38' : m.kind === 'checked' ? '1a' : '22'}`,
                        outline: `${on ? 2 : 1}px solid ${c}${on ? '' : m.kind === 'checked' ? '66' : '99'}`,
                      }} />
                  </Fragment>
                )
              }))}
            {callouts(byPage[p.key] ?? [], result, selId).map(({ finding, x, y, text, color }) => (
              <span key={finding.id} className={`absolute z-10 whitespace-nowrap rounded px-2 py-1 text-xs font-semibold text-on-accent shadow ${finding.id === selId ? '' : 'opacity-75'}`}
                style={{ left: `${x * 100}%`, top: `calc(${y * 100}% + 5px)`, background: color }}>
                now {text}
              </span>
            ))}
            <span className="absolute right-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
              {multi ? `${docs.find((d) => d.file === p.file)?.name} · ` : ''}p. {p.n}
            </span>
          </div>
        ))}
      </div>
    </>
  )
})

// Fallback when the PDF is not in data/raw: the fixture page text with each quote marked.
function TextPages({ pages, marks, selId, result, banner, page, onPage }: {
  pages: TextPage[]; marks: Placed[]; selId: string | null; result: Result; banner: ReactNode
  page: number; onPage: (n: number) => void
}) {
  const current = pages.find((p) => p.page === page) ?? pages[0]
  const text = current?.text ?? ''
  const spans = marks
    .filter((m) => m.page === current?.page && m.quote)
    .sort((a, b) => Number(a.finding.id === selId) - Number(b.finding.id === selId))
    .map((m) => ({ m, at: text.indexOf(m.quote!) }))
    .filter((s) => s.at >= 0)
    .sort((a, b) => a.at - b.at)
  const out: ReactNode[] = []
  let pos = 0
  for (const { m, at } of spans) {
    if (at < pos) continue // overlapping quote: keep the first
    const on = m.finding.id === selId
    const c = TONE_COLOR[m.tone]
    const row = m.kind === 'problem' ? changedRow(result, m.claim_id) : undefined
    out.push(text.slice(pos, at))
    out.push(
      <mark key={`${m.finding.id}-${m.claim_id}`} className="rounded-sm px-1 text-inherit"
        style={{ background: `${c}${on ? '55' : '22'}`, outline: on ? `2px solid ${c}` : 'none' }}>{m.quote}</mark>,
    )
    if (row) out.push(
      <span key={`${m.claim_id}-now`} className="ml-1 rounded px-2 py-1 align-middle font-sans text-xs font-semibold text-on-accent"
        style={{ background: c }}>now {row.current}</span>,
    )
    pos = at + m.quote!.length
  }
  out.push(text.slice(pos))
  return (
    <>
      <div className="flex flex-wrap items-center gap-1 font-mono text-xs">
        <span className="mr-2 font-sans text-muted">Page</span>
        {pages.map((p) => {
          const t = worstTone(marks.filter((m) => m.page === p.page))
          return (
            <button key={p.page} onClick={() => onPage(p.page)}
              className={`h-7 min-w-7 rounded px-2 tabular-nums ${p.page === current?.page ? 'bg-selected text-ink shadow-[inset_0_0_0_1px_var(--color-edge)]' : 'text-muted hover:bg-raised hover:text-ink'}`}
              style={{ boxShadow: t ? `inset 0 -2px 0 ${TONE_COLOR[t]}` : undefined }}>{p.page}</button>
          )
        })}
        <span className="ml-auto font-sans text-xs text-faint">PDF not downloaded: showing extracted text</span>
      </div>
      {banner && <p className="rounded-md border border-line bg-well px-3 py-2 text-xs text-soft">{banner}</p>}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="whitespace-pre-line rounded bg-paper p-8 text-base leading-7 text-paper-ink">
          <div className="mb-4 font-sans text-xs uppercase tracking-wide text-paper-meta">Page {current?.page} · text from the package</div>
          {out}
        </div>
      </div>
    </>
  )
}


function Icon({ kind }: { kind: 'x' | 'check' | 'dash' }) {
  const d = { x: 'm4 4 8 8M12 4l-8 8', check: 'm3.5 8.5 3 3 6-7', dash: 'M4.5 8h7' }[kind]
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden className="shrink-0">
      <path d={d} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const BIG = 'text-lg font-bold leading-tight'
const BAD = 'text-[#ff8a84]'
const show = (v: Value) => (v === null || v === undefined ? '—' : String(v))
const lower = (v: Value) => (Array.isArray(v) ? v : [show(v)]).join(' | ').toLowerCase()

// What the spec (or the job) needs, next to what was sent. Lists are chips; a needed item the other side lacks is outlined red.
function CompareBlock({ c }: { c: Compare }) {
  if (c.rows.length) { // currency: only the values that changed, sent -> current
    return (
      <div className="overflow-hidden rounded-[10px] border border-line">
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_16px_minmax(0,1.1fr)] gap-2 border-b border-line bg-well px-4 py-3">
          <span />
          {[c.left_label, null, c.right_label].map((l, i) => {
            if (l === null) return <span key={i} />
            const [head, rev] = splitLabel(l)
            return (
              <span key={i} className="flex min-w-0 flex-col gap-1">
                <span className={`${CAPS} ${i ? '!text-warn' : ''}`}>{head}</span>
                {rev && <span className="truncate font-mono text-xs text-faint" title={rev}>{rev}</span>}
              </span>
            )
          })}
        </div>
        {c.rows.map((r) => (
          <div key={r.property} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_16px_minmax(0,1.1fr)] items-baseline gap-2 border-t border-line px-4 py-3 first-of-type:border-t-0">
            <span className="text-muted">{r.label}</span>
            <span className="text-base text-muted">{r.submitted ?? '—'}</span>
            <span className="text-faint" aria-hidden>→</span>
            <span className="text-lg font-bold text-warn">{r.current ?? '—'}</span>
          </div>
        ))}
      </div>
    )
  }
  if (c.left_value === null || c.left_value === undefined) { // single fact, e.g. Status: Discontinued June 30, 2024
    return (
      <div className="flex flex-col gap-2 rounded-[10px] border border-line bg-well p-4">
        <span className={CAPS}>{c.left_label}</span>
        <span className={`flex items-center gap-2 ${BIG} ${c.verdict === 'fail' ? BAD : 'text-ink'}`}>
          {c.verdict === 'fail' && <Icon kind="x" />}{show(c.right_value)}
        </span>
      </div>
    )
  }
  const fail = c.verdict === 'fail'
  const missing = (Array.isArray(c.left_value) ? c.left_value : []).filter((it) => fail && !lower(c.right_value).includes(it.toLowerCase()))
  const notStated = c.right_value === 'Not stated' || c.right_value === 'Not found'
  const chips = Array.isArray(c.left_value) || Array.isArray(c.right_value)
  return (
    <div className={`grid overflow-hidden rounded-[10px] border border-line ${chips ? 'grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]' : 'grid-cols-2'}`}>
      <div className="flex min-w-0 flex-col gap-2 bg-well px-4 py-3">
        <span className={CAPS}>{c.left_label}</span>
        {Array.isArray(c.left_value)
          ? <div className="flex flex-wrap gap-2">{c.left_value.map((it) => (
              <span key={it} className={`rounded-md px-3 py-1 font-bold ${missing.includes(it) ? `border-[1.5px] border-bad text-base ${BAD}` : 'border border-line text-sm text-soft'}`}>{it}</span>))}</div>
          : <span className={BIG}>{show(c.left_value)}</span>}
      </div>
      <div className={`flex min-w-0 flex-col gap-2 border-l border-line px-4 py-3 ${fail && !notStated && !chips ? 'bg-bad/[0.07]' : ''}`}>
        <span className={CAPS}>{c.right_label}</span>
        {Array.isArray(c.right_value)
          ? <div className="flex flex-wrap gap-2">{c.right_value.map((it) => (
              <span key={it} className="rounded-md bg-white/[0.06] px-2 py-1 text-xs text-soft">{it}</span>))}</div>
          : <span className={`flex items-center gap-2 ${BIG} ${notStated ? 'text-muted' : fail ? BAD : c.verdict === 'changed' ? 'text-warn' : 'text-ink'}`}>
              {fail && !notStated && <Icon kind="x" />}{show(c.right_value)}
              {c.verdict === 'pass' && <span className="text-good"><Icon kind="check" /></span>}
            </span>}
        {missing.length > 0 && <span className={`text-xs ${BAD}`}>✗ doesn't cover {missing.join(', ')}</span>}
      </div>
    </div>
  )
}

// "Submitted (98-0400-5077-9 (2005))" -> ["Submitted", "98-0400-5077-9 (2005)"]
function splitLabel(l: string): [string, string] {
  const i = l.indexOf(' (')
  return i < 0 || !l.endsWith(')') ? [l, ''] : [l.slice(0, i), l.slice(i + 2, -1)]
}

const hostOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url } }


// ---------- review: what's wrong, and what's the fix? ----------

function Review({ queue, current, loaded, states, acts, onPick, onDecide, onResults, onAgain }: {
  queue: Case[]; current: Case | null; loaded: Record<string, Loaded>; states: Record<string, CaseState>; acts: Record<string, Act>
  onPick: (id: string) => void; onDecide: (id: string, a: Act) => void; onResults: () => void; onAgain: () => void
}) {
  const count = (a: Act) => Object.values(acts).filter((x) => x === a).length
  return (
    <div className="grid flex-1 grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)]">
      <nav className="hidden flex-col border-r border-line py-4 lg:flex" aria-label="Queue">
        {queue.map((c) => {
          const r = loaded[c.id].result
          const on = c.id === current?.id
          return (
            <button key={c.id} onClick={() => onPick(c.id)} aria-current={on ? 'true' : undefined}
              className={`flex h-14 flex-col justify-center gap-1 px-5 text-left ${on ? 'bg-raised shadow-[inset_2px_0_0_var(--color-ink)]' : 'hover:bg-raised'} ${acts[c.id] ? 'opacity-50' : ''}`}>
              <span className="truncate">{c.title}</span>
              <span className="text-xs" style={{ color: acts[c.id] ? undefined : DECISION_COLOR[r.decision] }}>
                {acts[c.id] ? ACT[acts[c.id]].done : DECISION_LABEL[r.decision]}
              </span>
            </button>
          )
        })}
      </nav>
      {current && loaded[current.id]
        ? <Reviewing key={current.id} c={current} l={loaded[current.id]} act={acts[current.id]} runId={states[current.id]?.run}
            onDecide={(a) => onDecide(current.id, a)} />
        : (
          <section className="flex flex-col items-center gap-4 px-6 py-24 text-center">
            <h1 className="text-2xl font-semibold">All {queue.length} reviewed</h1>
            <span className="text-muted">{count('forward')} forwarded · {count('note')} with a note · {count('return')} sent back</span>
            <div className="mt-3 flex items-center gap-4">
              <button className="flare h-10 rounded-lg px-4 font-semibold" onClick={onResults}>See how it scored</button>
              <button className="text-muted underline underline-offset-4 hover:text-ink" onClick={onAgain}>Review again</button>
            </div>
          </section>
        )}
    </div>
  )
}

function Reviewing({ c, l, act, onDecide }: { c: Case; l: Loaded; act?: Act; runId?: string; onDecide: (a: Act) => void }) {
  const { result, docs, text } = l
  // Worst first: must fix, then out of date, then notes and couldn't-confirm.
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass' && f.verdict !== 'not_applicable')
    .sort((a, b) => TONE_RANK[toneOf(a)] - TONE_RANK[toneOf(b)] || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]), [result])
  const marks: Placed[] = useMemo(() => result.findings.flatMap((f) =>
    f.highlights.map((h) => ({ ...h, finding: f, tone: h.kind === 'checked' ? 'green' as Tone : toneOf(f) }))), [result])
  const [selId, setSelId] = useState<string | null>(issues[0]?.id ?? null)
  const sel = issues.find((f) => f.id === selId) ?? null
  const [pulse, setPulse] = useState(0)
  const [textPage, setTextPage] = useState(() => (sel && firstMark(sel)?.page) || 1)
  const pdf = useRef<{ scrollTo: (key: string) => void }>(null)
  const fix = fixOf(result)
  const [attach, setAttach] = useState(true)
  const rec = REC[result.decision]
  const sub = c.from ?? 'the sender'
  const defaultNote = rec === 'forward' ? 'Reviewed. No exceptions taken.'
    : `${result.note_to_subcontractor || result.summary}${rec === 'return' && attach && fix?.suggest ? `\n\nSuggested: ${fix.suggest}. Checked against the spec.` : ''}`
  const [edited, setEdited] = useState<string | null>(null)
  const note = edited ?? defaultNote
  const actLabel = (a: Act) => (a === 'return' && !fix?.suggest ? 'Send back' : ACT[a].label)

  function select(f: Finding) {
    setSelId(f.id)
    setPulse((n) => n + 1)
    const m = firstMark(f)
    if (!m?.page) return
    if (docs) pdf.current?.scrollTo(pageKey(m.doc_file, m.page))
    else setTextPage(m.page)
  }

  const pageCount = docs ? docs.reduce((a, d) => a + d.pages.length, 0) : text?.length ?? 0
  const lost = sel && sel.highlights.length > 0 && docs && sel.highlights.every((h) => h.boxes.length === 0)
  const banner = !sel ? null
    : notFound(sel) ? <>Searched all {plural(pageCount, 'page')}: nothing in the package covers this.</>
    : lost ? <>Couldn't locate this on the page. The quote was: “{sel.highlights[0].quote}”</>
    : null
  const skipped = result.findings.filter((f) => f.verdict === 'not_applicable').length
  const src = sel?.evidence[0]

  return (
    <div className="grid min-w-0 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px]">
      {/* On narrow screens the decision comes first, then the document. */}
      <section className="order-2 flex min-w-0 flex-col gap-3 p-4 sm:p-6 xl:order-1 xl:sticky xl:top-0 xl:h-[calc(100vh-52px)]">
        {docs
          ? <PdfPages ref={pdf} caseId={result.case_id} docs={docs} marks={marks} selId={sel?.id ?? null} pulse={pulse}
              result={result} banner={banner} label={sub === 'you' ? 'Your upload' : sub} onPick={select} />
          : <TextPages pages={text ?? []} marks={marks} selId={sel?.id ?? null} result={result} banner={banner}
              page={textPage} onPage={setTextPage} />}
      </section>

      <aside className="order-1 flex min-w-0 flex-col gap-6 border-line p-4 sm:p-6 xl:order-2 xl:border-l">
        <div className="flex flex-col gap-1">
          <span className="font-semibold" style={{ color: DECISION_COLOR[result.decision] }}>{DECISION_LABEL[result.decision]}</span>
          <p className="text-base">{result.summary}</p>
        </div>

        {sel ? (
          <div className="flex flex-col gap-3">
            {issues.length > 1 && (
              <nav className="flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Findings">
                {issues.map((f) => (
                  <button key={f.id} onClick={() => select(f)} aria-current={f.id === sel.id ? 'true' : undefined}
                    className={f.id === sel.id ? 'text-ink' : 'text-muted underline underline-offset-4 hover:text-ink'}>{LABEL[f.verdict]}: {f.title}</button>
                ))}
              </nav>
            )}
            <span className="flex justify-between text-xs">
              <span style={{ color: TONE_COLOR[toneOf(sel)] }}>{LABEL[sel.verdict]}</span>
              <span className="text-muted">{firstMark(sel)?.page ? `page ${firstMark(sel)!.page}` : notFound(sel) ? 'not found' : 'whole document'}</span>
            </span>
            <h2 className="-mt-2 text-lg font-semibold leading-tight">{sel.title}</h2>
            {sel.compare && <CompareBlock c={sel.compare} />}
            {sel.why_it_matters && <p className="text-soft">{sel.why_it_matters}</p>}
            <span className="truncate text-xs text-muted">
              Source: {src
                ? <a href={src.url} target="_blank" rel="noreferrer" className="underline decoration-edge underline-offset-2 hover:text-ink">{src.title || hostOf(src.url)} ↗</a>
                : <>spec {sel.spec_ref || result.case_id}{result.document_revision ? ` · sheet ${result.document_revision}` : ''}</>}
            </span>
          </div>
        ) : (
          <ul className="flex flex-col gap-1 text-soft">
            {result.findings.filter((f) => f.verdict === 'pass').map((f) => <li key={f.id}><span className="text-good">✓</span> {f.title}</li>)}
            {skipped > 0 && <li className="text-xs text-faint">{skipped} not applicable</li>}
          </ul>
        )}

        {fix && <FixSection fix={fix} section={c.section} attach={attach} onAttach={(on) => { setAttach(on); setEdited(null) }} />}

        <div className="flex flex-col gap-2 border-t border-line pt-6">
          <label htmlFor="note" className="text-muted">{rec === 'return' ? `Note to ${sub}` : 'Stamp note'}</label>
          <textarea id="note" rows={5} value={note} onChange={(e) => setEdited(e.target.value)}
            className="resize-y rounded-lg border border-line bg-well p-3 leading-relaxed text-ink" />
          <button className="flare mt-2 h-12 rounded-lg font-semibold" onClick={() => onDecide(rec)}>{actLabel(rec)}</button>
          <div className="flex justify-center gap-6 text-muted">
            {(Object.keys(ACT) as Act[]).filter((a) => a !== rec).map((a) => (
              <button key={a} className="h-8 underline underline-offset-4 hover:text-ink" onClick={() => onDecide(a)}>{ACT[a].short}</button>
            ))}
          </div>
          {act && <span className="text-center text-xs text-faint">Already decided: {ACT[act].done}. Choosing again replaces it.</span>}
        </div>
      </aside>
    </div>
  )
}

const checkLine = (k: { ok: boolean | null; label: string; note: string }) =>
  `${k.ok === true ? '✓' : k.ok === false ? '✗' : '–'} ${k.label}${k.note && k.ok !== null ? ` ${k.note}` : ''}`

// What to send instead. Every candidate went through the same checks as a new submittal.
function FixSection({ fix, section, attach, onAttach }: { fix: Fix; section: string; attach: boolean; onAttach: (on: boolean) => void }) {
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-6">
      <span className="text-xs text-flare">Fix</span>
      <span className="-mt-2 font-semibold">{fix.head}</span>
      {fix.candidates.map((c, i) => {
        const bad = c.checks.some((k) => k.ok === false)
        const [verdict, color] = c.passes ? ['Passes', 'text-good'] : bad ? ['Fails', 'text-bad'] : ["Couldn't confirm", 'text-fyi']
        return (
          <div key={i} className={`flex flex-col gap-2 rounded-lg border p-3 ${c.passes ? 'border-good/40' : 'border-line'}`}>
            <span className="flex items-start justify-between gap-3">
              <a href={c.source_url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{c.name}</a>
              <span className={`shrink-0 text-xs ${color}`}>{verdict}</span>
            </span>
            <span className="text-xs leading-relaxed text-muted">{c.checks.map(checkLine).join('   ')}</span>
          </div>
        )
      })}
      {!fix.candidates.length && <span className="text-xs text-muted">Nothing found to check against {section}. Searched: “{fix.query}”</span>}
      {fix.suggest && (
        <label className="flex min-h-8 cursor-pointer items-center gap-2 text-soft">
          <input type="checkbox" checked={attach} onChange={(e) => onAttach(e.target.checked)} className="accent-[#F5791A]" />
          Attach to the note
        </label>
      )}
    </div>
  )
}

// ---------- alert: what changed since approval? ----------

type Order = 'none' | 'ordered' | 'installed'

function Alert({ c, result, onDone }: { c: Case; result: Result; onDone: () => void }) {
  const [order, setOrder] = useState<Order>('none')
  const [edits, setEdits] = useState<Partial<Record<Order, string>>>({})
  const status = result.findings.find((f) => f.check === 'status' && f.verdict === 'fail')
  const changed = status ?? result.findings.find((f) => f.verdict === 'fail' || f.verdict === 'outdated')
  const fix = fixOf(result)
  const best = fix?.candidates.find((x) => x.passes)
  const category = c.title.split(',')[0].replace(/^LED /, '').toLowerCase()
  const fact = show(changed?.compare?.right_value ?? 'Changed') // "Discontinued June 30, 2024"
  const [now, ...when] = fact.split(' ')
  const changedTo = `${now.toLowerCase()}${when.length ? ` (effective ${when.join(' ')})` : ''}`
  const approved = c.watch ? new Date(c.watch.approved).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : ''
  const src = changed?.evidence[0]
  if (!changed) {
    return <p className="m-6 text-muted">No change since approval. SpecCheck keeps checking this item nightly.</p>
  }
  const repl = best ? ` ${best.name} meets ${c.section}; checks attached.` : ''
  const drafts: Record<Order, [string, string, string]> = { // [label, draft, action]
    none: [`Message to ${c.from}`, `The ${c.product} approved under ${c.number} was ${changedTo}.${repl} Please submit ${best ? 'it or another' : 'a'} current substitute before ordering.`,
      best ? 'Send replacement to sub' : 'Ask sub for a substitute'],
    ordered: [`Message to ${c.from}`, `The ${c.product} on order for ${c.number} was ${changedTo}. Please confirm with your supplier that the full quantity will ship.${best ? ` If it can't,${repl}` : ''}`,
      'Ask sub to confirm'],
    installed: ['Closeout note', `Installed ${c.product} (${c.number}) was ${changedTo} after installation. For the O&M manual: replacements need a current substitute${best ? `, such as ${best.name}` : ''}.`,
      'Add to closeout'],
  }
  const [label, draft, action] = drafts[order]
  return (
    <div className="mx-auto grid w-full max-w-[1120px] flex-1 grid-cols-1 gap-12 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <span className="font-semibold text-bad">Changed since approval</span>
          <h1 className="text-2xl font-bold tracking-tight">The approved {category} was {status ? 'discontinued' : 'changed'}</h1>
          <span className="text-xs text-muted">{c.title} · {c.product} · approved {approved} · caught by the nightly watch</span>
        </div>
        <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-line">
          <div className="flex flex-col gap-1 bg-well p-4"><span className="text-xs text-muted">At approval</span><span className="text-lg font-semibold">Active</span></div>
          <div className="flex flex-col gap-1 border-l border-line p-4">
            <span className="text-xs text-muted">Today</span>
            <span className="text-lg font-semibold text-bad">{now}</span>
            {when.length > 0 && <span className="text-xs text-muted">effective {when.join(' ')}</span>}
          </div>
        </div>
        {src && <a href={src.url} target="_blank" rel="noreferrer" className="-mt-3 text-xs text-muted underline decoration-edge underline-offset-2 hover:text-ink">Source: {src.title} ↗</a>}
        <div className="flex flex-col gap-3 border-t border-line pt-6">
          <span className="text-xs text-flare">Fix</span>
          {best ? (
            <div className="flex flex-col gap-2 rounded-xl border border-good/40 p-4">
              <span className="flex items-start justify-between gap-3">
                <a href={best.source_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">{best.name}</a>
                <span className="shrink-0 text-xs text-good">Meets {c.section}</span>
              </span>
              <span className="text-xs leading-relaxed text-muted">{best.checks.map(checkLine).join('   ')}</span>
            </div>
          ) : <span className="text-muted">No passing replacement found.</span>}
        </div>
      </section>

      <aside className="flex flex-col gap-4">
        <span className="text-muted" id="order">Where is the order?</span>
        <div role="radiogroup" aria-labelledby="order" className="grid grid-cols-3 overflow-hidden rounded-lg border border-line">
          {([['none', 'Not ordered'], ['ordered', 'Ordered'], ['installed', 'Installed']] as [Order, string][]).map(([k, t]) => (
            <button key={k} role="radio" aria-checked={order === k} onClick={() => setOrder(k)}
              className={`h-10 border-l border-line first:border-l-0 ${order === k ? 'bg-selected text-ink' : 'text-muted hover:text-ink'}`}>{t}</button>
          ))}
        </div>
        <label htmlFor="msg" className="mt-2 text-muted">{label}</label>
        <textarea id="msg" rows={7} value={edits[order] ?? draft} onChange={(e) => setEdits((m) => ({ ...m, [order]: e.target.value }))}
          className="resize-y rounded-lg border border-line bg-well p-3 leading-relaxed text-ink" />
        <button className="flare h-12 rounded-lg font-semibold" onClick={onDone}>{action}</button>
        <button className="h-8 text-muted underline underline-offset-4 hover:text-ink" onClick={onDone}>Mark handled, keep watching</button>
      </aside>
    </div>
  )
}

// ---------- results: how good is it? ----------

const PROBLEM: Record<string, string> = {
  spec: 'spec', currency: 'out of date', validity: 'listing', status: 'discontinued', currency_note: 'newer, same values', completeness: 'missing',
}
const callOf = (d: Decision, problems: string[]) =>
  `${DECISION_LABEL[d]}${problems.length ? ` · ${problems.map((p) => PROBLEM[p] ?? p).join(', ')}` : ''}`

// About 40 working hours (one week) by hand for ~100 submittals: the canvas's reviewer estimate.
const BY_HAND_HOURS = 40

function Results() {
  const [scores, setScores] = useState<Scores | null | 'error' | undefined>(undefined)
  const [running, setRunning] = useState(false)
  useEffect(() => { getScores().then(setScores, () => setScores('error')) }, [])
  async function rerun() {
    setRunning(true)
    try { setScores(await runScores()) } catch { setScores('error') } finally { setRunning(false) }
  }
  const s = scores && scores !== 'error' ? scores : null
  const hours = s ? (s.time_ms_per_item * 100) / 3_600_000 : 0
  return (
    <main className="mx-auto flex w-full max-w-[1056px] flex-col gap-8 px-4 py-8 sm:px-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight">How well it works</h1>
          <span className="text-muted">
            {s ? `${s.rows.length} real submittals with a known answer. Last run ${new Date(s.generated_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}${s.mode === 'live' ? '.' : ', replayed from recordings.'}` : NBSP}
          </span>
        </div>
        <button className="flare h-10 rounded-lg px-4 font-semibold disabled:opacity-40" onClick={rerun} disabled={running}>
          {running ? 'Running…' : 'Run the scoring set'}
        </button>
      </section>

      {scores === undefined && <div className="grid h-[400px] grid-cols-2 gap-6 md:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <div key={i} className="h-20 rounded bg-raised" />)}</div>}
      {scores === 'error' && <p className="text-muted">Couldn't load the scores. Check that the API is running, then reload.</p>}
      {scores === null && <p className="text-muted">No scores yet. Run the scoring set, or <code className="font-mono text-soft">python scripts/eval.py</code>.</p>}

      {s && (
        <>
          <section className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat value={s.right_call.n} of={s.right_call.of} label="Right call" />
            <Stat value={s.caught.n} of={s.caught.of} label={`Problems caught, ${plural(s.false_alarms.n, 'false alarm')}`} />
            <Stat value={s.fixes_passing.n} of={s.fixes_passing.of} label="Fixes that pass the spec" accent />
            <Stat value={`${(s.time_ms_per_item / 1000).toFixed(1)} s`} label="Per submittal" />
          </section>

          <section className="grid grid-cols-[96px_minmax(0,1fr)_120px] items-center gap-x-4 gap-y-3">
            <span className="col-span-3 text-muted">A project with about 100 submittals</span>
            <span className="text-muted">By hand</span><span className="h-2 rounded bg-edge" /><span>about a week</span>
            <span>SpecCheck</span>
            <span className="h-2 rounded bg-line"><span className="block h-2 rounded bg-flare" style={{ width: `${Math.max(1, Math.min(100, (hours / BY_HAND_HOURS) * 100))}%` }} /></span>
            <span>{hours < 1 ? `${Math.max(1, Math.round(hours * 60))} min` : `${hours.toFixed(1)} hours`}</span>
          </section>

          <section className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead className="text-muted">
                <tr className="border-b border-line">{['Case', 'Document', 'Answer key', 'SpecCheck', 'Fix'].map((h, i) => <th key={h} className={`h-10 font-normal ${i === 0 ? 'w-16' : i === 1 ? 'w-44' : ''}`}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {s.rows.map((r) => (
                  <tr key={r.id} className="h-12 border-b border-line">
                    <td className="font-mono text-xs text-faint">{r.id}</td>
                    <td>{r.product || r.title}</td>
                    <td style={{ color: DECISION_COLOR[r.expected] }}>{callOf(r.expected, r.expected_problems)}</td>
                    <td>{r.error || !r.decision ? <span className="text-bad">Error</span>
                      : <span className="flex items-center gap-2"><span className={r.right_call ? 'text-good' : 'text-bad'}><Icon kind={r.right_call ? 'check' : 'x'} /></span>{DECISION_LABEL[r.decision]}</span>}</td>
                    <td className="text-muted">{!r.fix ? '—' : r.fix.passes ? r.fix.suggest : 'no passing fix'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <p className="text-xs text-muted">A problem counts as caught only if its type matches the key. A fix counts only if every check passes on quoted evidence, the same checks as a new submittal. All documents are public; sources are in the repo.</p>
        </>
      )}
    </main>
  )
}

function Stat({ value, of, label, accent }: { value: ReactNode; of?: number; label: string; accent?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className={`text-2xl font-bold tabular-nums ${accent ? 'text-flare' : ''}`}>
        {value}{of !== undefined && <span className="text-base font-medium text-faint">/{of}</span>}
      </span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  )
}
