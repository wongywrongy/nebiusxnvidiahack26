import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, getHighlights, getProject, getResult, startReplay, startRun, streamEvents,
  type Case, type CompareRow, type Decision, type Event, type Finding, type Highlight, type Highlights, type Page,
  type Project, type Result, type Stage, type Tone,
} from './api'

type View = 'ready' | 'running' | 'done' | 'detail'
type CaseState = { stage: Stage; message: string; model: string | null; decision?: Decision; summary?: string }

const ACTIVE: Stage[] = ['ingest', 'triage', 'extract', 'spec_check', 'verify', 'reconcile', 'report']
const NBSP = '\u00a0'

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [view, setView] = useState<View>('ready')
  const [runId, setRunId] = useState<string | null>(null)
  const [states, setStates] = useState<Record<string, CaseState>>({})
  const [detail, setDetail] = useState<{ result: Result; hl: Highlights } | null>(null)

  useEffect(() => { getProject().then(setProject) }, [])

  function follow(id: string) {
    setStates({})
    setRunId(id)
    setView('running')
    streamEvents(id, (e: Event) => {
      if (!e.case_id) return
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
    }, () => setTimeout(() => setView('done'), 900))
  }

  async function run() {
    if (project) follow(await startRun(project.cases.map((c) => c.id)))
  }

  async function replay() {
    if (runId) follow(await startReplay(runId))
  }

  async function open(caseId: string) {
    if (!runId) return
    const [result, hl] = await Promise.all([getResult(runId, caseId), getHighlights(runId, caseId)])
    setDetail({ result, hl })
    setView('detail')
  }

  const cases = project?.cases ?? []
  const doneCount = cases.filter((c) => states[c.id]?.stage === 'done').length
  const inDetail = view === 'detail' && detail

  return (
    <div className="min-h-screen font-sans text-[13px]">
      <header className="flex min-h-[52px] flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-white/5 px-6 py-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <button onClick={() => setView(runId && view === 'detail' ? 'done' : 'ready')} className="flex shrink-0 items-center gap-2 font-semibold">
            <span className="flare h-3.5 w-3.5 rounded" />SpecCheck
          </button>
          <span className="text-[#3a3d43]">/</span>
          <span className={inDetail ? 'shrink-0 text-muted' : ''}>{project?.name ?? '…'}</span>
          {inDetail && <><span className="text-[#3a3d43]">/</span><span className="truncate">{detail.result.title}</span></>}
        </div>
        {inDetail
          ? <Verdict result={detail.result} onBack={() => setView('done')} />
          : <span className="font-mono text-[11px] text-faint">Nemotron on Nebius · Tavily</span>}
      </header>

      <main className={inDetail ? 'mx-auto max-w-[1680px] px-4 py-4' : 'mx-auto flex max-w-[1120px] flex-col gap-7 px-6 py-12'}>
        {view === 'ready' && <Ready cases={cases} onRun={run} />}
        {view === 'running' && <Running cases={cases} states={states} done={doneCount} />}
        {view === 'done' && <Done cases={cases} states={states} onOpen={open} onAgain={() => setView('ready')} />}
        {inDetail && <Detail result={detail.result} hl={detail.hl} runId={runId!} onReplay={replay} />}
      </main>
    </div>
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

function Running({ cases, states, done }: { cases: Case[]; states: Record<string, CaseState>; done: number }) {
  return (
    <>
      <section className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight">Nemotron is reviewing {cases.length} submittals</h1>
          <p className="text-muted">Each package is read, checked against the spec, then checked against the manufacturer's site.</p>
        </div>
        <div className="flex min-w-[200px] flex-col gap-1.5">
          <span className="text-right font-mono text-xs tabular-nums">{done} of {cases.length} done</span>
          <div className="h-1 rounded bg-[#1b1d21]">
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
            <div key={c.id} className={`panel flex h-[214px] flex-col gap-3 p-3.5 ${s ? '' : 'opacity-55'}`}>
              <div className="relative flex h-28 shrink-0 flex-col gap-[7px] overflow-hidden rounded bg-[#edebe6] p-3">
                {[60, 88, 80, 84, 70, 76].map((w, i) => (
                  <div key={i} className="h-1 bg-[#d2cfc7]" style={{ width: `${w}%`, height: i === 0 ? 6 : 4 }} />
                ))}
                {active && <div className="scan absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-[#f5791a] to-transparent shadow-[0_0_10px_2px_rgba(245,121,26,0.6)]" />}
                {finished && s.decision && (
                  <div className="pop absolute inset-0 flex items-center justify-center bg-[#111317]/55">
                    <span className="rounded-md px-3 py-1.5 font-bold text-white" style={{ background: DECISION_COLOR[s.decision] }}>
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
            </div>
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
        <button onClick={onAgain} className="h-9 rounded-lg border border-[#2e3238] px-3.5">Run again</button>
      </section>
      <section className="panel overflow-hidden">
        {cases.map((c) => {
          const s = states[c.id]
          return (
            <button key={c.id} onClick={() => onOpen(c.id)}
              className="grid min-h-14 w-full grid-cols-[minmax(0,1fr)_180px_minmax(0,1.4fr)_60px] items-center gap-4 border-b border-[#1b1d21] px-4 text-left hover:bg-[#15171b]">
              <span>{c.title}</span>
              <span className="flex items-center gap-2 font-medium">
                {s?.decision && <span className="h-[7px] w-[7px] rounded-full" style={{ background: DECISION_COLOR[s.decision] }} />}
                {s?.decision ? DECISION_LABEL[s.decision] : s?.stage === 'error' ? 'Error' : '—'}
              </span>
              <span className="text-muted">{s?.summary}</span>
              <span className="text-right text-muted">Open →</span>
            </button>
          )
        })}
      </section>
    </>
  )
}


// ---------- result view ----------

const TONE_COLOR: Record<Tone, string> = { red: '#e5534b', amber: '#e5a93b', gray: '#8b8f98' }
const TONE_RANK: Record<Tone, number> = { red: 0, amber: 1, gray: 2 }
const toneOf = (f: Finding): Tone => (f.verdict === 'fail' ? 'red' : f.verdict === 'outdated' ? 'amber' : 'gray')
const LABEL: Record<Finding['verdict'], string> = {
  fail: 'Must fix', outdated: 'Out of date', note: 'Note', unverified: 'Not stated', pass: 'Passed',
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

function Verdict({ result, onBack }: { result: Result; onBack: () => void }) {
  const color = DECISION_COLOR[result.decision]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="flex items-center gap-2 font-semibold">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 10px ${color}` }} />
        {DECISION_LABEL[result.decision]}
      </span>
      <span className="flex gap-3 text-xs tabular-nums text-muted">
        {counts(result).map(([n, label, tone]) => (
          <span key={label} style={tone ? { color: TONE_COLOR[tone] } : undefined}>{n} {label}</span>
        ))}
      </span>
      <button onClick={onBack} className="h-8 rounded-lg border border-[#2a2d32] px-3 text-xs">← All submittals</button>
    </div>
  )
}

function Detail({ result, hl, runId, onReplay }: { result: Result; hl: Highlights; runId: string; onReplay: () => void }) {
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass'), [result])
  const [selId, setSelId] = useState<string | null>(issues[0]?.id ?? null)
  const sel = issues.find((f) => f.id === selId) ?? null
  const pageOf = (f: Finding) => hl.highlights.find((h) => h.finding_id === f.id)?.page ?? null
  const [page, setPage] = useState<number>((sel && pageOf(sel)) ?? 1)

  function select(f: Finding) {
    setSelId(f.id)
    setPage(pageOf(f) ?? page)
  }

  return (
    <div className="grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[270px_minmax(0,1fr)_360px]">
      <aside className="flex min-w-0 flex-col gap-4">
        <nav className="panel overflow-hidden">
          {issues.map((f) => {
            const p = pageOf(f)
            return (
              <button key={f.id} onClick={() => select(f)}
                className={`flex w-full flex-col gap-1 border-b border-l-2 border-b-[#1b1d21] px-3.5 py-3 text-left ${sel?.id === f.id ? 'border-l-flare bg-[#15171b]' : 'border-l-transparent hover:bg-[#15171b]'}`}>
                <span className="flex justify-between text-xs">
                  <span style={{ color: TONE_COLOR[toneOf(f)] }}>{LABEL[f.verdict]}</span>
                  <span className="font-mono text-faint">{p ? `p. ${p}` : notFound(f) ? 'not found' : 'whole doc'}</span>
                </span>
                <span className="leading-snug">{f.title}</span>
              </button>
            )
          })}
          <div className="px-3.5 py-3 text-muted">
            {issues.length ? '' : 'No problems found. '}{result.findings.length - issues.length} checks passed
          </div>
        </nav>
        <HowChecked result={result} runId={runId} onReplay={onReplay} />
      </aside>

      <section className="panel flex min-w-0 flex-col gap-4 p-4">
        <PageStrip pages={hl.pages} highlights={hl.highlights} findings={issues} current={page} onPick={setPage} />
        {sel && notFound(sel)
          ? <NotFound finding={sel} pages={hl.pages} caseId={result.case_id} />
          : <>
              {sel && sel.claim_ids.length === 0 && (
                <p className="text-xs text-muted">This applies to the whole document, not one spot on a page.</p>
              )}
              <PageView caseId={result.case_id} page={hl.pages.find((p) => p.page === page)}
                highlights={hl.highlights.filter((h) => h.page === page)} selId={sel?.id ?? null} result={result} />
            </>}
      </section>

      <aside className="flex min-w-0 flex-col gap-4">
        <FindingCard finding={sel} result={result} />
        <Note text={result.note_to_subcontractor} />
      </aside>
    </div>
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
      <div className="mt-2 flex flex-wrap justify-between gap-x-3 gap-y-1 border-t border-[#1b1d21] px-3.5 py-2.5 tabular-nums text-muted">
        <span>{tokens.toLocaleString()} tok</span>
        <span>${cost.toFixed(4)} + {result.web_credits} credits</span>
        <span>{(result.duration_ms / 1000).toFixed(1)} s</span>
      </div>
      <button onClick={onReplay} className="w-full border-t border-[#1b1d21] px-3.5 py-2.5 text-left text-flare hover:bg-[#15171b]">
        Replay run {runId.slice(-6)} →
      </button>
    </div>
  )
}

function PageStrip({ pages, highlights, findings, current, onPick }: {
  pages: Page[]; highlights: Highlight[]; findings: Finding[]; current: number; onPick: (n: number) => void
}) {
  const live = new Set(findings.map((f) => f.id))
  const tone = (n: number) => highlights.filter((h) => h.page === n && live.has(h.finding_id))
    .map((h) => h.tone).sort((a, b) => TONE_RANK[a] - TONE_RANK[b])[0]
  return (
    <div className="flex flex-wrap items-center gap-1 font-mono text-xs">
      <span className="mr-2 font-sans text-muted">Page</span>
      {pages.map((p) => {
        const t = tone(p.page)
        return (
          <button key={p.page} onClick={() => onPick(p.page)}
            className={`h-7 min-w-7 rounded px-2 tabular-nums ${p.page === current ? 'bg-[#23262c] text-ink' : 'text-muted hover:bg-[#15171b]'}`}
            style={{ boxShadow: t ? `inset 0 -2px 0 ${TONE_COLOR[t]}` : undefined }}>
            {p.page}
          </button>
        )
      })}
    </div>
  )
}

function changedRow(result: Result, claimId: string): CompareRow | undefined {
  const claim = result.claims.find((c) => c.id === claimId)
  return claim && result.comparison.find((r) => r.property === claim.property && r.changed)
}

function PageView({ caseId, page, highlights, selId, result }: {
  caseId: string; page?: Page; highlights: Highlight[]; selId: string | null; result: Result
}) {
  if (!page) return <p className="text-muted">No page text available.</p>
  // Selected finding on top, strong; the others faint.
  const ordered = [...highlights].sort((a, b) => Number(a.finding_id === selId) - Number(b.finding_id === selId))

  if (page.image) {
    return (
      <div className="relative mx-auto w-full max-w-[920px] overflow-hidden rounded bg-white">
        <img src={`/api/cases/${caseId}/pages/${page.page}.png`} alt={`Page ${page.page}`} className="block w-full" />
        {ordered.map((h) => {
          const on = h.finding_id === selId
          const c = TONE_COLOR[h.tone]
          const row = on ? changedRow(result, h.claim_id) : undefined
          return h.rects.map((r, i) => (
            <Fragment key={`${h.finding_id}-${h.claim_id}-${i}`}>
              <div className="absolute rounded-sm" style={{
                left: `${r[0] * 100}%`, top: `${r[1] * 100}%`, width: `${(r[2] - r[0]) * 100}%`, height: `${(r[3] - r[1]) * 100}%`,
                background: `${c}${on ? '40' : '18'}`, outline: on ? `2px solid ${c}` : `1px solid ${c}55`, outlineOffset: 1,
              }} />
              {row && i === 0 && (
                <span className="absolute z-10 mt-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold text-[#140a02] shadow"
                  style={{ left: `${r[0] * 100}%`, top: `${r[3] * 100}%`, background: c }}>
                  Today: {row.current}
                </span>
              )}
            </Fragment>
          ))
        })}
      </div>
    )
  }

  // No page image (mock mode): show the page text and mark each quote.
  const text = page.text ?? ''
  const spans = ordered
    .map((h) => ({ h, at: h.quote ? text.indexOf(h.quote) : -1 }))
    .filter((s) => s.at >= 0)
    .sort((a, b) => a.at - b.at)
  const out: ReactNode[] = []
  let pos = 0
  for (const { h, at } of spans) {
    if (at < pos) continue // overlapping quote: keep the first
    const on = h.finding_id === selId
    const c = TONE_COLOR[h.tone]
    const row = on ? changedRow(result, h.claim_id) : undefined
    out.push(text.slice(pos, at))
    out.push(
      <mark key={`${h.finding_id}-${h.claim_id}`} className="rounded-sm px-0.5 text-inherit"
        style={{ background: `${c}${on ? '55' : '22'}`, outline: on ? `2px solid ${c}` : 'none' }}>
        {h.quote}
      </mark>,
    )
    if (row) {
      out.push(
        <span key={`${h.claim_id}-today`} className="ml-1 rounded px-1.5 py-0.5 align-middle font-sans text-[11px] font-semibold text-[#140a02]"
          style={{ background: c }}>Today: {row.current}</span>,
      )
    }
    pos = at + (h.quote?.length ?? 0)
  }
  out.push(text.slice(pos))
  return (
    <div className="mx-auto w-full max-w-[920px] rounded bg-[#edebe6] p-8 font-serif text-[15px] leading-8 text-[#1d1f23]">
      <div className="mb-4 font-sans text-[11px] uppercase tracking-wide text-[#8a867c]">Page {page.page} · text from the package</div>
      {out}
    </div>
  )
}

function NotFound({ finding, pages, caseId }: { finding: Finding; pages: Page[]; caseId: string }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-base font-semibold">All {pages.length} page{pages.length === 1 ? '' : 's'} searched, not found</h3>
        <p className="text-muted">
          Expected: {finding.title.replace(/^Not stated in the package: |^Missing: /, '')}
          {finding.spec_ref ? <span className="font-mono text-xs text-faint"> · spec {finding.spec_ref}</span> : null}
        </p>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
        {pages.map((p) => (
          <div key={p.page} className="flex flex-col gap-1">
            {p.image
              ? <img src={`/api/cases/${caseId}/pages/${p.page}.png`} alt={`Page ${p.page}`} className="aspect-[17/22] w-full rounded bg-white object-cover object-top opacity-80" />
              : <div className="aspect-[17/22] overflow-hidden rounded bg-[#edebe6] p-2 font-serif text-[7px] leading-[10px] text-[#55524a]">{p.text}</div>}
            <span className="font-mono text-[11px] text-faint">p. {p.page}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function FindingCard({ finding: f, result }: { finding: Finding | null; result: Result }) {
  if (!f) {
    return (
      <div className="panel flex flex-col gap-2 p-5">
        <span className="text-xs text-good">No problems</span>
        <h2 className="text-lg font-bold leading-snug">All {result.findings.length} checks passed</h2>
        <p className="text-muted">{result.summary}</p>
      </div>
    )
  }
  const props = new Set(result.claims.filter((c) => f.claim_ids.includes(c.id)).map((c) => c.property))
  const rows = f.check === 'currency' ? result.comparison : result.comparison.filter((r) => props.has(r.property))
  const src = f.evidence[0]
  return (
    <div className="panel flex flex-col gap-4 p-5">
      <div className="flex flex-col gap-1.5">
        <span className="text-xs" style={{ color: TONE_COLOR[toneOf(f)] }}>
          {LABEL[f.verdict]}{f.severity !== 'info' ? ` · ${f.severity}` : ''}
        </span>
        <h2 className="text-lg font-bold leading-snug">{f.title}</h2>
        {f.detail && <p className="text-[#b9bdc6]">{f.detail}</p>}
      </div>

      {rows.length > 0 && (
        <div className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-xs">
          <span className="text-faint" /><span className="text-faint">Sent</span><span className="text-[#f5c25e]">Today</span>
          {rows.map((r) => (
            <Fragment key={r.property}>
              <span className={r.changed ? '' : 'text-muted'}>{r.label}</span>
              <span className={r.changed ? 'text-muted line-through' : ''}>{r.submitted ?? '—'}</span>
              <span className={r.changed ? 'font-semibold text-[#f5c25e]' : ''}>{r.current ?? '—'}</span>
            </Fragment>
          ))}
        </div>
      )}

      {f.why_it_matters && (
        <p className="rounded-lg border border-warn/20 bg-warn/5 px-3 py-2.5"><b>Why it matters:</b> {f.why_it_matters}</p>
      )}

      <div className="flex flex-col gap-1 border-t border-[#1b1d21] pt-3 text-xs">
        <span className="text-faint">Checked against</span>
        {src ? (
          <>
            <a href={src.url} target="_blank" rel="noreferrer" className="truncate text-ink underline decoration-[#3a3d43] underline-offset-2 hover:decoration-ink">
              {src.title || src.url}
            </a>
            <span className="font-mono text-[11px] text-faint">
              {src.tier}{src.retrieved_at ? ` · ${new Date(src.retrieved_at).toLocaleString()}` : ''}
              {f.evidence.length > 1 ? ` · +${f.evidence.length - 1} more` : ''}
            </span>
          </>
        ) : (
          <span>Spec {f.spec_ref || 'section'}{result.document_revision ? ` · sheet ${result.document_revision}` : ''}</span>
        )}
      </div>
    </div>
  )
}

function Note({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  if (!text) return null
  return (
    <div className="panel flex flex-col gap-2 p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">Note to the subcontractor</span>
        <button onClick={() => navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })}
          className="h-7 rounded-md border border-[#2a2d32] px-3 text-xs">{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <p className="rounded-lg border border-[#23262c] bg-[#0d0e11] p-3 leading-relaxed">{text}</p>
    </div>
  )
}
