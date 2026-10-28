import { forwardRef, Fragment, useEffect, useImperativeHandle, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, addToInbox, getCaseText, getDocPages, getHealth, getProject, getResult, modelName, pageUrl, scan,
  streamEvents, uploadToInbox, setUploadSpec, archiveUrl, getPackage, type SavedChecklist,
  type Case, type CompareRow, type Decision, type DocPages, type Finding, type Fix, type Mark, type Project, type Result,
  type Health, type Investigation, type PackageRow, type PackageSummary, type Recheck, type Stage, type TextPage, type Tone,
  type Usage, type Value,
} from './api'
import { AlternatesCard, ConfigureLines, PackageMatrix, SummaryCounters } from './Feedback'
import { ScoreboardPage, SpecsPage } from './SecondaryPages'

// Four steps, in order: what came in, what the scan found, the reviewer's call on each, what happened after.
type Step = 1 | 2 | 3 | 4
const STEPS: [Step, string][] = [[1, 'Inbox'], [2, 'Scan'], [3, 'Review'], [4, 'Outcome']]
// One item's progress through a run. at: when its result arrived.
type Row = { stage: Stage; model: string | null; at?: string; reason?: string }
// docs: page sizes of each downloaded PDF; null when one is missing, then text holds the recorded page text.
// run: the run the result came from, for its package row.
type Loaded = { result: Result; docs: DocPages[] | null; text: TextPage[] | null; run: string }
type Act = 'return' | 'approve' | 'not_checked' | 'manual'
type Call = { act: Act; message: string }

type Session = {
  version: 2; step: Step; reached: Step; inbox: Case[]; rows: Record<string, Row>; loaded: Record<string, Loaded>
  calls: Record<string, Call>; current: string | null; checks: Record<string, Row>; checked: Record<string, Result>
  requested: Record<string, boolean>; drafts: Record<string, string>; scanNote: string | null; checkNote: string | null
  checklists: SavedChecklist[]; packages: Record<string, PackageSummary | null>
}
const SESSION_KEY = 'speccheck.session.v2'
function readSession(): Partial<Session> {
  try {
    const saved = JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null')
    const maps = ['rows', 'loaded', 'calls', 'checks', 'checked', 'requested', 'drafts', 'packages']
    if (saved?.version !== 2 || ![1, 2, 3, 4].includes(saved.step) || ![1, 2, 3, 4].includes(saved.reached)
      || !Array.isArray(saved.inbox) || !saved.inbox.every((c: Case) => typeof c.id === 'string' && Array.isArray(c.submittal))
      || (saved.checklists !== undefined && (!Array.isArray(saved.checklists) || !saved.checklists.every((c: SavedChecklist) => c && typeof c.id === 'string' && typeof c.section === 'string' && typeof c.title === 'string')))
      || maps.some((key) => !saved[key] || typeof saved[key] !== 'object' || Array.isArray(saved[key]))) return {}
    // shortcut: completed work survives reload; interrupted scans need Retry until SSE resumption is added.
    for (const [id, row] of Object.entries(saved.rows) as [string, Row][]) {
      if (!saved.loaded[id] && row.stage !== 'error') saved.rows[id] = { stage: 'error', model: null, reason: 'Scan interrupted by reload. Retry this item.' }
    }
    for (const [id, row] of Object.entries(saved.checks) as [string, Row][]) {
      if (!saved.checked[id] && row.stage !== 'error') saved.checks[id] = { stage: 'error', model: null, reason: 'Re-check interrupted by reload. Check approved now to try again.' }
    }
    return saved
  } catch { return {} }
}

const STAGE: Partial<Record<Stage, [string, number]>> = {
  queued: ['Queued', 0.04], ingest: ['Reading pages', 0.12], triage: ['Reading pages', 0.22],
  extract: ['Checking the spec', 0.36], spec_check: ['Checking the spec', 0.5],
  verify: ['Checking manufacturer documents', 0.64], fix: ['Looking for a replacement', 0.8], report: ['Writing summary', 0.92],
  investigate: ['Investigating', 0.72],
  done: ['Writing summary', 0.98],
}
const KIND: Record<string, string> = { product_data: 'Product data', system_drawing: 'System drawing' }
const TRAY_MIME = 'application/x-speccheck-item'
const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const PRIMARY = 'flare h-10 shrink-0 rounded-lg px-4 font-semibold disabled:cursor-not-allowed disabled:opacity-40'
const NBSP = ' '

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
const now = () => `Today ${new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
const longDate = (d: string) => {
  const parsed = new Date(/^\d{4}-\d\d-\d\d$/.test(d) ? `${d}T00:00` : d)
  return Number.isNaN(parsed.getTime()) ? d : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
const fileName = (c: Case) => c.submittal[0]?.file.split('/').pop() ?? ''
const fixOf = (r?: Result) => r?.findings.find((f) => f.fix)?.fix ?? null
// Spec values come lower-cased ("astm e814"); acronyms back to capitals, list items joined.
const ACRONYM = /\b(astm|ul|ulc|can|dlc|cri|voc|fm|its|ic|cpvc|pvc|abs|pex|frpp|pvdf)\b/gi
const show = (v: Value | undefined) => (v === null || v === undefined || v === '' ? '—'
  : (Array.isArray(v) ? v.join(', ') : String(v)).replace(ACRONYM, (m) => m.toUpperCase()).replace(/\b([a-z])(\d{3,})\b/g, (_, a: string, n: string) => a.toUpperCase() + n))
const displayQuote = (quote: string) => quote.replace(/\*\*|__/g, '')
const hostOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url } }
const discontinued = (r?: Result) => r?.findings.find((f) => f.check === 'status' && f.verdict === 'fail')
// "tavily + nvidia/nemotron-3-super-120b-a12b" -> "Tavily + Nemotron 3 Super"
const modelTag = (m: string | null) => !m || m === 'code' ? ''
  : m.replace(/\S+\/\S+/g, (id: string) => modelName(id)).replace(/^tavily/i, 'Tavily')

// ---------- the trace: which model did what, from the usage every result carries ----------

const money = (usd: number) => `$${usd.toFixed(usd < 0.001 ? 4 : usd < 0.01 ? 3 : 2)}`
const kTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n))
const seconds = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s` : `${ms} ms`)
// What each call did, in the reviewer's words. Fix-step calls come prefixed "fix: ".
const TASK_LABEL: Record<string, string> = {
  triage: 'sorted the pages', extract_requirements: 'read the spec', extract_claims: 'read the data sheet', product_type: 'identified the product type',
  verify: 'read the web sources', investigate: 'investigated missing documents', report: 'wrote the result',
  'fix: extract_claims': 'read a replacement', 'fix: verify': 'checked a replacement online',
}
const taskLabel = (t: string) => TASK_LABEL[t] ?? t
// Calls grouped by model, in order of first use, each with its distinct tasks.
function byModel(usage: Usage[]): { model: string; tasks: string[]; calls: Usage[] }[] {
  const out: { model: string; tasks: string[]; calls: Usage[] }[] = []
  for (const u of usage) {
    let g = out.find((x) => x.model === u.model)
    if (!g) out.push((g = { model: u.model, tasks: [], calls: [] }))
    g.calls.push(u)
    const t = taskLabel(u.task)
    if (!g.tasks.includes(t)) g.tasks.push(t)
  }
  return out
}
const totals = (usage: Usage[]) => ({
  tokens: usage.reduce((n, u) => n + u.input_tokens + u.output_tokens, 0),
  cost: usage.reduce((n, u) => n + u.cost_usd, 0),
})

export default function App() {
  const [saved] = useState(readSession)
  const streams = useRef(new Set<() => void>())
  const generation = useRef(0)
  const [secondary, setSecondary] = useState(window.location.hash)
  const [project, setProject] = useState<Project | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [scanNote, setScanNote] = useState<string | null>(saved.scanNote ?? null)
  const [checkNote, setCheckNote] = useState<string | null>(saved.checkNote ?? null)
  const [failed, setFailed] = useState(false)
  const [step, setStep] = useState<Step>(saved.step ?? 1)
  const [reached, setReached] = useState<Step>(saved.reached ?? 1)
  const [inbox, setInbox] = useState<Case[]>(saved.inbox ?? [])
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<Record<string, Row>>(saved.rows ?? {}) // the scan
  const [loaded, setLoaded] = useState<Record<string, Loaded>>(saved.loaded ?? {})
  const [calls, setCalls] = useState<Record<string, Call>>(saved.calls ?? {}) // the reviewer's decisions, client-side only
  const [drafts, setDrafts] = useState<Record<string, string>>(saved.drafts ?? {})
  const [current, setCurrent] = useState<string | null>(saved.current ?? null)
  const [checks, setChecks] = useState<Record<string, Row>>(saved.checks ?? {}) // "Check approved now"
  const [checked, setChecked] = useState<Record<string, Result>>(saved.checked ?? {})
  const [requested, setRequested] = useState<Record<string, boolean>>(saved.requested ?? {}) // substitutions requested
  const [checklists, setChecklists] = useState<SavedChecklist[]>(saved.checklists ?? [])
  const [changingSpec, setChangingSpec] = useState(false)
  // The package view per run, fetched once its items are all in; null when it couldn't be loaded.
  const [packages, setPackages] = useState<Record<string, PackageSummary | null>>(saved.packages ?? {})

  useEffect(() => {
    const session: Session = { version: 2, step, reached, inbox, rows, loaded, calls, current, checks, checked, requested, drafts, scanNote, checkNote, checklists, packages }
    try { localStorage.setItem(SESSION_KEY, JSON.stringify(session)) }
    catch { try { localStorage.removeItem(SESSION_KEY) } catch { /* storage may be disabled */ } }
  }, [step, reached, inbox, rows, loaded, calls, current, checks, checked, requested, drafts, scanNote, checkNote, checklists, packages])
  const fetching = useRef(new Set<string>())
  const scanning = Object.values(rows).some((r) => !['done', 'error'].includes(r.stage))
  useEffect(() => {
    if (scanning) return
    for (const [id, l] of Object.entries(loaded)) {
      const run = l.run
      if (fetching.current.has(run) || packages[run] === null || packages[run]?.rows.some((r) => r.case_id === id)) continue
      fetching.current.add(run)
      const active = generation.current
      getPackage(run).then((p) => { if (active === generation.current) setPackages((m) => ({ ...m, [run]: p })) },
        () => { if (active === generation.current) setPackages((m) => ({ ...m, [run]: null })) })
        .finally(() => fetching.current.delete(run))
    }
  }, [scanning, loaded, packages])
  const rowOf = (id: string): PackageRow | undefined => {
    const run = loaded[id]?.run
    return run ? packages[run]?.rows.find((r) => r.case_id === id) : undefined
  }
  useEffect(() => () => { generation.current++; streams.current.forEach((close) => close()); streams.current.clear() }, [])

  useEffect(() => { getProject().then(setProject, () => setFailed(true)) }, [])
  useEffect(() => { getHealth().then(setHealth).catch(() => {}) }, [])
  useEffect(() => {
    const change = () => { setSecondary(window.location.hash); window.scrollTo({ top: 0 }) }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])

  function go(s: Step) {
    if (window.location.hash) window.location.hash = ''
    setStep(s)
    setReached((r) => (s > r ? s : r))
    window.scrollTo({ top: 0 })
  }

  // Stream a run into a row map; onDone gets each item's result.
  function follow(run: string, ids: string[], set: typeof setRows, onDone: (id: string, r: Result) => void) {
    const active = generation.current
    const incomplete = (reason: string) => {
      if (active !== generation.current) return
      set((m) => Object.fromEntries(Object.entries(m).map(([id, row]) => [id,
        !ids.includes(id) || ['done', 'error'].includes(row.stage) ? row : { stage: 'error', model: null, reason }])))
    }
    const close = streamEvents(run, (e) => {
      if (active !== generation.current) return
      const id = e.case_id
      if (!id) return
      if (e.stage === 'done') getResult(run, id).then((r) => {
        if (active !== generation.current) return
        set((m) => ({ ...m, [id]: { ...m[id], at: now() } })); return onDone(id, r)
      }).catch((error: Error) => { if (active === generation.current) set((m) => ({ ...m, [id]: { stage: 'error', model: null, reason: error.message } })) })
      set((m) => ({ ...m, [id]: { ...m[id], stage: e.stage, reason: e.stage === 'error' ? e.message : undefined,
        model: e.model ?? (e.stage === 'done' ? null : m[id]?.model ?? null) } }))
    }, () => {
      streams.current.delete(close)
      incomplete('The scan ended before this item completed. Retry this item.')
      getHealth().then(setHealth).catch(() => {})
    }, (error) => { streams.current.delete(close); incomplete(error.message) })
    streams.current.add(close)
  }

  function startOver() {
    generation.current++
    streams.current.forEach((close) => close()); streams.current.clear()
    setInbox([]); setRows({}); setLoaded({}); setCalls({}); setDrafts({}); setCurrent(null)
    setChecks({}); setChecked({}); setRequested({}); setScanNote(null); setCheckNote(null); setError(null)
    setChecklists([]); setPackages({})
    setReached(1); go(1)
    try { localStorage.removeItem(SESSION_KEY) } catch { /* storage may be disabled */ }
  }

  async function add(id: string) {
    const active = generation.current
    setError(null)
    try {
      const c = await addToInbox(id)
      if (active !== generation.current) return
      setInbox((i) => (i.some((x) => x.id === c.id) ? i : [...i, c]))
    } catch (e) { if (active === generation.current) setError((e as Error).message) }
  }

  async function upload(files: File[]) {
    const active = generation.current
    setError(null)
    for (const f of files) {
      if (active !== generation.current) return
      try {
        const c = await uploadToInbox(f)
        if (active !== generation.current) return
        setInbox((i) => [...i, { ...c, received: now() }])
      } catch (e) { if (active === generation.current) setError(`${f.name}: ${(e as Error).message}`) }
    }
  }

  async function startScan(retryId?: string) {
    const active = generation.current
    const fresh = inbox.filter((c) => retryId ? c.id === retryId : !rows[c.id])
    setError(null)
    try {
      const run = await scan(fresh.map((c) => c.id))
      if (active !== generation.current) return
      setScanNote(run.note ?? null)
      setRows((m) => ({ ...m, ...Object.fromEntries(fresh.map((c) => [c.id, { stage: 'queued' as Stage, model: null }])) }))
      follow(run.run_id, fresh.map((c) => c.id), setRows, async (id, result) => {
        const c = fresh.find((x) => x.id === id)!
        const found = await Promise.all(c.submittal.map((d) => getDocPages(id, d.file)))
        const docs = found.length && found.every(Boolean) ? (found as DocPages[]) : null
        const text = docs ? null : await getCaseText(id)
        if (active !== generation.current) return
        setLoaded((m) => ({ ...m, [id]: { result, docs, text, run: run.run_id } }))
      })
      go(2)
    } catch (e) { if (active === generation.current) setError((e as Error).message) }
  }

  async function changeSpec(id: string, spec: string) {
    const active = generation.current
    setChangingSpec(true); setError(null)
    try {
      const updated = await setUploadSpec(id, spec)
      if (active === generation.current) setInbox((items) => items.map((c) => c.id === id ? { ...c, ...updated, checklist_id: updated.checklist_id } : c))
    } catch (e) { if (active === generation.current) setError((e as Error).message) }
    finally { setChangingSpec(false) }
  }

  const scanned = inbox.filter((c) => rows[c.id])
  const queue = scanned.filter((c) => loaded[c.id])

  // shortcut: the memo covers one run; items retried into a second run are left out until memos take several runs.
  const memoRun = queue.map((c) => loaded[c.id].run)[0]

  function startReview() {
    setCurrent((queue.find((c) => !calls[c.id]) ?? queue[0])?.id ?? null)
    go(3)
  }

  function decide(id: string, call: Call) {
    const next = { ...calls, [id]: call }
    setCalls(next)
    const i = queue.findIndex((c) => c.id === id)
    const after = [...queue.slice(i + 1), ...queue.slice(0, i)].find((c) => !next[c.id])
    if (after) { setCurrent(after.id); window.scrollTo({ top: 0 }) } else go(4)
  }

  const watchList = [...queue.filter((c) => loaded[c.id].result.decision !== 'not_applicable' && calls[c.id]?.act === 'approve'), ...(project?.watched ?? [])]

  async function checkApproved() {
    const active = generation.current
    setError(null)
    try {
      const run = await scan(watchList.map((c) => c.id), 700, true)
      if (active !== generation.current) return
      setCheckNote(run.note ?? null)
      setChecked({})
      setChecks((m) => ({ ...m, ...Object.fromEntries(watchList.map((c) => [c.id, { stage: 'queued' as Stage, model: null }])) }))
      follow(run.run_id, watchList.map((c) => c.id), setChecks, (id, r) => setChecked((m) => ({ ...m, [id]: r })))
    } catch (e) { if (active === generation.current) setError((e as Error).message) }
  }

  const sections = project?.specs.map((s) => s.section) ?? []
  const mode = project?.mode ?? 'mock'
  return (
    <div className="min-h-screen font-sans text-sm">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 sm:px-6 md:flex-nowrap">
          <span className="flex h-10 shrink-0 items-center gap-2 font-semibold"><span className="h-3 w-3 rounded-sm bg-flare" />SpecCheck
            {project && <span className="font-normal text-xs text-muted">{mode === 'mock' ? 'Mock' : 'Live'}</span>}
          </span>
          <span className="hidden min-w-0 flex-1 truncate text-muted xl:inline">{project?.name}</span>
          <StepBar step={step} reached={reached} onGo={go} />
          <nav aria-label="Project reference" className="ml-auto flex shrink-0 gap-4 font-mono text-xs text-muted">
            <a href="#specs" className="py-2 hover:text-ink">Specs<span className="hidden xl:inline"> {sections.join(' · ')}</span></a>
            <a href="#scoreboard" className="py-2 hover:text-ink">Scoreboard</a>
            {inbox.length > 0 && <a href="#" className="py-2 hover:text-ink" onClick={(e) => { e.preventDefault(); startOver() }}>Start over</a>}
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1120px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
        {secondary === '#specs' ? <SpecsPage back={STEPS[step - 1][1]} onUse={(checklist) => setChecklists((items) => [...items, checklist])} />
          : secondary === '#scoreboard' ? <ScoreboardPage back={STEPS[step - 1][1]} /> : null}
        <div hidden={secondary === '#specs' || secondary === '#scoreboard'}
          className={secondary === '#specs' || secondary === '#scoreboard' ? undefined : 'contents'}>
        {failed && <p className="text-muted">Couldn't load the project. Check that the API is running, then reload.</p>}
        {!failed && step === 1 && (
          <InboxStep project={project} health={health} inbox={inbox} rows={rows} error={error} onAdd={add} onUpload={upload}
            checklists={checklists} changingSpec={changingSpec} onSpec={changeSpec}
            onRemove={(id) => setInbox((i) => i.filter((c) => c.id !== id))} onScan={() => startScan()} />
        )}
        {step === 2 && <ScanStep items={scanned} rows={rows} loaded={loaded} mode={mode} note={scanNote} error={error} rowOf={rowOf} memoRun={memoRun}
          onRetry={startScan} onReview={startReview} onOpen={(id) => { setCurrent(id); go(3) }} />}
        {step === 3 && (
          <ReviewStep queue={queue} loaded={loaded} calls={calls} drafts={drafts} current={current} mode={mode} rowOf={rowOf}
            onPick={setCurrent} onDecide={decide} onDraft={(id, message) => setDrafts((m) => ({ ...m, [id]: message }))} />
        )}
        {step === 4 && (
          <>
          {checkNote && <p className="text-muted" role="status">{checkNote}</p>}
          <OutcomeStep queue={queue} loaded={loaded} calls={calls} rows={rows} watched={project?.watched ?? []} checks={checks} rowOf={rowOf} memoRun={memoRun}
            checked={checked} requested={requested} error={error} recheck={project?.recheck} onCheck={checkApproved}
            onRequest={(id) => setRequested((m) => ({ ...m, [id]: true }))} />
          </>
        )}
        </div>
      </main>
    </div>
  )
}

function MemoLink({ run }: { run: string }) {
  return <a href={`/memo/${run}`} target="_blank" rel="noreferrer" className="-mt-2 self-start text-muted underline underline-offset-4 hover:text-ink">Package review memo</a>
}

function StepBar({ step, reached, onGo }: { step: Step; reached: Step; onGo: (s: Step) => void }) {
  return (
    <nav aria-label="Steps" className="order-last -ml-2 flex w-full shrink-0 items-center gap-1 overflow-x-auto md:order-none md:w-auto">
      {STEPS.map(([n, label], i) => {
        const on = n === step, done = n < step
        return (
          <Fragment key={n}>
            {i > 0 && <span className={`h-px w-3 shrink-0 sm:w-4 ${n <= reached ? 'bg-edge' : 'bg-line'}`} aria-hidden />}
            <button onClick={() => onGo(n)} disabled={n > reached} aria-current={on ? 'step' : undefined} aria-label={`${n} ${label}${done ? ', done' : ''}`}
              className={`flex h-8 shrink-0 items-center gap-2 rounded-lg px-2.5 disabled:cursor-not-allowed disabled:text-faint ${on ? 'bg-raised font-medium text-ink' : 'text-soft enabled:hover:text-ink'}`}>
              <span className={`flex h-5 w-5 items-center justify-center rounded-full font-mono text-xs ${on ? 'bg-flare text-on-accent' : done ? 'bg-good/15 text-good' : 'bg-line text-faint'}`}>
                {done ? <Icon kind="check" /> : n}
              </span>
              <span className={on ? '' : 'hidden lg:inline'}>{label}</span>
            </button>
          </Fragment>
        )
      })}
    </nav>
  )
}

function Heading({ title, count, children }: { title: string; count: string; children?: ReactNode }) {
  return (
    <section className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <span className="text-muted">{count}</span>
      </div>
      {children}
    </section>
  )
}

function Pill({ d }: { d: Decision }) {
  const c = DECISION_COLOR[d]
  return (
    <span className="inline-flex h-6 shrink-0 items-center rounded-full px-2 text-xs font-semibold"
      style={{ color: c, background: `${c}1f`, boxShadow: `inset 0 0 0 1px ${c}59` }}>{DECISION_LABEL[d]}</span>
  )
}

// A table as a grid, so rows can stack on a phone. cols: the sm+ grid template.
function Table({ cols, head, children }: { cols: string; head: string[]; children: ReactNode }) {
  return (
    <div className="flex flex-col">
      <div className={`hidden h-10 items-center gap-4 border-b border-line px-4 sm:grid ${CAPS}`} style={{ gridTemplateColumns: cols }}>
        {head.map((h, i) => <span key={i}>{h}</span>)}
      </div>
      {children}
    </div>
  )
}

function TableRow({ cols, children }: { cols: string; children: ReactNode }) {
  return (
    <div className="arrive flex flex-col gap-2 border-b border-line px-4 py-3 last:border-b-0 sm:grid sm:items-center sm:gap-4" style={{ gridTemplateColumns: cols }}>
      {children}
    </div>
  )
}

// ---------- 1 · Inbox ----------

function InboxStep({ project, health, inbox, rows, error, checklists, changingSpec, onSpec, onAdd, onUpload, onRemove, onScan }: {
  project: Project | null; health: Health | null; inbox: Case[]; rows: Record<string, Row>; error: string | null
  checklists: SavedChecklist[]; changingSpec: boolean; onSpec: (id: string, spec: string) => void
  onAdd: (id: string) => Promise<void>; onUpload: (f: File[]) => void; onRemove: (id: string) => void; onScan: () => void
}) {
  const [over, setOver] = useState(false)
  const [addingSamples, setAddingSamples] = useState(false)
  const fresh = inbox.filter((c) => !rows[c.id])
  const senders = new Set(fresh.map((c) => c.from ?? 'You')).size
  const count = fresh.length ? `${plural(fresh.length, 'submittal')} from ${plural(senders, 'subcontractor')}, not scanned`
    : inbox.length ? `${plural(inbox.length, 'submittal')}, all scanned` : 'No submittals'
  const inside = new Set(inbox.map((c) => c.id))
  const samples = (project?.tray ?? []).flatMap((g) => g.items).filter((c) => c.ready && !inside.has(c.id))

  function drop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    const id = e.dataTransfer.getData(TRAY_MIME)
    if (id) onAdd(id)
    else onUpload([...e.dataTransfer.files].filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')))
  }
  const browse = (
    <input type="file" multiple accept="application/pdf,.pdf" className="sr-only"
      onChange={(e) => { onUpload([...(e.target.files ?? [])]); e.target.value = '' }} />
  )
  const cols = 'minmax(0,1fr) minmax(0,1.3fr) 140px 40px'

  return (
    <>
      <Heading title="Inbox" count={project ? count : NBSP}>
        <button className={PRIMARY} onClick={onScan} disabled={!fresh.length || changingSpec || addingSamples}>{fresh.length ? `Scan ${plural(fresh.length, 'submittal')}` : 'Scan'}</button>
      </Heading>
      {!inbox.length && <p className="-mt-3 max-w-3xl leading-6 text-muted">SpecCheck checks each submittal against the project spec and the manufacturer's current documents, then writes what to send back and what to forward.</p>}
      {project?.mode === 'mock' && <p className="-mt-3 text-xs text-muted">Mock mode uses fixture answers. No model calls, live web checks or credits spent.</p>}
      {health?.mode === 'live' && (health.budget.usd_left <= 0 || health.budget.credits_left <= 0) && (
        <p className="-mt-3 text-muted" role="status">Today's live budget is spent. Recorded samples can replay; uploads can be checked tomorrow (UTC).</p>
      )}
      <section onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDrop={drop}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(false) }}
        className={`overflow-hidden rounded-xl border border-dashed transition-colors ${over ? 'border-flare bg-flare/5' : 'border-edge'}`}>
        {inbox.length ? (
          <>
            <Table cols={cols} head={['From', 'Attachment', 'Received', '']}>
              {inbox.map((c) => (
                <TableRow key={c.id} cols={cols}>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{c.from ?? 'You'}</span>
                    <span className="truncate text-xs text-muted">{c.trade ?? 'Upload'}</span>
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-mono text-xs text-ink" title={fileName(c)}>{fileName(c)}</span>
                    <span className="text-xs text-muted">{plural(c.pages, 'page')}</span>
                    {c.upload && <label className="mt-1 flex min-w-0 flex-col gap-1 text-xs text-muted">Check against
                      <select aria-label={`Spec for ${fileName(c)}`} value={c.checklist_id ?? c.section}
                        onChange={(e) => onSpec(c.id, e.target.value)} disabled={!!rows[c.id] || !!c.scanned_at || changingSpec}
                        className="w-full min-w-0 rounded-md border border-edge bg-well px-2 py-1 text-ink disabled:opacity-50">
                        {project?.specs.map((s) => <option key={s.section} value={s.section}>{s.title} {s.section}</option>)}
                        {checklists.map((s) => <option key={s.id} value={s.id}>{s.section} {s.title} · unreviewed draft</option>)}
                      </select>
                    </label>}
                  </span>
                  <span className="text-xs text-muted">{c.received}</span>
                  {rows[c.id]
                    ? <span className="text-xs text-faint">Scanned</span>
                    : <button onClick={() => onRemove(c.id)} aria-label={`Remove ${fileName(c)}`}
                        className="flex h-8 w-8 items-center justify-center self-end rounded-md text-muted hover:bg-raised hover:text-ink sm:self-auto">
                        <Icon kind="x" />
                      </button>}
                </TableRow>
              ))}
            </Table>
            <label className="flex h-12 cursor-pointer items-center justify-center gap-1 border-t border-dashed border-edge text-muted hover:text-ink">
              Drop more PDF files here or <span className="underline underline-offset-4">browse</span>{browse}
            </label>
          </>
        ) : (
          <label className="flex min-h-44 cursor-pointer flex-col items-center justify-center gap-1 px-4 text-center">
            <span className="text-base">Drop PDF files here</span>
            <span className="text-muted underline underline-offset-4 hover:text-ink">or browse</span>
            {browse}
          </label>
        )}
        {error && <p className="border-t border-line px-4 py-3 text-bad" role="alert">{error}</p>}
      </section>

      {!inbox.some((c) => c.upload) && <div className="flex flex-col gap-2 text-muted">
        <p>No submittals handy? Try one:</p>
        <ul className="flex flex-col gap-1 text-xs">
          {project?.try?.filter((d) => d.kind === 'product').map((d) => <li key={d.url}>
            <a href={d.url} target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-ink">{d.title} ↗</a> · {d.fits}
          </li>)}
        </ul>
        <a href="#specs" className="self-start underline underline-offset-4 hover:text-ink">or check your own spec →</a>
      </div>}

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="font-semibold">Sample submittals</h2>
          <span className="text-muted">Public manufacturer documents, as two subcontractors would send them. Drag into the inbox.</span>
          <button className="self-start text-muted underline underline-offset-4 enabled:hover:text-ink disabled:opacity-40"
            disabled={addingSamples || !samples.length} onClick={async () => {
              setAddingSamples(true)
              try { await Promise.all(samples.map((c) => onAdd(c.id))) }
              finally { setAddingSamples(false) }
            }}>{addingSamples ? 'Adding samples…' : 'Add all samples'}</button>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {(project?.tray ?? []).map((g) => (
            <div key={g.from} className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-4">
              <span className="truncate"><span className="font-medium">{g.from}</span><span className="text-muted"> · {g.trade}</span></span>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {g.items.map((c) => <Tile key={c.id} c={c} added={inside.has(c.id)} onAdd={onAdd} />)}
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}

function Tile({ c, added, onAdd }: { c: Case; added: boolean; onAdd: (id: string) => void }) {
  const off = added || !c.ready
  return (
    <span title={!c.ready ? 'Available in live mode' : added ? 'In the inbox' : undefined} className="flex min-w-0">
      <button draggable={!off} disabled={off} onClick={() => onAdd(c.id)} aria-label={`Add ${fileName(c)} to the inbox`}
        onDragStart={(e) => { e.dataTransfer.setData(TRAY_MIME, c.id); e.dataTransfer.effectAllowed = 'copy' }}
        className="flex w-full min-w-0 items-start gap-3 rounded-lg border border-line bg-well p-3 text-left enabled:cursor-grab enabled:hover:border-edge disabled:cursor-not-allowed disabled:opacity-40">
        <PdfIcon />
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate font-medium text-ink">{c.product}</span>
          <span className="truncate font-mono text-xs text-soft" title={fileName(c)}>{fileName(c)}</span>
          <span className="truncate text-xs text-muted">{c.number} · {KIND[c.submittal[0]?.role ?? ''] ?? 'Document'}</span>
        </span>
      </button>
    </span>
  )
}

function PdfIcon() {
  return (
    <svg width="20" height="24" viewBox="0 0 20 24" fill="none" aria-hidden className="mt-0.5 shrink-0">
      <path d="M2 1.5h11l5 5v16H2z" stroke="var(--color-edge)" strokeWidth="1.25" fill="var(--color-panel)" />
      <path d="M13 1.5v5h5" stroke="var(--color-edge)" strokeWidth="1.25" />
      <rect x="4" y="14" width="12" height="6" rx="1" fill="var(--color-bad)" />
      <text x="10" y="18.6" textAnchor="middle" fontSize="4.6" fontWeight="700" fill="#fff" fontFamily="ui-sans-serif, system-ui">PDF</text>
    </svg>
  )
}

function Icon({ kind }: { kind: 'x' | 'check' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden className="shrink-0">
      <path d={kind === 'x' ? 'm4 4 8 8M12 4l-8 8' : 'm3.5 8.5 3 3 6-7'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ---------- 2 · Scan ----------

function ScanStep({ items, rows, loaded, mode, note, error, rowOf, memoRun, onRetry, onReview, onOpen }: {
  items: Case[]; rows: Record<string, Row>; loaded: Record<string, Loaded>; mode: Project['mode']; note: string | null; error: string | null
  rowOf: (id: string) => PackageRow | undefined; memoRun?: string; onRetry: (id: string) => void; onReview: () => void; onOpen: (id: string) => void
}) {
  const failed = items.filter((c) => rows[c.id]?.stage === 'error').length
  const done = items.filter((c) => loaded[c.id]).length + failed
  const complete = items.length > 0 && done === items.length
  const n = (...ds: Decision[]) => items.filter((c) => ds.includes(loaded[c.id]?.result.decision as Decision)).length
  const matrix = items.map((c) => rowOf(c.id)).filter((r): r is PackageRow => !!r)
  const manual = matrix.filter((r) => r.manual_review_suggested).length
  const count = complete
    ? [`${n('send_back')} to send back`, `${n('approve', 'approve_with_note')} to approve`, ...(n('not_applicable') ? [`${n('not_applicable')} not checked`] : []),
      ...(manual ? [`${manual} worth a manual look`] : []), ...(failed ? [`${failed} couldn't scan`] : [])].join(' · ')
    : `${done} of ${items.length} done`
  const cols = '112px minmax(0,1fr) minmax(0,1.2fr)'
  // What the scan spent, summed over the results so far: the models by name, tokens, Tavily credits, cost, wall time.
  const results = items.map((c) => loaded[c.id]?.result).filter((r): r is Result => Boolean(r))
  const usage = results.flatMap((r) => r.usage)
  const models = byModel(usage).map((g) => modelName(g.model))
  const { tokens, cost } = totals(usage)
  const credits = results.reduce((s, r) => s + r.web_credits, 0)
  const longest = Math.max(0, ...results.map((r) => r.duration_ms))
  const allMock = results.every((r) => r.mode === 'mock')
  const anyMock = results.some((r) => r.mode === 'mock')
  return (
    <>
      <Heading title={complete ? 'Scan complete' : 'Scanning'} count={mode === 'mock' ? `${count} · mock` : count}>
        {complete && <button className={PRIMARY} onClick={onReview} disabled={!items.some((c) => loaded[c.id])}>Start review</button>}
      </Heading>
      {note && <p className="-mt-3 text-muted" role="status">{note}</p>}
      {error && <p className="text-bad" role="alert">{error}</p>}
      {complete && results.length > 0 && (
        <p className="-mt-3 text-xs leading-5 text-muted">
          {allMock ? `Fixture answers for ${models.join(' and ')} cover ${plural(results.length, 'submittal')}`
            : anyMock ? `${plural(results.length, 'submittal')} checked with live and fixture answers for ${models.join(' and ')}`
            : `${models.join(' and ')} on Nebius Token Factory read ${plural(results.length, 'submittal')}`}
          {credits > 0 ? allMock ? `; Tavily fixtures account for ${credits} estimated credits`
            : anyMock ? `; ${credits} Tavily credits include mock estimates` : `; Tavily checked the manufacturers' sites (${credits} credits)` : ''}.
          {' '}{kTokens(tokens)} tokens · {money(cost)} model cost · {seconds(longest)} for the longest item
          {allMock ? ' · estimated counts and cost; no provider calls' : anyMock ? ' · includes estimated counts and cost' : ''}
          {!anyMock && usage.some((u) => u.cached) && ' · includes cached usage; cached cost and credits are usage equivalents, not fresh charges'}
          {results.some((r) => r.replayed_from) ? ' · replayed items show their original usage and time' : ''}
          {' · '}<a href="#scoreboard" className="underline underline-offset-4 hover:text-ink">Scoreboard</a>
        </p>
      )}
      {complete && matrix.length > 0 && <PackageMatrix rows={matrix} onOpen={onOpen}
        decision={(r) => <><Pill d={r.decision} /><span className="text-xs text-muted">{r.stamp}</span></>} />}
      {complete && memoRun && <MemoLink run={memoRun} />}
      {(!complete || matrix.length < items.length) && <section className="rounded-xl border border-line">
        <Table cols={cols} head={['Number', 'Submittal', 'Result']}>
          {items.filter((c) => !complete || !rowOf(c.id)).map((c) => {
            const r = rows[c.id]
            const l = loaded[c.id]
            const [label, at] = STAGE[r.stage] ?? ['Queued', 0]
            return (
              <TableRow key={c.id} cols={cols}>
                <span className="font-mono text-xs text-muted">{c.number ?? 'Upload'}</span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate">{c.title}</span>
                  <span className="truncate text-xs text-muted">{[c.product, c.from ?? 'You'].filter(Boolean).join(' · ')}</span>
                </span>
                {r.stage === 'error' ? <span className="flex flex-col items-start gap-1">
                    <span className="text-bad" role="alert">{r.reason ?? "Couldn't scan this one"}</span>
                    <button className="min-h-8 rounded px-2 text-soft underline underline-offset-4 hover:text-ink"
                      onClick={() => onRetry(c.id)} aria-label={`Retry ${c.title}`}>Retry</button>
                  </span>
                  : l ? (
                    <span className="flex min-w-0 flex-col items-start gap-1">
                      <Pill d={l.result.decision} />
                      <span className="w-full truncate text-xs text-muted" title={reviewSummary(l.result)}>{reviewSummary(l.result)}</span>
                    </span>
                  ) : (
                    <span className="flex min-w-0 flex-col gap-2">
                      <span className="flex justify-between gap-3 text-xs">
                        <span className="truncate text-soft">{label}</span>
                        <span className="shrink-0 font-mono text-faint">{modelTag(r.model)}</span>
                      </span>
                      <span className="h-0.5 rounded-full bg-line">
                        <span className="block h-0.5 rounded-full bg-flare transition-[width] duration-500" style={{ width: `${at * 100}%` }} />
                      </span>
                    </span>
                  )}
              </TableRow>
            )
          })}
        </Table>
      </section>}
    </>
  )
}

// ---------- 3 · Review ----------

function ReviewStep({ queue, loaded, calls, drafts, current, mode, rowOf, onPick, onDecide, onDraft }: {
  queue: Case[]; loaded: Record<string, Loaded>; calls: Record<string, Call>; current: string | null; mode: Project['mode']
  drafts: Record<string, string>; rowOf: (id: string) => PackageRow | undefined; onPick: (id: string) => void
  onDecide: (id: string, call: Call) => void; onDraft: (id: string, message: string) => void
}) {
  const c = queue.find((q) => q.id === current) ?? queue[0]
  if (!c) return <Heading title="Review" count="Nothing to review" />
  const i = queue.indexOf(c)
  const row = rowOf(c.id)
  return (
    <>
      <Heading title="Review" count={`${Object.keys(calls).filter((id) => queue.some((q) => q.id === id)).length} of ${queue.length} decided`} />
      <div className="-mt-2 flex gap-1" role="group" aria-label="Submittals">
        {queue.map((q) => (
          <button key={q.id} onClick={() => onPick(q.id)} aria-current={q.id === c.id ? 'true' : undefined}
            aria-label={`${q.number ?? q.title}${calls[q.id] ? ', decided' : ''}`} title={`${q.number ?? ''} ${q.title}`}
            className="flex h-6 flex-1 items-center">
            <span className={`block h-1 w-full rounded-full ${q.id === c.id ? 'bg-flare' : calls[q.id] ? 'bg-muted' : 'bg-line'}`} />
          </button>
        ))}
      </div>
      {row ? <Reviewing key={c.id} c={c} at={i + 1} of={queue.length} l={loaded[c.id]} row={row} call={calls[c.id]} mode={mode}
        messageDraft={drafts[c.id]} onDraft={(message) => onDraft(c.id, message)} onDecide={(call) => onDecide(c.id, call)} />
        : <p className="text-muted" role="status">Loading the package view for this run…</p>}
    </>
  )
}

const TONE_COLOR: Record<Tone, string> = { red: '#e5534b', amber: '#e5a93b', blue: '#7fa7d9', green: '#2e9e68' }
const TONE_RANK: Record<Tone, number> = { red: 0, amber: 1, blue: 2, green: 3 }
const SEVERITY_RANK: Record<Finding['severity'], number> = { critical: 0, major: 1, minor: 2, info: 3 }
const toneOf = (f: Finding): Tone =>
  f.verdict === 'pass' ? 'green' : f.verdict === 'fail' ? 'red' : f.verdict === 'outdated' ? 'amber' : 'blue'
const WEB = new Set(['currency', 'status'])
// Rows a reviewer has to act on: failures, an old or newer sheet, an option to specify, a major gap in the evidence.
const needsAction = (f: Finding) => ['fail', 'outdated', 'note'].includes(f.verdict) || !!f.configure?.length
  || (['unverified', 'pending'].includes(f.verdict) && ['critical', 'major'].includes(f.severity))
const ACT_SAVED: Record<Act, string> = { return: 'return decision', approve: 'approval decision', not_checked: 'not checked', manual: 'flagged for manual review' }

function reviewSummary(r: Result): string {
  if (r.validity && r.validity !== 'legacy') return r.summary
  return 'Historical result. Evidence coverage has not been evaluated under the current review rules.'
}

// Web checks as rows of the one check table: Required is what the maker publishes today.
const WEB_LABEL: Record<string, string> = { 'status-discontinued': 'Product status' }
function webRows(f: Finding): CheckRow[] {
  if (f.verdict === 'unverified') return [[f, `Couldn't confirm ${f.check === 'status' ? 'product status' : 'current sheet'}`, f.compare?.right_value, f.compare?.left_value]]
  if (f.compare?.rows.length) return f.compare.rows.map((r: CompareRow): CheckRow => [f, r.label, `Current: ${r.current ?? '—'}`, r.submitted])
  if (f.id === 'status-discontinued') return [[f, WEB_LABEL[f.id], 'In production', f.compare?.right_value]]
  if (f.id === 'status-active') return [[f, 'Product status', 'In production', f.compare?.right_value]]
  const now = f.compare?.right_value
  const current = f.verdict === 'pass' && (now === 'unknown' || !now) ? 'Same values as current' : `Current: ${show(now)}`
  return [[f, 'Data sheet version', current, f.compare?.left_value]]
}
const checkRows = (fs: Finding[]): CheckRow[] => fs.flatMap((f) => WEB.has(f.check) ? webRows(f) : [[f, f.title, f.compare?.left_value, f.compare?.right_value] as CheckRow])

function Reviewing({ c, at, of, l, row, call, mode, messageDraft, onDraft, onDecide }: {
  c: Case; at: number; of: number; l: Loaded; row: PackageRow; call?: Call; mode: Project['mode']; onDecide: (call: Call) => void
  messageDraft?: string; onDraft: (message: string) => void
}) {
  const { result, docs, text } = l
  // Worst first: must fix, then out of date, then notes and couldn't-confirm.
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass' && f.verdict !== 'not_applicable')
    .sort((a, b) => TONE_RANK[toneOf(a)] - TONE_RANK[toneOf(b)] || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]), [result])
  // A discontinued product's ordering options are moot, as in the package row.
  const acts = (f: Finding) => needsAction(f) && !(row.still_made === 'discontinued' && f.configure?.length)
  const acting = issues.filter(acts)
  const minor = issues.filter((f) => !acts(f))
  const met = result.findings.filter((f) => f.verdict === 'pass')
  const marks: Placed[] = useMemo(() => result.findings.flatMap((f) =>
    f.highlights.map((h) => ({ ...h, finding: f, tone: h.kind === 'checked' ? 'green' as Tone : toneOf(f) }))), [result])
  const first = acting.find((f) => firstMark(f)) ?? issues.find((f) => firstMark(f)) ?? issues[0]
  const [textPage, setTextPage] = useState(() => (first && firstMark(first)?.page) || 1)
  const fix = fixOf(result)
  const notApplicable = result.decision === 'not_applicable'
  const rec: Act = notApplicable ? 'not_checked' : result.decision === 'send_back' ? 'return' : 'approve'
  const who = c.from ?? 'sender'
  const draft = (a: Act) => a === 'return' ? row.return_note : row.approval_note
  const [message, setMessage] = useState(messageDraft ?? (call?.act === rec ? call.message : draft(rec)))
  const otherTypes = result.findings.filter((f) => f.verdict === 'not_applicable' && f.product_type && f.detail.startsWith('For other product type:'))
  const source = result.findings.filter((f) => WEB.has(f.check)).flatMap((f) => f.evidence)[0]
  const sortRows = (rs: CheckRow[]) => rs.sort((x, y) => TONE_RANK[toneOf(x[0])] - TONE_RANK[toneOf(y[0])])

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_440px]">
      <section className="order-2 flex min-w-0 flex-col gap-3 lg:order-1 lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:self-start">
        {docs
          ? <PdfPages caseId={result.case_id} docs={docs} marks={marks} selId={first?.id ?? null} result={result} href={c.submittal[0]?.url} />
          : <TextPages pages={text ?? []} marks={marks} selId={first?.id ?? null} result={result} page={textPage} onPage={setTextPage}
              name={fileName(c)} href={c.submittal[0]?.url} product={c.product} />}
      </section>

      <aside className="order-1 flex min-w-0 flex-col gap-5 lg:order-2">
        <div className="flex flex-col gap-2">
          <span className="text-xs text-muted"><span className="font-mono">{c.number ?? 'Upload'}</span> · from {c.from ?? 'you'} · {at} of {of}</span>
          <h2 className="text-lg font-semibold leading-tight">{c.title}</h2>
          <span className="flex flex-wrap items-center gap-2"><Pill d={result.decision} />
            <span className="text-xs text-muted">{row.stamp}</span>
            {call && <span className="text-xs text-muted">· Saved: {ACT_SAVED[call.act]}</span>}</span>
          <p className="text-base text-soft">{notApplicable
            ? `None of the ${result.spec_rule_count ?? result.findings.length} rules in ${result.spec_title ?? c.section} found a value in this document. Pick a different spec for it in the Inbox.`
            : reviewSummary(result)}</p>
          {result.checklist_id && <p className="text-muted">Checked against your draft checklist {result.spec_section} {result.spec_title} ({result.spec_rule_count} rules, unreviewed). Drafted by Nemotron 3 Super · edited by you · unreviewed · this browser only.</p>}
        </div>

        {!notApplicable && <SummaryCounters result={result} />}

        {!notApplicable && <div className="flex flex-col gap-2 rounded-xl border border-line bg-panel p-4">
          <span className={CAPS}>What to send</span>
          {row.what_to_send.length ? <ol className="flex flex-col gap-2 text-base">{row.what_to_send.map((t, n) => (
            <li key={t} className="flex gap-3"><span className="font-mono text-muted">{n + 1}</span><span>{t}</span></li>))}</ol>
            : <p className="text-base text-soft">Nothing. Forward as submitted.</p>}
        </div>}

        {row.still_made !== 'discontinued' && <ConfigureLines findings={result.findings} />}
        {fix && (result.decision === 'send_back' || row.still_made === 'discontinued') && <AlternatesCard fix={fix} />}

        {(acting.length > 0 || met.length > 0 || minor.length > 0) && <div className="flex flex-col gap-2">
          {acting.length > 0 && <Checks head={['Needs action', 'Required', 'Submitted']} rows={sortRows(checkRows(acting))} />}
          {met.length > 0 && <details className="text-muted">
            <summary className="cursor-pointer">{plural(met.length, 'requirement')} met ✓</summary>
            <div className="mt-2"><Checks head={['Check', 'Required', 'Submitted']} rows={checkRows(met)} /></div>
          </details>}
          {minor.length > 0 && <details className="text-muted">
            <summary className="cursor-pointer">{plural(minor.length, 'minor item')} couldn't be confirmed</summary>
            <div className="mt-2"><Checks head={['Check', 'Required', 'Submitted']} rows={checkRows(minor)} /></div>
          </details>}
          {otherTypes.length > 0 && <details className="text-muted">
            <summary className="cursor-pointer">{otherTypes.length} rules for other product types</summary>
            <ul className="mt-2 flex flex-col gap-2 text-xs">{otherTypes.map((f) =>
              <li key={f.id}>{f.product_type?.replace(/_/g, ' ')}: {f.title} · {f.spec_ref}</li>)}</ul>
          </details>}
        </div>}

        <details className="text-muted">
          <summary className="cursor-pointer">How this was checked</summary>
          <div className="mt-2 flex flex-col gap-2">
            <span className="text-xs leading-5">
              Sources: spec {c.section}{result.document_revision ? ` · submitted sheet ${result.document_revision}` : ''}
              {source && <> · <a href={source.url} target="_blank" rel="noreferrer" className="underline decoration-edge underline-offset-2 hover:text-ink">{source.title || hostOf(source.url)} ↗</a></>}
              {source?.archived_path && <> · <a href={archiveUrl(source.archived_path)} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink">archived copy</a></>}
              {result.product_type && ` · product type: ${result.product_type.replace(/_/g, ' ')}`}
            </span>
            <Trace result={result} mode={mode} />
          </div>
        </details>

        {notApplicable ? <div className="flex flex-col gap-3">
          <p className="text-muted">Upload this document again in the Inbox to choose another spec before scanning.</p>
          <button className={`${PRIMARY} self-start`} onClick={() => onDecide({ act: 'not_checked', message: '' })}>Mark as not checked</button>
        </div> : <div className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-4">
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <label htmlFor="message" className={CAPS}>{rec === 'return' ? `Draft for ${who}` : 'Draft for architect'}</label>
            {rec === 'return' && c.email && <span className="font-mono text-xs text-muted">{c.email}</span>}
          </span>
          <textarea id="message" rows={8} value={message} onChange={(e) => { setMessage(e.target.value); onDraft(e.target.value) }}
            className="resize-y rounded-lg border border-line bg-well p-3 leading-relaxed text-ink" />
          <p className="text-xs text-muted">Decisions and drafts stay in this browser. No email is sent.</p>
          <div className="flex flex-wrap gap-2">
            {rec === 'return' ? (
              <>
                <button className={PRIMARY} onClick={() => onDecide({ act: 'return', message })}>Save return decision</button>
                <button className="btn" onClick={() => onDecide({ act: 'approve', message: draft('approve') })}>Save approval</button>
              </>
            ) : (
              <>
                <button className={PRIMARY} onClick={() => onDecide({ act: 'approve', message })}>Save approval decision</button>
                <button className="btn" onClick={() => onDecide({ act: 'return', message: draft('return') })}>Save return</button>
              </>
            )}
            <button className="btn" onClick={() => onDecide({ act: 'manual', message })}>Flag for manual review</button>
          </div>
        </div>}
      </aside>
    </div>
  )
}

type CheckRow = [Finding, string, Value | undefined, Value | undefined]

// How this item was checked: each Nemotron model and what it did, Tavily's part, and that code made every call.
// One muted line; the per-call table is behind a disclosure. All of it is the usage the result already carries.
function Trace({ result, mode }: { result: Result; mode: Project['mode'] }) {
  mode = result.mode ?? mode
  const groups = byModel(result.usage)
  const sources = new Set(result.findings.flatMap((f) => f.evidence.map((e) => e.url))).size
  const { tokens, cost } = totals(result.usage)
  const cached = result.usage.length > 0 && result.usage.every((u) => u.cached)
  if (!groups.length) return null
  return (
    <details className="group text-xs leading-5 text-muted">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <span className="text-faint">{mode === 'mock' ? 'Mock fixtures for ' : 'Checked by '}</span>
        {groups.map((g, i) => (
          <Fragment key={g.model}>
            {i > 0 && (i === groups.length - 1 ? ' and ' : ', ')}
            <span className="text-soft">{modelName(g.model)}</span> ({g.tasks.join(', ')})
          </Fragment>
        ))}
        {mode === 'live' && <span className="text-faint"> on Nebius Token Factory</span>}
        {result.web_credits > 0 && <> · <span className="text-soft">Tavily</span>{mode === 'mock' ? ' fixture evidence cites ' : ' evidence cites '}{plural(sources, 'source')}</>}
        {' · verdicts by code'}
        {result.spec_rule_count != null && ` · checked against ${result.spec_section}: ${result.spec_match_count} of ${result.spec_rule_count} rules matched`}
        {result.checklist_id && ` · your draft checklist ${result.spec_section} ${result.spec_title} (${result.spec_rule_count} rules, unreviewed)`}
        {!!result.ocr_pages && ` · ${plural(result.ocr_pages, 'page')} scanned → OCR (Tesseract), ${mode === 'mock' ? 'mock reading by' : 'read by'} Nemotron 3 Super`}
        {result.investigation && ` · investigated in ${plural(result.investigation.steps.length, 'step')}`}
        {result.replayed_from && ' · replayed'}
        {result.evidence_label && ` · archived to ${result.evidence_label}`}
        <span className="text-faint"> · {mode === 'mock' ? 'estimated ' : ''}{kTokens(tokens)} tokens · {money(cost)} {mode === 'live' && result.usage.some((u) => u.cached) ? 'equivalent model cost' : 'model cost'} · {seconds(result.duration_ms)}</span>
        <span className="ml-1 text-faint underline decoration-edge underline-offset-2 group-open:hidden">every call</span>
      </summary>
      <div className="mt-2 overflow-hidden rounded-lg border border-line">
        {result.warnings?.map((warning) => <p key={warning} className="border-b border-line px-3 py-2">{warning}</p>)}
        {result.investigation && (
          <div className="border-b border-line px-3 py-2">
            <p className="text-soft">Investigation · {result.investigation.outcome === 'found' ? 'quotes confirmed'
              : result.investigation.outcome === 'capped' ? "limit reached; couldn't confirm" : "couldn't confirm"}</p>
            <ol className="mt-1 space-y-1 break-words">
              {result.investigation.steps.map((s) => <li key={s.n}>{investigationLine(s)}</li>)}
            </ol>
          </div>
        )}
        <div className={`grid h-8 items-center gap-3 border-b border-line bg-well px-3 ${CAPS}`} style={{ gridTemplateColumns: '1.1fr 1.5fr 0.5fr 0.5fr 0.55fr 0.65fr' }}>
          <span>Call</span><span>Model</span><span className="text-right">In</span><span className="text-right">Out</span><span className="text-right">Time</span><span className="text-right">Cost</span>
        </div>
        {result.usage.map((u, i) => (
          <div key={i} className="grid items-center gap-3 border-b border-line px-3 py-1.5 last:border-b-0" style={{ gridTemplateColumns: '1.1fr 1.5fr 0.5fr 0.5fr 0.55fr 0.65fr' }}>
            <span className="truncate text-soft">{taskLabel(u.task)}</span>
            <span className="truncate font-mono" title={u.model}>{modelName(u.model)}{u.thinking === 'off' ? '' : u.thinking ? ` · thinking ${u.thinking}` : ''}</span>
            <span className="text-right font-mono">{kTokens(u.input_tokens)}</span>
            <span className="text-right font-mono">{kTokens(u.output_tokens)}</span>
            <span className="text-right font-mono">{u.cached && mode === 'live' ? 'cached' : seconds(u.latency_ms)}</span>
            <span className="text-right font-mono">{money(u.cost_usd)}</span>
          </div>
        ))}
        <p className="border-t border-line px-3 py-1.5 text-faint">
          {result.replayed_from
            ? `Replayed from ${result.replayed_from.slice(0, 4)}-${result.replayed_from.slice(4, 6)}-${result.replayed_from.slice(6, 8)}; usage and time belong to the original ${mode} run. No new provider calls.`
            : mode === 'live'
            ? cached ? `Live mode: model calls used cached answers from an earlier live run. Tavily used ${result.web_credits} credits this time.`
              : 'Live mode: real calls to NVIDIA Nemotron 3 on Nebius Token Factory and to Tavily. Repeats are cached.'
            : 'Mock mode: fixture answers, no API calls; token counts are estimated from text length.'}
          {' '}Models read and quote; every pass/fail is computed in code from the quoted values.
          {mode === 'live' && result.usage.some((u) => u.cached) && ' Cached rows show original token usage and equivalent cost; they are not billed again.'}
        </p>
      </div>
    </details>
  )
}

function investigationLine(s: Investigation['steps'][number]) {
  if (s.tool === 'finish') return `finish: ${s.summary}`
  const domains = Array.isArray(s.args.include_domains) ? ` (${s.args.include_domains.join(', ')})` : ''
  const target = s.tool === 'search' ? `"${String(s.args.query ?? '')}"${domains}`
    : String(s.args.url ?? '').replace(/^https?:\/\/(www\.)?/, '')
  return `${s.tool} ${target} → ${s.summary}`
}

function Checks({ head, rows }: { head: string[]; rows: CheckRow[] }) {
  const cols = 'minmax(0,1.1fr) minmax(0,1fr) minmax(0,1fr)'
  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className={`grid h-9 items-center gap-3 border-b border-line bg-well px-3 ${CAPS}`} style={{ gridTemplateColumns: cols }}>
        {head.map((h) => <span key={h}>{h}</span>)}
      </div>
      {rows.map(([f, label, a, b], i) => (
        <div key={`${f.id}-${i}`} className="grid items-baseline gap-3 border-b border-line px-3 py-2 last:border-b-0" style={{ gridTemplateColumns: cols }}>
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="h-2 w-2 shrink-0 translate-y-[-1px] rounded-full" style={{ background: TONE_COLOR[toneOf(f)] }} aria-hidden />
            <span className="min-w-0 break-words">{label}{f.spec_ref && <span className="block text-xs text-muted">{f.spec_ref}</span>}</span>
          </span>
          <span className="min-w-0 break-words text-muted">{show(a)}</span>
          <span className="min-w-0 break-words" style={{ color: f.verdict === 'pass' ? undefined : TONE_COLOR[toneOf(f)] }}>{show(b)}</span>
        </div>
      ))}
    </div>
  )
}

// ---------- the document, with findings drawn on it ----------

type Placed = Mark & { finding: Finding; tone: Tone }
type PdfPage = { key: string; file: string; n: number; width: number; height: number }

const pageKey = (file: string | null, n: number | null) => `${file}#${n}`
// A finding's page: the first claim that was located, else the first claim with a page.
const firstMark = (f: Finding) => f.highlights.find((h) => h.boxes.length) ?? f.highlights.find((h) => h.page)

function worstTone(ms: Placed[]): Tone | undefined {
  return ms.map((m) => m.tone).sort((a, b) => TONE_RANK[a] - TONE_RANK[b])[0]
}

// "now 17.5 W · 86.4 lm/W": one label per problem finding on a page, under its leftmost box.
function callouts(ms: Placed[], result: Result) {
  const by = new Map<string, Placed[]>()
  for (const m of ms) if (m.kind === 'problem') by.set(m.finding.id, [...(by.get(m.finding.id) ?? []), m])
  return [...by.values()].flatMap((group) => {
    const rows = group.map((m) => changedRow(result, m.claim_id)).filter((r): r is CompareRow => !!r)
    const boxes = group.flatMap((m) => m.boxes)
    if (!rows.length || !boxes.length) return []
    return [{ finding: group[0].finding, x: Math.min(...boxes.map((b) => b.x0)), y: Math.max(...boxes.map((b) => b.y1)),
      text: [...new Set(rows.map((r) => r.current))].join(' · '), color: TONE_COLOR[group[0].tone] }]
  })
}

function changedRow(result: Result, claimId: string): CompareRow | undefined {
  const claim = result.claims.find((c) => c.id === claimId)
  return claim && result.comparison.find((r) => r.property === claim.property && r.changed)
}

function DocHeader({ name, page, pages, href, children }: { name: string; page: number; pages: number; href?: string; children?: ReactNode }) {
  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-1">
      <span className="flex min-w-0 items-baseline gap-3">
        <span className="truncate font-mono text-xs text-ink" title={name}>{name}</span>
        <span className="shrink-0 text-xs text-muted">Page {page} of {pages}</span>
      </span>
      <span className="flex items-center gap-3">
        {children}
        {href && <a href={href} target="_blank" rel="noreferrer" className="text-xs text-muted underline decoration-edge underline-offset-2 hover:text-ink">Open original ↗</a>}
      </span>
    </div>
  )
}

// Real PDF pages in a scrolling column, every located claim drawn over them, opened at the first problem.
const PdfPages = forwardRef<{ scrollTo: (key: string) => void }, {
  caseId: string; docs: DocPages[]; marks: Placed[]; selId: string | null; result: Result; href?: string
}>(function PdfPages({ caseId, docs, marks, selId, result, href }, ref) {
  const pages: PdfPage[] = docs.flatMap((d) => d.pages.map((s, i) => ({ key: pageKey(d.file, i + 1), file: d.file, n: i + 1, ...s })))
  const sel = marks.find((p) => p.finding.id === selId && p.boxes.length) ?? marks.find((p) => p.finding.id === selId && p.page)
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
    if (box.scrollHeight > box.clientHeight + 1) box.scrollTo({ top: el.offsetTop - 4, behavior: 'smooth' })
    else el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  useImperativeHandle(ref, () => ({ scrollTo }))
  useEffect(() => { // open at the first problem's page
    if (sel) requestAnimationFrame(() => {
      const el = refs.current[pageKey(sel.doc_file, sel.page)], box = scroller.current
      if (el && box && box.scrollHeight > box.clientHeight + 1) box.scrollTop = el.offsetTop - 4
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const name = docs.find((d) => pageKey(d.file, 1).split('#')[0] === at?.split('#')[0])?.name ?? docs[0]?.name ?? ''
  return (
    <>
      <DocHeader name={name} page={pages.findIndex((p) => p.key === at) + 1} pages={pages.length} href={href}>
        {pages.length > 1 && (
          <nav className="flex gap-1 font-mono text-xs" aria-label="Pages">
            {pages.map((p, i) => {
              const t = worstTone(byPage[p.key] ?? [])
              return (
                <button key={p.key} onClick={() => scrollTo(p.key)} aria-current={p.key === at ? 'page' : undefined} aria-label={`Page ${i + 1}`}
                  className={`h-6 min-w-6 rounded px-1 tabular-nums ${p.key === at ? 'bg-selected text-ink' : 'text-faint hover:text-ink'}`}
                  style={{ boxShadow: t ? `inset 0 -2px 0 ${TONE_COLOR[t]}` : undefined }}>{i + 1}</button>
              )
            })}
          </nav>
        )}
      </DocHeader>
      <div ref={scroller} className="relative flex max-h-[75vh] min-h-0 flex-1 flex-col gap-4 overflow-y-auto rounded lg:max-h-none">
        {pages.map((p) => (
          <div key={p.key} ref={(el) => { refs.current[p.key] = el }}
            className="relative w-full shrink-0 overflow-hidden rounded-sm bg-white shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)]"
            style={{ aspectRatio: `${p.width} / ${p.height}` }}>
            <img src={pageUrl(caseId, p.file, p.n)} alt={`Page ${p.n}`} decoding="async" className="absolute inset-0 h-full w-full" />
            {/* checked first so problems draw on top; the first problem last of all */}
            {[...(byPage[p.key] ?? [])]
              .sort((a, b) => Number(a.kind === 'problem') - Number(b.kind === 'problem') || Number(a.finding.id === selId) - Number(b.finding.id === selId))
              .map((m) => m.boxes.map((b, i) => {
                const on = m.finding.id === selId
                const c = TONE_COLOR[m.tone]
                return (
                  <div key={`${m.finding.id}-${m.claim_id}-${i}`} title={`${m.kind === 'checked' ? 'Checked' : 'Problem'}: ${m.finding.title}`}
                    className="absolute rounded-[2px]"
                    style={{
                      left: `calc(${b.x0 * 100}% - 2px)`, top: `calc(${b.y0 * 100}% - 2px)`,
                      width: `calc(${(b.x1 - b.x0) * 100}% + 4px)`, height: `calc(${(b.y1 - b.y0) * 100}% + 4px)`,
                      background: `${c}${on ? '38' : m.kind === 'checked' ? '1a' : '22'}`,
                      outline: `${on ? 2 : 1}px solid ${c}${on ? '' : m.kind === 'checked' ? '66' : '99'}`,
                    }} />
                )
              }))}
            {callouts(byPage[p.key] ?? [], result).map(({ finding, x, y, text, color }) => (
              <span key={finding.id} className="absolute z-10 whitespace-nowrap rounded px-2 py-1 text-xs font-semibold text-on-accent shadow"
                style={{ left: `${x * 100}%`, top: `calc(${y * 100}% + 5px)`, background: color }}>now {text}</span>
            ))}
          </div>
        ))}
      </div>
    </>
  )
})

// Fallback when the PDF is not downloaded: a page-style excerpt of the recorded text, only the lines around each
// finding, each marked. PDF text is cleaned first: letter-per-line headings are joined, "Label:" lines meet their value.
const squash = (t: string) => t.replace(/\s+/g, ' ').trim().toLowerCase()

function cleanLines(text: string): string[] {
  const out: string[] = []
  let letters = ''
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (line.length <= 1) { letters += line || ' '; continue }
    if (letters.trim()) out.push(letters.replace(/\s+/g, ' ').trim())
    letters = ''
    out.push(line.replace(/\s+/g, ' '))
  }
  if (letters.trim()) out.push(letters.replace(/\s+/g, ' ').trim())
  const merged: string[] = []
  for (let i = 0; i < out.length; i++) {
    const next = out[i + 1]
    if (out[i].endsWith(':') && next && next.length <= 48 && !next.endsWith(':')) { merged.push(`${out[i]} ${next}`); i++ }
    else merged.push(out[i])
  }
  return merged
}

function TextPages({ pages, marks, selId, result, page, onPage, name, href, product }: {
  pages: TextPage[]; marks: Placed[]; selId: string | null; result: Result; page: number; onPage: (n: number) => void
  name: string; href?: string; product?: string
}) {
  const current = pages.find((p) => p.page === page) ?? pages[0]
  const lines = useMemo(() => cleanLines(current?.text ?? ''), [current])
  // Each marked line: the worst mark on it (problems over checked, the selected finding over the rest).
  const hit = new Map<number, Placed>()
  for (const m of marks.filter((x) => x.page === current?.page && x.quote)) {
    const q = squash(m.quote!)
    let i = lines.findIndex((l) => squash(l).includes(q))
    if (i < 0 && q.length > 24) i = lines.findIndex((l) => squash(l).includes(q.slice(0, 24)))
    if (i < 0) continue
    const had = hit.get(i)
    const rank = (x: Placed) => (x.kind === 'problem' ? 2 : 0) + (x.finding.id === selId ? 1 : 0)
    if (!had || rank(m) > rank(had)) hit.set(i, m)
  }
  const keep = new Set<number>()
  for (const i of hit.keys()) for (let k = i - 2; k <= i + 2; k++) if (k >= 0 && k < lines.length) keep.add(k)
  if (!keep.size) lines.slice(0, 14).forEach((_, k) => keep.add(k))
  const shown = [...keep].sort((x, y) => x - y)

  return (
    <>
      <DocHeader name={name} page={current?.page ?? 1} pages={pages.length} href={href}>
        {pages.length > 1 && (
          <nav className="flex gap-1 font-mono text-xs" aria-label="Pages">
            {pages.map((p) => {
              const t = worstTone(marks.filter((m) => m.page === p.page))
              return (
                <button key={p.page} onClick={() => onPage(p.page)} aria-current={p.page === current?.page ? 'page' : undefined}
                  className={`h-6 min-w-6 rounded px-1 tabular-nums ${p.page === current?.page ? 'bg-selected text-ink' : 'text-faint hover:text-ink'}`}
                  style={{ boxShadow: t ? `inset 0 -2px 0 ${TONE_COLOR[t]}` : undefined }}>{p.page}</button>
              )
            })}
          </nav>
        )}
      </DocHeader>
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto rounded-xl bg-well p-4 sm:p-8">
        <article className="flex w-full max-w-[560px] flex-col gap-1 self-start rounded-sm bg-paper px-6 py-8 text-paper-ink shadow-[0_16px_40px_-18px_rgba(0,0,0,0.9)] sm:px-10 sm:py-10">
          <header className="mb-4 flex items-baseline justify-between gap-4 border-b border-paper-rule pb-3">
            <span className="text-base font-bold">{product ?? name}</span>
            {result.document_revision && <span className="shrink-0 font-mono text-xs text-paper-meta">{result.document_revision}</span>}
          </header>
          <span className="mb-2 font-mono text-xs uppercase tracking-[0.08em] text-paper-meta">Page {current?.page} · excerpt</span>
          {shown.map((k, j) => {
            const m = hit.get(k)
            const gap = j > 0 && k !== shown[j - 1] + 1
            const c = m ? TONE_COLOR[m.tone] : ''
            const row = m?.kind === 'problem' ? changedRow(result, m.claim_id) : undefined
            return (
              <Fragment key={k}>
                {gap && <span className="py-1 text-center text-paper-meta" aria-hidden>⋯</span>}
                <span className={`-mx-2 flex flex-wrap items-baseline justify-between gap-x-3 rounded-sm px-2 py-1 leading-6 ${m ? 'font-semibold' : ''}`}
                  style={m ? { background: `${c}${m.finding.id === selId ? '40' : '26'}`, boxShadow: `inset 3px 0 0 ${c}` } : undefined}
                  title={m ? `${m.kind === 'checked' ? 'Checked' : 'Problem'}: ${m.finding.title}` : undefined}>
                  <span className="min-w-0">{displayQuote(lines[k])}</span>
                  {row && <span className="shrink-0 rounded px-2 py-0.5 font-sans text-xs font-semibold text-on-accent" style={{ background: c }}>now {row.current}</span>}
                </span>
              </Fragment>
            )
          })}
        </article>
      </div>
    </>
  )
}

// ---------- 4 · Outcome ----------

// When the nightly re-check (scripts/recheck.py as a Nebius Serverless Job) last ran, in one line.
const recheckLine = (r: Recheck) => {
  const flagged = r.items.filter((i) => i.status !== 'no_change').length
  const when = new Date(r.checked_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  const by = r.job_name ? `${r.runner} ${r.job_name}` : r.runner === 'local' ? '' : r.runner
  return `${r.mode === 'mock' ? 'Mock · ' : ''}Re-checked${by ? ` by ${by}` : ''} · ${when} · ${plural(r.items.length, 'item')}, ${flagged} flagged`
}

function OutcomeStep({ queue, loaded, calls, rows, watched, checks, checked, requested, error, recheck, rowOf, memoRun, onCheck, onRequest }: {
  queue: Case[]; loaded: Record<string, Loaded>; calls: Record<string, Call>; rows: Record<string, Row>; watched: Case[]
  rowOf: (id: string) => PackageRow | undefined; memoRun?: string
  checks: Record<string, Row>; checked: Record<string, Result>; requested: Record<string, boolean>; error: string | null
  recheck?: Recheck | null; onCheck: () => void; onRequest: (id: string) => void
}) {
  const notChecked = queue.filter((c) => loaded[c.id].result.decision === 'not_applicable')
  const returned = queue.filter((c) => loaded[c.id].result.decision !== 'not_applicable' && calls[c.id]?.act === 'return')
  const approved = [...queue.filter((c) => loaded[c.id].result.decision !== 'not_applicable' && calls[c.id]?.act === 'approve'), ...watched]
  const manual = queue.filter((c) => calls[c.id]?.act === 'manual')
  const checking = approved.some((c) => checks[c.id] && checks[c.id].stage !== 'error' && !checked[c.id])
  const alerts = approved.filter((c) => discontinued(checked[c.id]))
  const back = 'minmax(0,0.8fr) minmax(0,1.2fr) minmax(0,1.4fr) minmax(0,1.4fr)'
  const sent = '112px minmax(0,1fr) minmax(0,2fr)'
  const fwd = '112px minmax(0,1.4fr) 112px 140px 128px'
  return (
    <>
      <Heading title="Outcome" count={`${returned.length} to return · ${approved.length - watched.length} approved${manual.length ? ` · ${manual.length} for manual review` : ''}`}>
        <button className={PRIMARY} onClick={onCheck} disabled={checking || !approved.length}>
          {checking ? 'Checking…' : 'Check approved now'}
        </button>
      </Heading>
      <p className="-mt-3 text-xs text-muted">Decisions and drafts are saved in this browser. No messages have been sent. The watch list includes a sample approval from 2024.</p>
      {memoRun && <MemoLink run={memoRun} />}
      {error && <p className="text-bad" role="alert">{error}</p>}

      {notChecked.length > 0 && <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Not checked</h2>
        {notChecked.map((c) => <p key={c.id} className="text-muted">{c.title} · Doesn't match this spec ({loaded[c.id].result.spec_section ?? c.section}).</p>)}
      </section>}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Marked for return to subcontractors</h2>
        <div className="rounded-xl border border-line">
          {returned.length ? (
            <Table cols={sent} head={['Number', 'Recipient', 'What to send']}>
              {returned.map((c) => {
                const row = rowOf(c.id)
                return (
                  <TableRow key={c.id} cols={sent}>
                    <span className="font-mono text-xs text-muted">{c.number ?? 'Upload'}</span>
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate">{c.from ?? 'Sender'}</span>
                      <span className="truncate text-xs text-muted">{c.product ?? c.title}</span>
                    </span>
                    <ol className="flex flex-col gap-1 text-soft">{row?.what_to_send.map((t) => <li key={t}>{t}</li>) ?? '—'}</ol>
                  </TableRow>
                )
              })}
            </Table>
          ) : <p className="px-4 py-6 text-muted">None marked for return.</p>}
        </div>
      </section>

      {manual.length > 0 && <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Manual review</h2>
        <div className="rounded-xl border border-line">
          <Table cols={back} head={['Number', 'Submittal', 'Still needs a person', 'Flagged']}>
            {manual.map((c) => {
              const row = rowOf(c.id)
              return (
                <TableRow key={c.id} cols={back}>
                  <span className="font-mono text-xs text-muted">{c.number ?? 'Upload'}</span>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{c.title}</span>
                    <span className="truncate text-xs text-muted">{c.from ?? 'You'}</span>
                  </span>
                  <span className="text-soft">{row?.what_to_send.join(' · ') || (row?.couldnt_confirm ? `${plural(row.couldnt_confirm, 'item')} couldn't be confirmed` : '—')}</span>
                  <span className="text-xs text-muted">{row ? `${row.stamp} suggested` : ''}</span>
                </TableRow>
              )
            })}
          </Table>
        </div>
      </section>}

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-semibold">Approved for forwarding to the architect</h2>
        </div>
        {recheck && <p className="break-words text-xs text-muted">{recheckLine(recheck)}</p>}
        <div className="rounded-xl border border-line">
          <Table cols={fwd} head={['Number', 'Product', 'Approved', 'Last checked', 'Status']}>
            {approved.map((c) => {
              const w = checks[c.id]
              const res = checked[c.id]
              const latest = res ?? loaded[c.id]?.result
              const unconfirmed = latest?.findings.find((f) => ['currency', 'status'].includes(f.check) && f.verdict === 'unverified')
              const currency = latest?.findings.find((f) => f.check === 'currency' && ['outdated', 'fail', 'note'].includes(f.verdict))
              const scannedAt = c.watch ? undefined : rows[c.id]?.at
              const status = w?.stage === 'error' ? <span className="text-bad">{w.reason ?? "Couldn't check"}</span>
                : w && !res ? <span className="flex items-center gap-2 text-soft"><span className="blink h-2 w-2 rounded-full bg-flare" />Checking</span>
                : unconfirmed ? <span className="text-muted" title={unconfirmed.detail}>Couldn't confirm · {unconfirmed.detail}</span>
                : discontinued(latest) ? <span className="font-medium text-bad">Discontinued</span>
                : currency ? <span className="text-muted" title={currency.detail}>{currency.title}</span>
                : res ? <span className="text-good">No change</span>
                : scannedAt ? <span className="text-good">No change</span> : <span className="text-muted">Watching</span>
              return (
                <TableRow key={c.id} cols={fwd}>
                  <span className="font-mono text-xs text-muted">{c.number ?? 'Upload'}</span>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{c.product ?? c.title}</span>
                    <span className="truncate text-xs text-muted">{c.from ?? 'You'}</span>
                  </span>
                  <span className="text-xs text-muted"><span className="sm:hidden">Approved </span>{c.watch ? longDate(c.watch.approved) : 'Today'}</span>
                  <span className="text-xs text-muted"><span className="sm:hidden">Last checked </span>{w?.at ?? scannedAt ?? '—'}</span>
                  {status}
                </TableRow>
              )
            })}
          </Table>
        </div>
        {alerts.map((c) => (
          <Alert key={c.id} c={c} result={checked[c.id]} sent={!!requested[c.id]} onRequest={() => onRequest(c.id)} />
        ))}
      </section>
    </>
  )
}

function Alert({ c, result, sent, onRequest }: { c: Case; result: Result; sent: boolean; onRequest: () => void }) {
  const f = discontinued(result)!
  const when = String(f.compare?.right_value ?? '').replace(/^Discontinued\s*/, '')
  const src = f.evidence[0]
  const fix = fixOf(result)
  const who = c.from ?? 'the sender'
  const steps: [string, string, boolean][] = [
    ['Approved', c.watch ? longDate(c.watch.approved) : 'Today', false],
    ['Discontinued', when ? longDate(when) : '—', true],
    ['Detected', 'Today', true],
  ]
  return (
    <section className="arrive flex flex-col gap-5 rounded-xl border border-bad/50 bg-bad/[0.06] p-4 sm:p-5" aria-label={`${c.number} discontinued`}>
      <div className="flex flex-col gap-1">
        <span className="font-mono text-xs font-semibold tracking-[0.08em] text-bad">{c.number} · DISCONTINUED</span>
        <h3 className="text-lg font-semibold leading-tight">{c.product} is no longer manufactured</h3>
      </div>
      <ol className="grid grid-cols-3">
        {steps.map(([label, date, bad], i) => (
          <li key={label} className="flex flex-col gap-2">
            <span className="flex items-center">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${bad ? 'bg-bad' : 'bg-good'}`} />
              {i < steps.length - 1 && <span className="h-px flex-1 bg-edge" />}
            </span>
            <span className="text-xs text-muted">{label}</span>
            <span className="font-medium">{date}</span>
          </li>
        ))}
      </ol>
      {f.quote && (
        <blockquote className="flex flex-col gap-1 border-l-2 border-edge pl-3">
          <span className="text-base text-soft">“{displayQuote(f.quote)}”</span>
          {src && <a href={src.url} target="_blank" rel="noreferrer" className="truncate text-xs text-muted underline decoration-edge underline-offset-2 hover:text-ink">{src.title || hostOf(src.url)} ↗</a>}
        </blockquote>
      )}
      {fix && <AlternatesCard fix={fix} />}
      <button className="btn h-auto max-w-full self-start whitespace-normal py-2 text-left" onClick={onRequest} disabled={sent}>
        {sent ? `Request saved for ${who}` : `Save substitution request for ${who}`}
      </button>
    </section>
  )
}
