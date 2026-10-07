import { forwardRef, Fragment, useEffect, useImperativeHandle, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, getCaseText, getDocPages, getProject, getResult, getScores, pageUrl, startReplay, startRun,
  streamEvents, uploadPdf,
  type Case, type Compare, type CompareRow, type Decision, type DocPages, type Event, type Finding, type Fix, type Mark,
  type Project, type Result, type Scores, type Stage, type TextPage, type Tone, type Value,
} from './api'

type View = 'ready' | 'running' | 'done' | 'detail' | 'results'
type CaseState = { stage: Stage; message: string; model: string | null; decision?: Decision; summary?: string }

const ACTIVE: Stage[] = ['ingest', 'triage', 'extract', 'spec_check', 'verify', 'reconcile', 'fix', 'report']
const NBSP = '\u00a0'

// docs: page sizes of each downloaded submittal PDF; null when one is missing, then text holds the fixture pages.
type Loaded = { result: Result; docs: DocPages[] | null; text: TextPage[] | null }

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [view, setView] = useState<View>('ready')
  const [runId, setRunId] = useState<string | null>(null)
  const [runDone, setRunDone] = useState(false)
  const [states, setStates] = useState<Record<string, CaseState>>({})
  const [loaded, setLoaded] = useState<Record<string, Loaded>>({})
  const [current, setCurrent] = useState<string | null>(null)
  // Uploaded PDFs: extra rows, each on its own run.
  const [uploads, setUploads] = useState<Case[]>([])
  const [uploadRun, setUploadRun] = useState<Record<string, string>>({})

  useEffect(() => { getProject().then(setProject) }, [])

  const cases = [...(project?.cases ?? []), ...uploads]
  const openable = cases.filter((c) => states[c.id]?.stage === 'done').map((c) => c.id)
  const runOf = (caseId: string) => uploadRun[caseId] ?? runId

  async function load(id: string, caseId: string, files?: string[]): Promise<Loaded> {
    files ??= cases.find((c) => c.id === caseId)?.submittal.map((d) => d.file) ?? []
    const [result, ...found] = await Promise.all([getResult(id, caseId), ...files.map((f) => getDocPages(caseId, f))])
    const docs = found.length && found.every(Boolean) ? (found as DocPages[]) : null
    const l = { result: result as Result, docs, text: docs ? null : await getCaseText(caseId) }
    setLoaded((m) => ({ ...m, [caseId]: l }))
    return l
  }

  function track(id: string, files?: Record<string, string[]>) {
    return (e: Event) => {
      if (!e.case_id) return
      if (e.stage === 'done') load(id, e.case_id, files?.[e.case_id]) // prefetch, so opening and switching are instant
      setStates((s) => ({
        ...s,
        [e.case_id!]: {
          stage: e.stage,
          message: e.message,
          model: e.model,
          decision: (e.data?.decision as Decision) ?? s[e.case_id!]?.decision,
          summary: (e.data?.summary as string) ?? s[e.case_id!]?.summary,
        },
      }))
    }
  }

  function follow(id: string) {
    // Uploads keep their own state; only the project's items start over.
    setStates((s) => Object.fromEntries(Object.entries(s).filter(([k]) => k in uploadRun)))
    setLoaded((m) => Object.fromEntries(Object.entries(m).filter(([k]) => k in uploadRun)))
    setRunId(id)
    setRunDone(false)
    setView('running')
    streamEvents(id, track(id), () => {
      setRunDone(true)
      // Move on only if the reviewer is still watching the run, never out of a result they opened.
      setTimeout(() => setView((v) => (v === 'running' ? 'done' : v)), 900)
    })
  }

  async function upload(file: File) {
    const { run_id, case: c } = await uploadPdf(file)
    setUploads((u) => [...u, c])
    setUploadRun((m) => ({ ...m, [c.id]: run_id }))
    setStates((s) => ({ ...s, [c.id]: { stage: 'queued', message: 'Waiting', model: null } }))
    streamEvents(run_id, track(run_id, { [c.id]: c.submittal.map((d) => d.file) }), () => {})
  }

  async function run() {
    if (project) follow(await startRun(project.cases.map((c) => c.id)))
  }

  async function replay() {
    if (runId) follow(await startReplay(runId))
  }

  async function open(caseId: string) {
    const id = runOf(caseId)
    if (!id || !openable.includes(caseId)) return
    if (!loaded[caseId]) await load(id, caseId)
    setCurrent(caseId)
    setView('detail')
    window.scrollTo({ top: 0 }) // a new result starts at its top, not where the list was scrolled
  }

  const overview = () => setView(runId ? (runDone ? 'done' : 'running') : 'ready')
  const detail = view === 'detail' && current ? loaded[current] : undefined

  // Left/right arrows step through submittals while a result is open.
  useEffect(() => {
    if (view !== 'detail' || !current) return
    function onKey(e: KeyboardEvent) {
      if (e.altKey || e.metaKey || e.ctrlKey || (e.target as HTMLElement).closest('input, textarea, select')) return
      const i = openable.indexOf(current!)
      const next = e.key === 'ArrowRight' ? openable[i + 1] : e.key === 'ArrowLeft' ? openable[i - 1] : undefined
      if (next) { e.preventDefault(); open(next) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="min-h-screen font-sans text-[13px]">
      <header className="flex min-h-[52px] flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-white/5 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          <button onClick={overview} className="flex shrink-0 items-center gap-2 font-semibold">
            <span className="flare h-3.5 w-3.5 rounded" />SpecCheck
          </button>
          <span className="text-faint" aria-hidden>/</span>
          <span className="truncate text-muted">{view === 'results' ? 'Results' : project?.name ?? '…'}</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {detail
            ? <Verdict result={detail.result} />
            : <span className="hidden font-mono text-[11px] text-faint sm:inline">Nemotron on Nebius · Tavily</span>}
          <button onClick={() => setView(view === 'results' ? (runId ? (runDone ? 'done' : 'running') : 'ready') : 'results')}
            aria-pressed={view === 'results'} className={`btn ${view === 'results' ? 'bg-selected' : ''}`}>Results</button>
        </div>
      </header>

      {detail && (
        <DocSwitcher cases={cases} states={states} current={current!} openable={openable} onOpen={open} onAll={overview} />
      )}

      <main className={detail ? 'mx-auto max-w-[1680px] px-4 py-4' : 'mx-auto flex max-w-[1120px] flex-col gap-7 px-4 py-10 sm:px-6 sm:py-12'}>
        {view === 'ready' && <Ready cases={cases} states={states} onRun={run} onOpen={open} onUpload={upload} />}
        {view === 'running' && <Running cases={cases} states={states} done={openable.length} onOpen={open} onUpload={upload} />}
        {view === 'done' && <Done cases={cases} states={states} onOpen={open} onAgain={run} onUpload={upload} />}
        {view === 'results' && <Results />}
        {detail && <Detail key={current} result={detail.result} docs={detail.docs} text={detail.text} runId={runOf(current!)!}
          onReplay={uploadRun[current!] ? undefined : replay} />}
      </main>
    </div>
  )
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d={dir === 'left' ? 'M10 3 5 8l5 5' : 'm6 3 5 5-5 5'} stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// Every submittal one click away while reviewing; arrows and prev/next step through them in order.
function DocSwitcher({ cases, states, current, openable, onOpen, onAll }: {
  cases: Case[]; states: Record<string, CaseState>; current: string; openable: string[]
  onOpen: (id: string) => void; onAll: () => void
}) {
  const i = openable.indexOf(current)
  const strip = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Scroll only the strip (scrollIntoView would also scroll the page).
    const el = strip.current, chip = el?.querySelector<HTMLElement>('[aria-current=page]')
    if (el && chip) el.scrollTo({ left: chip.offsetLeft - el.offsetLeft - (el.clientWidth - chip.offsetWidth) / 2, behavior: 'smooth' })
  }, [current])
  return (
    <nav aria-label="Submittals" className="sticky top-0 z-20 flex items-center gap-2 border-b border-line bg-[#0b0c0f]/90 px-4 py-2 backdrop-blur">
      <button onClick={onAll} className="btn shrink-0">All {cases.length}</button>
      <div ref={strip} className="flex min-w-0 flex-1 gap-1 overflow-x-auto [scrollbar-width:none]">
        {cases.map((c) => {
          const s = states[c.id]
          const on = c.id === current
          return (
            <button key={c.id} onClick={() => onOpen(c.id)} disabled={!openable.includes(c.id)} aria-current={on ? 'page' : undefined}
              title={s?.decision ? `${c.title}: ${DECISION_LABEL[s.decision]}` : c.title}
              className={`flex h-8 max-w-[210px] shrink-0 items-center gap-2 rounded-md px-2.5 text-xs transition-colors disabled:opacity-40 ${on ? 'bg-selected text-ink shadow-[inset_0_0_0_1px_var(--color-edge)]' : 'text-muted enabled:hover:bg-raised enabled:hover:text-ink'}`}>
              <span className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ background: s?.decision ? DECISION_COLOR[s.decision] : 'var(--color-faint)' }} />
              <span className="truncate">{c.title}</span>
            </button>
          )
        })}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <span className="mr-1 hidden font-mono text-[11px] tabular-nums text-faint sm:inline">{i + 1}/{openable.length}</span>
        <button className="btn w-8 px-0" onClick={() => onOpen(openable[i - 1])} disabled={i <= 0} aria-label="Previous submittal" title="Previous submittal (←)"><Chevron dir="left" /></button>
        <button className="btn w-8 px-0" onClick={() => onOpen(openable[i + 1])} disabled={i >= openable.length - 1} aria-label="Next submittal" title="Next submittal (→)"><Chevron dir="right" /></button>
      </div>
    </nav>
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
      className={`flex cursor-pointer flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed px-4 py-3.5 transition-colors ${over ? 'border-flare bg-flare/5' : 'border-edge hover:border-flare'}`}>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium">Check your own submittal</span>
        <span className="text-xs text-muted">
          {error ?? "Drop any firestop or light fixture PDF. It's checked against this project's specs like any other submittal."}
        </span>
      </span>
      <span className="btn pointer-events-none">{busy ? 'Uploading…' : 'Choose a PDF'}</span>
      <input type="file" accept="application/pdf,.pdf" className="sr-only" disabled={busy}
        onChange={(e) => { send(e.target.files?.[0]); e.target.value = '' }} />
    </label>
  )
}

function Ready({ cases, states, onRun, onOpen, onUpload }: {
  cases: Case[]; states: Record<string, CaseState>; onRun: () => void; onOpen: (id: string) => void; onUpload: (f: File) => Promise<void>
}) {
  const base = cases.filter((c) => !c.upload).length
  return (
    <>
      <section className="flex flex-col items-center gap-4 pt-6 text-center">
        <h1 className="text-[40px] font-bold leading-tight tracking-tight">{base} submittals are waiting for review</h1>
        <p className="max-w-[540px] text-[15px] text-muted">
          SpecCheck reads each package, compares it to the spec, and checks the manufacturer's current documents online.
          Anything it sends back comes with a fix.
        </p>
        <button onClick={onRun} className="flare mt-3 h-[52px] rounded-[10px] px-7 text-base font-bold">
          Review all {base} submittals
        </button>
      </section>
      <Upload onUpload={onUpload} />
      <section className="panel grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-px overflow-hidden bg-line">
        {cases.map((c) => {
          const s = states[c.id]
          return (
            <button key={c.id} onClick={() => onOpen(c.id)} disabled={s?.stage !== 'done'}
              className="flex flex-col gap-1 bg-panel px-4 py-3.5 text-left enabled:hover:bg-raised">
              <span className="truncate">{c.title}</span>
              <span className="flex items-center gap-2 font-mono text-[11px] text-faint">
                {c.section}{c.upload && <span className="text-flare">your upload</span>}
                {s && <span className={ACTIVE.includes(s.stage) ? 'blink text-soft' : 'text-soft'}>
                  {s.decision ? DECISION_LABEL[s.decision] : s.message}</span>}
              </span>
            </button>
          )
        })}
      </section>
    </>
  )
}

function Running({ cases, states, done, onOpen, onUpload }: {
  cases: Case[]; states: Record<string, CaseState>; done: number; onOpen: (id: string) => void; onUpload: (f: File) => Promise<void>
}) {
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight">Nemotron is reviewing {cases.length} submittals</h1>
          <p className="text-muted">Each package is read, checked against the spec, then checked against the manufacturer's site. Send-backs get a fix. Open any finished card.</p>
        </div>
        <div className="flex min-w-[200px] flex-col gap-1.5">
          <span className="text-right font-mono text-xs tabular-nums">{done} of {cases.length} done</span>
          <div className="h-1 rounded bg-line">
            <div className="flare h-1 rounded transition-all duration-500" style={{ width: `${(done / Math.max(cases.length, 1)) * 100}%` }} />
          </div>
        </div>
      </section>
      <section className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
        {cases.map((c) => {
          const s = states[c.id]
          const active = !!s && ACTIVE.includes(s.stage)
          const finished = s?.stage === 'done'
          return (
            // Fixed height and single-line rows: cards never resize while stages change.
            <button key={c.id} onClick={() => onOpen(c.id)} disabled={!finished} title={finished ? 'Open result' : undefined}
              className={`panel flex h-[214px] flex-col gap-3 p-3.5 text-left transition-colors enabled:hover:border-edge ${s ? '' : 'opacity-55'}`}>
              <div className="relative flex h-28 shrink-0 flex-col gap-[7px] overflow-hidden rounded bg-paper p-3">
                {[60, 88, 80, 84, 70, 76].map((w, i) => (
                  <div key={i} className="h-1 bg-paper-rule" style={{ width: `${w}%`, height: i === 0 ? 6 : 4 }} />
                ))}
                {active && <div className="scan absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-flare to-transparent shadow-[0_0_10px_2px_rgba(245,121,26,0.6)]" />}
                {finished && s.decision && (
                  <div className="pop absolute inset-0 flex items-center justify-center bg-panel/55">
                    <span className="rounded-md px-3 py-1.5 font-bold text-on-accent" style={{ background: DECISION_COLOR[s.decision] }}>
                      {DECISION_LABEL[s.decision]}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex min-w-0 flex-col gap-1">
                <span className="h-5 truncate font-medium leading-5" title={c.title}>{c.title}</span>
                <span className={`h-4 truncate text-xs leading-4 ${active ? 'blink' : 'text-muted'}`}>{s?.message ?? 'Waiting'}</span>
                <span className="h-4 truncate font-mono text-[11px] leading-4 text-faint">{(active && s?.model) || (c.upload ? 'your upload' : NBSP)}</span>
              </div>
            </button>
          )
        })}
      </section>
      <Upload onUpload={onUpload} />
    </>
  )
}

function Done({ cases, states, onOpen, onAgain, onUpload }: {
  cases: Case[]; states: Record<string, CaseState>; onOpen: (id: string) => void; onAgain: () => void; onUpload: (f: File) => Promise<void>
}) {
  const sendBack = cases.filter((c) => states[c.id]?.decision === 'send_back').length
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-5">
        <h1 className="text-[30px] font-bold tracking-tight">
          {sendBack} submittal{sendBack === 1 ? '' : 's'} need{sendBack === 1 ? 's' : ''} to go back, each with a fix
        </h1>
        <button onClick={onAgain} className="btn h-9 px-3.5">Run again</button>
      </section>
      <section className="panel overflow-hidden">
        {cases.map((c) => {
          const s = states[c.id]
          const active = !!s && ACTIVE.includes(s.stage)
          return (
            <button key={c.id} onClick={() => onOpen(c.id)} disabled={!s?.decision}
              className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-line px-4 py-3 text-left last:border-b-0 enabled:hover:bg-raised disabled:cursor-not-allowed md:min-h-14 md:grid-cols-[minmax(0,1fr)_170px_minmax(0,1.4fr)_64px] md:py-2">
              <span className="flex min-w-0 flex-col font-medium md:font-normal">
                <span className="truncate">{c.title}</span>
                {c.upload && <span className="font-mono text-[11px] text-flare">your upload</span>}
              </span>
              <span className="flex items-center gap-2 justify-self-end font-medium md:justify-self-auto">
                {s?.decision && <span className="h-[7px] w-[7px] rounded-full" style={{ background: DECISION_COLOR[s.decision] }} />}
                {s?.decision ? DECISION_LABEL[s.decision] : s?.stage === 'error' ? 'Error' : active ? <span className="blink text-muted">{s.message}</span> : '—'}
              </span>
              <span className="col-span-2 text-muted md:col-span-1">{s?.summary}</span>
              <span className="hidden text-right text-muted md:block">{s?.decision ? 'Open →' : ''}</span>
            </button>
          )
        })}
      </section>
      <Upload onUpload={onUpload} />
    </>
  )
}

// ---------- result view ----------

const TONE_COLOR: Record<Tone, string> = { red: '#e5534b', amber: '#f0892a', gray: '#8b8f98', green: '#2e9e68' }
const TONE_RANK: Record<Tone, number> = { red: 0, amber: 1, gray: 2, green: 3 }
const SEVERITY_RANK: Record<Finding['severity'], number> = { critical: 0, major: 1, minor: 2, info: 3 }
const toneOf = (f: Finding): Tone => (f.verdict === 'fail' ? 'red' : f.verdict === 'outdated' ? 'amber' : 'gray')
const LABEL: Record<Finding['verdict'], string> = {
  fail: 'Must fix', outdated: 'Out of date', note: 'Note', unverified: 'Not stated', pass: 'Passed', not_applicable: 'Not applicable',
}
// A requirement was looked for but no claim was found on any page.
const notFound = (f: Finding) => !!f.requirement_id && f.claim_ids.length === 0

function counts(result: Result) {
  const by = (v: Finding['verdict']) => result.findings.filter((f) => f.verdict === v).length
  return [
    [by('fail'), 'must fix', 'red'], [by('outdated'), 'out of date', 'amber'], [by('unverified'), 'not stated', 'gray'],
    [by('note'), 'note', 'gray'], [by('pass'), 'passed', null],
  ].filter(([n]) => n) as [number, string, Tone | null][]
}

function Verdict({ result }: { result: Result }) {
  const color = DECISION_COLOR[result.decision]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="hidden max-w-[260px] truncate text-muted lg:inline">{result.title}</span>
      <span className="flex items-center gap-2 font-semibold">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 10px ${color}` }} />
        {DECISION_LABEL[result.decision]}
      </span>
      <span className="flex gap-3 text-xs tabular-nums text-muted">
        {counts(result).map(([n, label, tone]) => (
          <span key={label} style={tone ? { color: TONE_COLOR[tone] } : undefined}>{n} {label}</span>
        ))}
      </span>
    </div>
  )
}

type Placed = Mark & { finding: Finding; tone: Tone }
type PdfPage = { key: string; file: string; n: number; width: number; height: number }

const pageKey = (file: string | null, n: number | null) => `${file}#${n}`
// A finding's page: the first claim that was located, else the first claim with a page.
const firstMark = (f: Finding) => f.highlights.find((h) => h.boxes.length) ?? f.highlights.find((h) => h.page)

function Detail({ result, docs, text, runId, onReplay }: {
  result: Result; docs: DocPages[] | null; text: TextPage[] | null; runId: string; onReplay?: () => void
}) {
  // Worst first: must fix, then out of date, then notes and not-stated.
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass' && f.verdict !== 'not_applicable')
    .sort((a, b) => TONE_RANK[toneOf(a)] - TONE_RANK[toneOf(b)] || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]), [result])
  const marks: Placed[] = useMemo(() => result.findings.flatMap((f) =>
    f.highlights.map((h) => ({ ...h, finding: f, tone: h.kind === 'checked' ? 'green' as Tone : toneOf(f) }))), [result])
  const [selId, setSelId] = useState<string | null>(issues[0]?.id ?? null)
  const sel = issues.find((f) => f.id === selId) ?? null
  const [pulse, setPulse] = useState(0)
  const [textPage, setTextPage] = useState(() => (sel && firstMark(sel)?.page) || 1)
  const pdf = useRef<{ scrollTo: (key: string) => void }>(null)

  function select(f: Finding) {
    setSelId(f.id)
    setPulse((n) => n + 1)
    const m = firstMark(f)
    if (!m?.page) return
    if (docs) pdf.current?.scrollTo(pageKey(m.doc_file, m.page))
    else setTextPage(m.page)
  }

  const passed = result.findings.filter((f) => f.verdict === 'pass').length
  const skipped = result.findings.filter((f) => f.verdict === 'not_applicable').length
  const pageCount = docs ? docs.reduce((a, d) => a + d.pages.length, 0) : text?.length ?? 0
  const lost = sel && sel.highlights.length > 0 && docs && sel.highlights.every((h) => h.boxes.length === 0)
  const banner = !sel ? null
    : notFound(sel) ? <>Searched all {plural(pageCount, 'page')}: nothing in the package covers this{sel.spec_ref ? ` (spec ${sel.spec_ref})` : ''}.</>
    : sel.claim_ids.length === 0 ? <>This applies to the whole document, not one spot on a page.</>
    : lost ? <>Couldn't locate this on the page. The quote was: “{sel.highlights[0].quote}”</>
    : null

  return (
    <div className="grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[270px_minmax(0,1fr)_360px]">
      {/* Below 1100px the asides dissolve so the order is list, document, details, how it was checked. */}
      <aside className="contents min-[1100px]:flex min-[1100px]:min-w-0 min-[1100px]:flex-col min-[1100px]:gap-4">
        <nav className="panel overflow-hidden">
          {issues.map((f) => {
            const p = firstMark(f)?.page
            return (
              <button key={f.id} onClick={() => select(f)}
                aria-current={sel?.id === f.id ? 'true' : undefined}
                className={`flex w-full flex-col gap-1 border-b border-line px-3.5 py-3 text-left transition-colors ${sel?.id === f.id ? 'bg-selected shadow-[inset_0_0_0_1px_var(--color-edge)]' : 'hover:bg-raised'}`}>
                <span className="flex justify-between text-xs">
                  <span style={{ color: TONE_COLOR[toneOf(f)] }}>{LABEL[f.verdict]}</span>
                  <span className="font-mono text-faint">{p ? `p. ${p}` : notFound(f) ? 'not found' : 'whole doc'}</span>
                </span>
                <span className="leading-snug">{f.title}</span>
              </button>
            )
          })}
          <div className="px-3.5 py-3 text-muted">
            {issues.length ? '' : 'No problems found. '}{plural(passed, 'check')} passed
            {skipped > 0 && <span className="block text-xs text-faint">{plural(skipped, 'check')} not applicable to this document type</span>}
          </div>
        </nav>
        <div className="order-last min-[1100px]:order-none"><HowChecked result={result} runId={runId} onReplay={onReplay} /></div>
      </aside>

      <section className="panel flex min-w-0 flex-col gap-3 p-3 min-[1100px]:sticky min-[1100px]:top-[66px] min-[1100px]:h-[calc(100vh-82px)]">
        {docs
          ? <PdfPages ref={pdf} caseId={result.case_id} docs={docs} marks={marks} selId={sel?.id ?? null} pulse={pulse}
              result={result} banner={banner} onPick={select} />
          : <TextPages pages={text ?? []} marks={marks} selId={sel?.id ?? null} result={result} banner={banner}
              page={textPage} onPage={setTextPage} />}
      </section>

      <aside className="contents min-[1100px]:block min-[1100px]:min-w-0">
        <FindingCard finding={sel} result={result} passed={passed} />
      </aside>
    </div>
  )
}

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
  banner: ReactNode; onPick: (f: Finding) => void
}>(function PdfPages({ caseId, docs, marks, selId, pulse, result, banner, onPick }, ref) {
  const pages: PdfPage[] = docs.flatMap((d) => d.pages.map((s, i) => ({ key: pageKey(d.file, i + 1), file: d.file, n: i + 1, ...s })))
  const multi = docs.length > 1
  const scroller = useRef<HTMLDivElement>(null)
  const refs = useRef<Record<string, HTMLDivElement | null>>({})
  const byPage = useMemo(() => {
    const m: Record<string, Placed[]> = {}
    for (const p of marks) if (p.boxes.length) (m[pageKey(p.doc_file, p.page)] ??= []).push(p)
    return m
  }, [marks])

  function scrollTo(key: string) {
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
      <div className="flex shrink-0 gap-2 overflow-x-auto pb-1 pt-1.5 pr-1.5" role="list" aria-label="Pages">
        {pages.map((p) => {
          const t = worstTone(byPage[p.key] ?? [])
          return (
            <button key={p.key} role="listitem" onClick={() => scrollTo(p.key)} aria-label={`Page ${p.n}${t ? ', has highlights' : ''}`}
              className="relative w-11 shrink-0 rounded-sm bg-white ring-1 ring-line transition-shadow hover:ring-edge"
              style={{ aspectRatio: `${p.width} / ${p.height}` }}>
              <img src={pageUrl(caseId, p.file, p.n)} alt="" className="h-full w-full rounded-sm object-cover" />
              <span className="absolute bottom-0.5 left-0.5 rounded-sm bg-black/65 px-1 font-mono text-[9px] leading-tight text-white">{p.n}</span>
              {t && <span className="absolute -right-1.5 -top-1.5 h-3 w-3 rounded-full ring-2 ring-panel" style={{ background: TONE_COLOR[t] }} />}
            </button>
          )
        })}
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
              <span key={finding.id} className={`absolute z-10 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold text-on-accent shadow ${finding.id === selId ? '' : 'opacity-75'}`}
                style={{ left: `${x * 100}%`, top: `calc(${y * 100}% + 5px)`, background: color }}>
                now {text}
              </span>
            ))}
            <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-white">
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
      <mark key={`${m.finding.id}-${m.claim_id}`} className="rounded-sm px-0.5 text-inherit"
        style={{ background: `${c}${on ? '55' : '22'}`, outline: on ? `2px solid ${c}` : 'none' }}>{m.quote}</mark>,
    )
    if (row) out.push(
      <span key={`${m.claim_id}-now`} className="ml-1 rounded px-1.5 py-0.5 align-middle font-sans text-[11px] font-semibold text-on-accent"
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
        <span className="ml-auto font-sans text-[11px] text-faint">PDF not downloaded: showing extracted text</span>
      </div>
      {banner && <p className="rounded-md border border-line bg-well px-3 py-2 text-xs text-soft">{banner}</p>}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="whitespace-pre-line rounded bg-paper p-8 font-serif text-[15px] leading-7 text-paper-ink">
          <div className="mb-4 font-sans text-[11px] uppercase tracking-wide text-paper-meta">Page {current?.page} · text from the package</div>
          {out}
        </div>
      </div>
    </>
  )
}

function HowChecked({ result, runId, onReplay }: { result: Result; runId: string; onReplay?: () => void }) {
  const tokens = result.usage.reduce((a, u) => a + u.input_tokens + u.output_tokens, 0)
  const cost = result.usage.reduce((a, u) => a + u.cost_usd, 0)
  return (
    <div className="panel overflow-hidden font-mono text-[11px]">
      <div className="px-3.5 pb-1 pt-3 font-sans text-xs font-medium">How it was checked</div>
      {result.usage.map((u, i) => (
        <div key={i} className="flex justify-between gap-3 px-3.5 py-1">
          <span className="shrink-0 whitespace-nowrap">{u.task.replace(/_/g, ' ')}</span>
          <span className="truncate text-muted">{u.model.split('/').pop()}</span>
        </div>
      ))}
      <div className="mt-2 flex flex-wrap justify-between gap-x-3 gap-y-1 border-t border-line px-3.5 py-2.5 tabular-nums text-muted">
        <span>{tokens.toLocaleString()} tok</span>
        <span>${cost.toFixed(4)} + {result.web_credits} credits</span>
        <span>{(result.duration_ms / 1000).toFixed(1)} s</span>
      </div>
      {onReplay && (
        <button onClick={onReplay} className="w-full border-t border-line px-3.5 py-2.5 text-left text-flare hover:bg-raised">
          Replay run {runId.slice(-6)} →
        </button>
      )}
    </div>
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

const CAPS = 'font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-faint'
const BIG = 'text-[22px] font-bold leading-tight'
const BAD = 'text-[#ff8a84]'
const show = (v: Value) => (v === null || v === undefined ? '—' : String(v))
const lower = (v: Value) => (Array.isArray(v) ? v : [show(v)]).join(' | ').toLowerCase()

// What the spec (or the job) needs, next to what was sent. Lists are chips; a needed item the other side lacks is outlined red.
function CompareBlock({ c }: { c: Compare }) {
  if (c.rows.length) { // currency: only the values that changed, sent -> current
    return (
      <div className="overflow-hidden rounded-[10px] border border-line">
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_16px_minmax(0,1.1fr)] gap-2 border-b border-line bg-well px-3.5 py-2.5">
          <span />
          {[c.left_label, null, c.right_label].map((l, i) => {
            if (l === null) return <span key={i} />
            const [head, rev] = splitLabel(l)
            return (
              <span key={i} className="flex min-w-0 flex-col gap-0.5">
                <span className={`${CAPS} ${i ? '!text-today' : ''}`}>{head}</span>
                {rev && <span className="truncate font-mono text-[10px] text-faint" title={rev}>{rev}</span>}
              </span>
            )
          })}
        </div>
        {c.rows.map((r) => (
          <div key={r.property} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_16px_minmax(0,1.1fr)] items-baseline gap-2 border-t border-line px-3.5 py-2.5 first-of-type:border-t-0">
            <span className="text-muted">{r.label}</span>
            <span className="text-[15px] text-muted">{r.submitted ?? '—'}</span>
            <span className="text-faint" aria-hidden>→</span>
            <span className="text-[17px] font-bold text-today">{r.current ?? '—'}</span>
          </div>
        ))}
      </div>
    )
  }
  if (c.left_value === null || c.left_value === undefined) { // single fact, e.g. Status: Discontinued June 30, 2024
    return (
      <div className="flex flex-col gap-1.5 rounded-[10px] border border-line bg-well p-3.5">
        <span className={CAPS}>{c.left_label}</span>
        <span className={`flex items-center gap-1.5 ${BIG} ${c.verdict === 'fail' ? BAD : 'text-ink'}`}>
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
      <div className="flex min-w-0 flex-col gap-2 bg-well px-3.5 py-3">
        <span className={CAPS}>{c.left_label}</span>
        {Array.isArray(c.left_value)
          ? <div className="flex flex-wrap gap-1.5">{c.left_value.map((it) => (
              <span key={it} className={`rounded-md px-2.5 py-1 font-bold ${missing.includes(it) ? `border-[1.5px] border-bad text-base ${BAD}` : 'border border-line text-sm text-soft'}`}>{it}</span>))}</div>
          : <span className={BIG}>{show(c.left_value)}</span>}
      </div>
      <div className={`flex min-w-0 flex-col gap-2 border-l border-line px-3.5 py-3 ${fail && !notStated && !chips ? 'bg-bad/[0.07]' : ''}`}>
        <span className={CAPS}>{c.right_label}</span>
        {Array.isArray(c.right_value)
          ? <div className="flex flex-wrap gap-1.5">{c.right_value.map((it) => (
              <span key={it} className="rounded-md bg-white/[0.06] px-2 py-0.5 text-xs text-soft">{it}</span>))}</div>
          : <span className={`flex items-center gap-1.5 ${BIG} ${notStated ? 'text-muted' : fail ? BAD : c.verdict === 'changed' ? 'text-today' : 'text-ink'}`}>
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

// Send-backs: what to send instead. Every candidate went through the same checks as a new submittal.
function FixPanel({ fix, attach, onAttach }: { fix: Fix; attach: boolean; onAttach: (on: boolean) => void }) {
  const ok = fix.candidates.filter((c) => c.passes).length
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-flare/35 p-4">
      <span className="flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F5A35A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z" />
        </svg>
        <span className={`${CAPS} !text-[#F5A35A]`}>{fix.suggest ? 'SpecCheck found a fix' : 'Looked for a fix'}</span>
      </span>
      <span className="-mt-1 font-semibold">{fix.head}</span>
      {fix.candidates.map((c, i) => (
        <div key={i} className={`flex flex-col gap-2 rounded-[10px] border p-3 ${c.placeholder ? 'border-dashed' : ''} ${c.passes ? 'border-good/40 bg-good/[0.05]' : 'border-line'}`}>
          <span className="flex items-start justify-between gap-2.5">
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="font-semibold">{c.name}</span>
              {c.source_url
                ? <a href={c.source_url} target="_blank" rel="noreferrer" className="truncate font-mono text-[11px] text-faint underline decoration-edge underline-offset-2 hover:text-soft">{hostOf(c.source_url)}</a>
                : <span className="font-mono text-[11px] text-faint">placeholder · a live run fills this in</span>}
            </span>
            {(() => {
              const bad = c.checks.find((k) => k.ok === false)
              return (
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.passes ? 'bg-good/15 text-[#4CC38A]' : 'bg-bad/15 text-[#E57373]'}`}>
                  {c.passes ? 'Passes' : `Fails: ${bad?.note || bad?.label || 'spec'}`}
                </span>
              )
            })()}
          </span>
          <div className="flex flex-col gap-1">
            {c.checks.map((k, j) => {
              const color = k.ok === true ? 'text-[#4CC38A]' : k.ok === false ? 'text-[#E57373]' : 'text-faint'
              return (
                <span key={j} className="flex items-baseline gap-2 text-xs">
                  <span className={`self-center ${color}`}><Icon kind={k.ok === true ? 'check' : k.ok === false ? 'x' : 'dash'} /></span>
                  <span className="text-soft">{k.label}</span>
                  <span className={`ml-auto shrink-0 ${color}`}>{k.note}</span>
                </span>
              )
            })}
          </div>
        </div>
      ))}
      {fix.candidates.length > 0 && (
        <span className="text-xs leading-normal text-muted">
          {ok} of {fix.candidates.length} pass{ok === 1 && fix.candidates.length === 1 ? 'es' : ''}. Each was checked with the same steps as a new submittal; “not stated” items are minor and don't block it.
        </span>
      )}
      {fix.suggest && (
        <label className="flex min-h-8 cursor-pointer items-center gap-2">
          <input type="checkbox" checked={attach} onChange={(e) => onAttach(e.target.checked)} className="accent-[#F5791A]" />
          Attach to the note
        </label>
      )}
    </div>
  )
}

function FindingCard({ finding: f, result, passed }: { finding: Finding | null; result: Result; passed: number }) {
  const src = f?.evidence[0]
  const [attach, setAttach] = useState(true)
  const fixes = result.findings.flatMap((x) => (x.fix?.suggest ? [x.fix.suggest] : []))
  const note = result.note_to_subcontractor && attach && fixes.length
    ? `${result.note_to_subcontractor}\n\nSuggested: ${fixes.join('; ')}. Checked against the spec; details attached.`
    : result.note_to_subcontractor
  return (
    <div className="panel flex flex-col gap-4 p-5">
      {f ? (
        <>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="flex justify-between font-mono text-[11px] uppercase tracking-[0.06em]">
              <span style={{ color: TONE_COLOR[toneOf(f)] }}>{LABEL[f.verdict]}{f.severity !== 'info' ? ` · ${f.severity}` : ''}</span>
              {firstMark(f)?.page && <span className="text-faint">page {firstMark(f)!.page}</span>}
            </span>
            <h2 className="text-lg font-bold leading-snug">{f.title}</h2>
          </div>
          {f.compare && <CompareBlock c={f.compare} />}
          {f.why_it_matters && <p className="text-[13px] leading-snug text-soft"><span className="text-faint">Why it matters: </span>{f.why_it_matters}</p>}
          <div className="truncate text-xs text-faint">
            {src ? (
              <>Checked against <a href={src.url} target="_blank" rel="noreferrer" className="text-soft underline decoration-edge underline-offset-2 hover:decoration-ink">{src.title || src.url}</a>
                {src.retrieved_at ? ` · ${new Date(src.retrieved_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}</>
            ) : <>Checked against spec {f.spec_ref || 'section'}{result.document_revision ? ` · sheet ${result.document_revision}` : ''}</>}
          </div>
          {f.fix && <FixPanel fix={f.fix} attach={attach} onAttach={setAttach} />}
        </>
      ) : (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-good">No problems</span>
          <h2 className="text-lg font-bold">All {plural(passed, 'check')} passed</h2>
          <p className="text-muted">{result.summary}</p>
        </div>
      )}
      <Note text={note} />
    </div>
  )
}

function Note({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  if (!text) return null
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">Note to send</span>
        <button onClick={() => navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })}
          className="btn h-7">{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <p className="whitespace-pre-line rounded-lg border border-line bg-well p-3 leading-relaxed">{text}</p>
    </div>
  )
}

// ---------- results ----------

const PROBLEM: Record<string, string> = {
  spec: 'spec', currency: 'out of date', validity: 'listing', status: 'discontinued', currency_note: 'newer, same values', completeness: 'missing',
}
const callOf = (d: Decision, problems: string[]) =>
  `${DECISION_LABEL[d]}${problems.length ? `: ${problems.map((p) => PROBLEM[p] ?? p).join(', ')}` : ''}`

function Stat({ value, of, label, accent }: { value: ReactNode; of?: number; label: string; accent?: boolean }) {
  return (
    <div className={`panel flex flex-col gap-1.5 p-3.5 ${accent ? '!border-flare/35' : ''}`}>
      <span className={`text-[26px] font-bold tabular-nums ${accent ? 'text-[#F5A35A]' : ''}`}>
        {value}{of !== undefined && <span className="text-[15px] font-semibold text-faint"> / {of}</span>}
      </span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  )
}

function Results() {
  const [scores, setScores] = useState<Scores | null | undefined>(undefined)
  useEffect(() => { getScores().then(setScores) }, [])
  if (scores === undefined) return <p className="text-muted">Loading…</p>
  if (scores === null) {
    return (
      <section className="panel flex flex-col gap-2 p-6">
        <h1 className="text-[24px] font-bold tracking-tight">No scores yet</h1>
        <p className="text-muted">Run <code className="font-mono text-soft">python scripts/eval.py</code> to score all 8 cases against the answer key.</p>
      </section>
    )
  }
  const s = scores
  const when = new Date(s.generated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  const ph = s.fixes_passing.placeholders
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[28px] font-bold tracking-tight">How well it works</h1>
          <span className="text-muted">{s.rows.length} real submittals with a known answer, run end to end.</span>
        </div>
        <span className="font-mono text-xs text-faint">{s.mode} run {s.run_id.slice(-6)} · {when}</span>
      </section>

      {s.mode !== 'live' && (
        <p className="rounded-lg border border-line bg-well px-3.5 py-2.5 text-xs text-soft">
          Mock mode: model and web answers are replayed from recorded fixtures, so time is near zero and cost uses placeholder prices.
          {ph > 0 && ` ${ph} of the passing fixes ${ph === 1 ? 'is a placeholder' : 'are placeholders'} that a live run fills in.`}
        </p>
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat value={s.right_call.n} of={s.right_call.of} label="Right call" />
        <Stat value={s.caught.n} of={s.caught.of} label="Problems caught" />
        <Stat value={s.false_alarms.n} of={s.false_alarms.of} label="False alarms on clean items" />
        <Stat value={s.fixes_passing.n} of={s.fixes_passing.of} label={`Fixes that pass the spec${ph ? ` (${ph} placeholder)` : ''}`} accent />
        <Stat value={`${(s.time_ms_per_item / 1000).toFixed(1)} s`} label="Per submittal" />
        <Stat value={`$${s.cost_usd_per_item.toFixed(3)}`} label="Per submittal, models + search" />
      </section>

      <section className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left">
            <thead className="font-mono text-[11px] text-faint">
              <tr className="border-b border-line">
                {['Case', 'Document', 'Answer key', 'SpecCheck', 'Fix', 'Time', 'Cost'].map((h, i) => (
                  <th key={h} className={`px-4 py-2.5 font-normal ${i >= 5 ? 'text-right' : ''}`}>{h.toUpperCase()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {s.rows.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-3 font-mono text-xs text-muted">{r.id}</td>
                  <td className="px-4 py-3">{r.title}</td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2">
                      <span className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ background: DECISION_COLOR[r.expected] }} />
                      {callOf(r.expected, r.expected_problems)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {r.error || !r.decision ? <span className={BAD}>Error</span> : (
                      <span className={`flex items-center gap-1.5 ${r.right_call && r.caught === r.expected_problems.length ? '' : BAD}`}>
                        <span className={r.right_call ? 'text-good' : BAD}><Icon kind={r.right_call ? 'check' : 'x'} /></span>
                        {callOf(r.decision, r.found_problems ?? [])}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {!r.fix ? 'none needed' : r.fix.passes
                      ? <span className="flex items-center gap-1.5"><span className="text-good"><Icon kind="check" /></span>
                          <span className={r.fix.placeholder ? 'text-faint' : 'text-soft'}>{r.fix.placeholder ? 'placeholder' : r.fix.suggest}</span></span>
                      : <span className={BAD}>no passing fix</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-xs tabular-nums text-muted">{r.time_ms !== undefined ? `${(r.time_ms / 1000).toFixed(1)} s` : '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-xs tabular-nums text-muted">{r.cost_usd !== undefined ? `$${r.cost_usd.toFixed(3)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel grid gap-2 p-5 text-soft sm:grid-cols-3 sm:gap-6">
        <span><b className="text-ink">Right call:</b> approve, approve with note, or send back matches the key.</span>
        <span><b className="text-ink">Caught:</b> the problem type matches too (spec, listing, out of date, discontinued).</span>
        <span><b className="text-ink">Fix passes:</b> the suggested sheet or product clears the same checks as a new submittal.</span>
      </section>
    </>
  )
}
