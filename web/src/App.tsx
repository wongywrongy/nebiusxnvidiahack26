import { useEffect, useMemo, useState } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, getProject, getResult, startRun, streamEvents,
  type Case, type Decision, type Event, type Finding, type Project, type Result, type Stage,
} from './api'

type View = 'ready' | 'running' | 'done' | 'detail'
type CaseState = { stage: Stage; message: string; model: string | null; decision?: Decision; summary?: string }

const ACTIVE: Stage[] = ['ingest', 'triage', 'extract', 'spec_check', 'verify', 'reconcile', 'report']

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [view, setView] = useState<View>('ready')
  const [runId, setRunId] = useState<string | null>(null)
  const [states, setStates] = useState<Record<string, CaseState>>({})
  const [result, setResult] = useState<Result | null>(null)

  useEffect(() => { getProject().then(setProject) }, [])

  async function run() {
    if (!project) return
    setStates({})
    setView('running')
    const id = await startRun(project.cases.map((c) => c.id))
    setRunId(id)
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

  async function open(caseId: string) {
    if (!runId) return
    setResult(await getResult(runId, caseId))
    setView('detail')
  }

  const cases = project?.cases ?? []
  const doneCount = cases.filter((c) => states[c.id]?.stage === 'done').length

  return (
    <div className="min-h-screen font-sans text-[13px]">
      <header className="flex h-[52px] items-center justify-between border-b border-white/5 px-6">
        <div className="flex items-center gap-2.5">
          <button onClick={() => setView(runId && view === 'detail' ? 'done' : 'ready')} className="flex items-center gap-2 font-semibold">
            <span className="flare h-3.5 w-3.5 rounded" />SpecCheck
          </button>
          <span className="text-[#3a3d43]">/</span>
          <span>{project?.name ?? '…'}</span>
        </div>
        <span className="font-mono text-[11px] text-faint">Nemotron on Nebius · Tavily</span>
      </header>

      <main className="mx-auto flex max-w-[1120px] flex-col gap-7 px-6 py-12">
        {view === 'ready' && <Ready cases={cases} onRun={run} />}
        {view === 'running' && <Running cases={cases} states={states} done={doneCount} />}
        {view === 'done' && <Done cases={cases} states={states} onOpen={open} onAgain={() => setView('ready')} />}
        {view === 'detail' && result && <Detail result={result} onBack={() => setView('done')} />}
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
          <span className="text-right font-mono text-xs">{done} of {cases.length} done</span>
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
            <div key={c.id} className={`panel flex flex-col gap-3 p-3.5 ${s ? '' : 'opacity-55'}`}>
              <div className="relative flex h-28 flex-col gap-[7px] overflow-hidden rounded bg-[#edebe6] p-3">
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
                <span className="font-medium">{c.title}</span>
                <span className={`text-xs ${active ? 'blink' : 'text-muted'}`}>{s?.message ?? 'Waiting'}</span>
                <span className="font-mono text-[11px] text-faint">{active ? s?.model ?? '' : ''}</span>
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

function Detail({ result, onBack }: { result: Result; onBack: () => void }) {
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass'), [result])
  const passed = result.findings.length - issues.length
  const [sel, setSel] = useState<Finding | null>(issues[0] ?? null)
  const [showHow, setShowHow] = useState(true)
  const tokens = result.usage.reduce((a, u) => a + u.input_tokens + u.output_tokens, 0)

  return (
    <>
      <section className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="h-3 w-3 rounded-full" style={{ background: DECISION_COLOR[result.decision], boxShadow: `0 0 12px ${DECISION_COLOR[result.decision]}` }} />
          <div>
            <h1 className="text-[28px] font-bold tracking-tight">{result.title}: {DECISION_LABEL[result.decision]}</h1>
            <p className="text-muted">{result.summary}</p>
          </div>
        </div>
        <button onClick={onBack} className="h-9 rounded-lg border border-[#2a2d32] px-3">← All submittals</button>
      </section>

      <div className="flex flex-wrap gap-5">
        <nav className="panel w-[360px] max-w-full self-start overflow-hidden">
          {issues.map((f) => (
            <button key={f.id} onClick={() => setSel(f)}
              className={`flex w-full flex-col gap-1 border-b border-[#1b1d21] px-4 py-3.5 text-left ${sel?.id === f.id ? 'border-l-2 border-l-flare bg-[#15171b]' : 'hover:bg-[#15171b]'}`}>
              <span className="text-xs" style={{ color: f.verdict === 'fail' ? '#e57373' : f.verdict === 'outdated' ? '#e5a93b' : '#8b8f98' }}>
                {f.verdict === 'fail' ? 'Must fix' : f.verdict === 'outdated' ? 'Out of date' : f.verdict === 'note' ? 'Note' : 'Not stated'}
              </span>
              <span className="text-sm">{f.title}</span>
            </button>
          ))}
          <div className="px-4 py-3 text-muted">{passed} checks passed</div>
        </nav>

        <section className="panel flex min-w-0 flex-1 basis-[560px] flex-col gap-6 p-7 text-sm">
          {sel ? (
            <div className="flex flex-col gap-2">
              <h2 className="text-[22px] font-bold">{sel.title}</h2>
              <p className="text-[#b9bdc6]">{sel.detail}</p>
              {sel.why_it_matters && (
                <p className="rounded-[10px] border border-warn/20 bg-warn/5 px-4 py-3"><b>Why it matters:</b> {sel.why_it_matters}</p>
              )}
            </div>
          ) : <h2 className="text-[22px] font-bold">No problems found</h2>}

          {result.comparison.length > 0 && (
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-x-4 gap-y-2.5">
              <span className="text-muted">Property</span><span className="text-muted">What they sent</span>
              <span className="text-[#f5c25e]">What the manufacturer says today</span>
              {result.comparison.map((r) => (
                <Row key={r.property} label={r.label} a={r.submitted} b={r.current} changed={r.changed} />
              ))}
            </div>
          )}

          {sel && sel.evidence.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-muted">Where we checked</span>
              {sel.evidence.map((e) => (
                <a key={e.url} href={e.url} target="_blank" rel="noreferrer"
                  className="flex justify-between gap-4 rounded-lg border border-[#1b1d21] px-3.5 py-3 hover:bg-[#15171b]">
                  <span>{e.title}</span><span className="font-mono text-xs text-faint">{e.tier}</span>
                </a>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-muted">Note to send back</span>
              <button onClick={() => navigator.clipboard.writeText(result.note_to_subcontractor)}
                className="h-7 rounded-md border border-[#2a2d32] px-3 text-xs">Copy</button>
            </div>
            <p className="rounded-lg border border-[#23262c] bg-[#0d0e11] p-3">{result.note_to_subcontractor}</p>
          </div>

          <div className="flex flex-col gap-2 border-t border-[#1b1d21] pt-5">
            <button onClick={() => setShowHow(!showHow)} className="flex justify-between font-medium">
              How this was checked <span className="font-mono text-xs text-muted">{showHow ? 'hide' : 'show'}</span>
            </button>
            {showHow && (
              <div className="overflow-hidden rounded-[10px] border border-[#1b1d21] font-mono text-xs">
                {result.usage.map((u, i) => (
                  <div key={i} className="grid grid-cols-[1fr_1.4fr_1fr] gap-3 border-t border-[#1b1d21] px-3.5 py-2.5 first:border-t-0">
                    <span>{u.task}</span><span className="text-muted">{u.model}</span>
                    <span className="text-right text-faint">{u.input_tokens + u.output_tokens} tok</span>
                  </div>
                ))}
                <div className="border-t border-[#1b1d21] bg-white/[0.02] px-3.5 py-2.5 text-muted">
                  {tokens.toLocaleString()} tokens · {result.web_credits} Tavily credits · {(result.duration_ms / 1000).toFixed(1)} s
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </>
  )
}

function Row({ label, a, b, changed }: { label: string; a: string | null; b: string | null; changed: boolean }) {
  return (
    <>
      <span className={changed ? '' : 'text-muted'}>{label}</span>
      <span className={changed ? 'text-muted line-through' : ''}>{a ?? '—'}</span>
      <span className={changed ? 'font-semibold text-[#f5c25e]' : ''}>{b ?? '—'}</span>
    </>
  )
}
