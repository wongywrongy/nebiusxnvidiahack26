import { forwardRef, Fragment, useEffect, useImperativeHandle, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, getCaseText, getDocPages, getProject, getResult, pageUrl, startReplay, startRun, streamEvents,
  type Case, type Compare, type CompareRow, type Decision, type DocPages, type Event, type Finding, type Mark,
  type Project, type Result, type Stage, type TextPage, type Tone, type Value,
} from './api'

type View = 'ready' | 'running' | 'done' | 'detail'
type CaseState = { stage: Stage; message: string; model: string | null; decision?: Decision; summary?: string }

const ACTIVE: Stage[] = ['ingest', 'triage', 'extract', 'spec_check', 'verify', 'reconcile', 'report']
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

  useEffect(() => { getProject().then(setProject) }, [])

  const cases = project?.cases ?? []
  const openable = cases.filter((c) => states[c.id]?.stage === 'done').map((c) => c.id)

  async function load(id: string, caseId: string): Promise<Loaded> {
    const files = cases.find((c) => c.id === caseId)?.submittal.map((d) => d.file) ?? []
    const [result, ...found] = await Promise.all([getResult(id, caseId), ...files.map((f) => getDocPages(caseId, f))])
    const docs = found.length && found.every(Boolean) ? (found as DocPages[]) : null
    const l = { result: result as Result, docs, text: docs ? null : await getCaseText(caseId) }
    setLoaded((m) => ({ ...m, [caseId]: l }))
    return l
  }

  function follow(id: string) {
    setStates({})
    setLoaded({})
    setRunId(id)
    setRunDone(false)
    setView('running')
    streamEvents(id, (e: Event) => {
      if (!e.case_id) return
      if (e.stage === 'done') load(id, e.case_id) // prefetch, so opening and switching are instant
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
    }, () => {
      setRunDone(true)
      // Move on only if the reviewer is still watching the run, never out of a result they opened.
      setTimeout(() => setView((v) => (v === 'running' ? 'done' : v)), 900)
    })
  }

  async function run() {
    if (project) follow(await startRun(project.cases.map((c) => c.id)))
  }

  async function replay() {
    if (runId) follow(await startReplay(runId))
  }

  async function open(caseId: string) {
    if (!runId || !openable.includes(caseId)) return
    if (!loaded[caseId]) await load(runId, caseId)
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
          <span className="truncate text-muted">{project?.name ?? '…'}</span>
        </div>
        {detail
          ? <Verdict result={detail.result} />
          : <span className="font-mono text-[11px] text-faint">Nemotron on Nebius · Tavily</span>}
      </header>

      {detail && (
        <DocSwitcher cases={cases} states={states} current={current!} openable={openable} onOpen={open} onAll={overview} />
      )}

      <main className={detail ? 'mx-auto max-w-[1680px] px-4 py-4' : 'mx-auto flex max-w-[1120px] flex-col gap-7 px-4 py-10 sm:px-6 sm:py-12'}>
        {view === 'ready' && <Ready cases={cases} onRun={run} />}
        {view === 'running' && <Running cases={cases} states={states} done={openable.length} onOpen={open} />}
        {view === 'done' && <Done cases={cases} states={states} onOpen={open} onAgain={run} />}
        {detail && <Detail key={current} result={detail.result} docs={detail.docs} text={detail.text} runId={runId!} onReplay={replay} />}
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

function Ready({ cases, onRun }: { cases: Case[]; onRun: () => void }) {
  return (
    <>
      <section className="flex flex-col items-center gap-4 pt-6 text-center">
        <h1 className="text-[40px] font-bold leading-tight tracking-tight">{cases.length} submittals are waiting for review</h1>
        <p className="max-w-[540px] text-[15px] text-muted">
          SpecCheck reads each package, compares it to the spec, and checks the manufacturer's current documents online.
        </p>
        <button onClick={onRun} className="flare mt-3 h-[52px] rounded-[10px] px-7 text-base font-bold">
          Review all {cases.length} submittals
        </button>
      </section>
      <section className="panel grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-px overflow-hidden bg-line">
        {cases.map((c) => (
          <div key={c.id} className="flex flex-col gap-1 bg-panel px-4 py-3.5">
            <span>{c.title}</span>
            <span className="font-mono text-[11px] text-faint">{c.section}</span>
          </div>
        ))}
      </section>
    </>
  )
}

function Running({ cases, states, done, onOpen }: {
  cases: Case[]; states: Record<string, CaseState>; done: number; onOpen: (id: string) => void
}) {
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight">Nemotron is reviewing {cases.length} submittals</h1>
          <p className="text-muted">Each package is read, checked against the spec, then checked against the manufacturer's site. Open any finished card.</p>
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
                <span className="h-4 truncate font-mono text-[11px] leading-4 text-faint">{(active && s?.model) || NBSP}</span>
              </div>
            </button>
          )
        })}
      </section>
    </>
  )
}

function Done({ cases, states, onOpen, onAgain }: {
  cases: Case[]; states: Record<string, CaseState>; onOpen: (id: string) => void; onAgain: () => void
}) {
  const sendBack = cases.filter((c) => states[c.id]?.decision === 'send_back').length
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-5">
        <h1 className="text-[30px] font-bold tracking-tight">
          {sendBack} submittal{sendBack === 1 ? '' : 's'} need{sendBack === 1 ? 's' : ''} to go back
        </h1>
        <button onClick={onAgain} className="btn h-9 px-3.5">Run again</button>
      </section>
      <section className="panel overflow-hidden">
        {cases.map((c) => {
          const s = states[c.id]
          return (
            <button key={c.id} onClick={() => onOpen(c.id)} disabled={!s?.decision}
              className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-line px-4 py-3 text-left last:border-b-0 enabled:hover:bg-raised disabled:cursor-not-allowed md:min-h-14 md:grid-cols-[minmax(0,1fr)_170px_minmax(0,1.4fr)_64px] md:py-2">
              <span className="font-medium md:font-normal">{c.title}</span>
              <span className="flex items-center gap-2 justify-self-end font-medium md:justify-self-auto">
                {s?.decision && <span className="h-[7px] w-[7px] rounded-full" style={{ background: DECISION_COLOR[s.decision] }} />}
                {s?.decision ? DECISION_LABEL[s.decision] : s?.stage === 'error' ? 'Error' : '—'}
              </span>
              <span className="col-span-2 text-muted md:col-span-1">{s?.summary}</span>
              <span className="hidden text-right text-muted md:block">{s?.decision ? 'Open →' : ''}</span>
            </button>
          )
        })}
      </section>
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
  result: Result; docs: DocPages[] | null; text: TextPage[] | null; runId: string; onReplay: () => void
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

function HowChecked({ result, runId, onReplay }: { result: Result; runId: string; onReplay: () => void }) {
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
      <button onClick={onReplay} className="w-full border-t border-line px-3.5 py-2.5 text-left text-flare hover:bg-raised">
        Replay run {runId.slice(-6)} →
      </button>
    </div>
  )
}

function Icon({ kind }: { kind: 'x' | 'check' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden className="shrink-0">
      <path d={kind === 'x' ? 'm4 4 8 8M12 4l-8 8' : 'm3.5 8.5 3 3 6-7'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const CAPS = 'text-[10px] font-medium uppercase tracking-[0.08em] text-faint'
const BIG = 'text-[20px] font-semibold leading-tight'
const show = (v: Value) => (v === null || v === undefined ? '—' : String(v))

// Lists as chips. On the "needs" side, an item the other side lacks is a red outlined chip.
function Chips({ items, against, fail }: { items: string[]; against?: Value; fail?: boolean }) {
  const other = (Array.isArray(against) ? against : [show(against ?? null)]).join(' | ').toLowerCase()
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((it) => {
        const missing = fail && against !== undefined && !other.includes(it.toLowerCase())
        return (
          <span key={it} className={`rounded-md border px-2 py-0.5 text-xs ${missing ? 'border-bad font-semibold text-[#ff8a84]' : 'border-line bg-well text-soft'}`}>
            {it}
          </span>
        )
      })}
    </div>
  )
}

function Side({ label, value, against, tone }: { label: string; value: Value; against?: Value; tone?: 'fail' | 'pass' | 'changed' }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className={CAPS}>{label}</span>
      {Array.isArray(value)
        ? <Chips items={value} against={against} fail={against !== undefined} />
        : <span className={`flex items-center gap-1.5 ${BIG} ${tone === 'fail' ? 'text-[#ff8a84]' : tone === 'changed' ? 'text-today' : 'text-ink'}`}>
            {show(value)}{tone === 'fail' && <Icon kind="x" />}{tone === 'pass' && <span className="text-good"><Icon kind="check" /></span>}
          </span>}
    </div>
  )
}

function CompareBlock({ c }: { c: Compare }) {
  if (c.rows.length) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-line bg-well p-3.5">
        <div className="grid grid-cols-2 gap-3">
          <span className={CAPS}>{c.left_label}</span><span className={CAPS}>{c.right_label}</span>
        </div>
        {c.rows.map((r) => (
          <div key={r.property} className="flex flex-col gap-1">
            <span className="text-xs text-muted">{r.label}</span>
            <div className="grid grid-cols-2 items-baseline gap-3">
              <span className={`${BIG} text-muted line-through decoration-1`}>{r.submitted ?? '—'}</span>
              <span className={`${BIG} text-today`}><span className="mr-1.5 text-sm text-faint" aria-hidden>→</span>{r.current ?? '—'}</span>
            </div>
          </div>
        ))}
      </div>
    )
  }
  if (c.left_value === null || c.left_value === undefined) { // single fact, e.g. Status: Discontinued June 30, 2024
    return (
      <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-well p-3.5">
        <span className={CAPS}>{c.left_label}</span>
        <span className={`flex items-center gap-1.5 ${BIG} ${c.verdict === 'fail' ? 'text-[#ff8a84]' : 'text-ink'}`}>
          {show(c.right_value)}{c.verdict === 'fail' && <Icon kind="x" />}
        </span>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 gap-4 rounded-lg border border-line bg-well p-3.5">
      <Side label={c.left_label} value={c.left_value} against={c.verdict === 'fail' ? c.right_value : undefined} />
      <Side label={c.right_label} value={c.right_value} tone={c.verdict} />
    </div>
  )
}

function FindingCard({ finding: f, result, passed }: { finding: Finding | null; result: Result; passed: number }) {
  const src = f?.evidence[0]
  return (
    <div className="panel flex flex-col gap-4 p-5">
      {f ? (
        <>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="text-xs" style={{ color: TONE_COLOR[toneOf(f)] }}>
              {LABEL[f.verdict]}{f.severity !== 'info' ? ` · ${f.severity}` : ''}
            </span>
            <h2 className="truncate text-lg font-bold" title={f.title}>{f.title}</h2>
          </div>
          {f.compare && <CompareBlock c={f.compare} />}
          {f.why_it_matters && <p className="text-[13px] leading-snug text-soft"><span className="text-faint">Why it matters: </span>{f.why_it_matters}</p>}
          <div className="truncate text-xs text-faint">
            {src ? (
              <>Checked against <a href={src.url} target="_blank" rel="noreferrer" className="text-soft underline decoration-edge underline-offset-2 hover:decoration-ink">{src.title || src.url}</a>
                {src.retrieved_at ? ` · ${new Date(src.retrieved_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}` : ''}</>
            ) : <>Checked against spec {f.spec_ref || 'section'}{result.document_revision ? ` · sheet ${result.document_revision}` : ''}</>}
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-good">No problems</span>
          <h2 className="text-lg font-bold">All {plural(passed, 'check')} passed</h2>
          <p className="text-muted">{result.summary}</p>
        </div>
      )}
      <Note text={result.note_to_subcontractor} />
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
      <p className="rounded-lg border border-line bg-well p-3 leading-relaxed">{text}</p>
    </div>
  )
}
