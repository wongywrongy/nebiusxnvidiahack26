import { forwardRef, Fragment, useEffect, useImperativeHandle, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react'
import {
  DECISION_COLOR, DECISION_LABEL, addToInbox, getCaseText, getDocPages, getProject, getResult, pageUrl, scan, streamEvents,
  uploadToInbox,
  type Case, type CompareRow, type Decision, type DocPages, type Finding, type Fix, type Mark, type Project, type Result,
  type Stage, type TextPage, type Tone, type Value,
} from './api'

// Four steps, in order: what came in, what the scan found, the reviewer's call on each, what happened after.
type Step = 1 | 2 | 3 | 4
const STEPS: [Step, string][] = [[1, 'Inbox'], [2, 'Scan'], [3, 'Review'], [4, 'Outcome']]
// One item's progress through a run. at: when its result arrived.
type Row = { stage: Stage; model: string | null; at?: string }
// docs: page sizes of each downloaded PDF; null when one is missing, then text holds the recorded page text.
type Loaded = { result: Result; docs: DocPages[] | null; text: TextPage[] | null }
type Act = 'return' | 'approve'
type Call = { act: Act; message: string }

const STAGE: Partial<Record<Stage, [string, number]>> = {
  queued: ['Queued', 0.04], ingest: ['Reading pages', 0.12], triage: ['Reading pages', 0.22],
  extract: ['Checking the spec', 0.36], spec_check: ['Checking the spec', 0.5],
  verify: ['Checking manufacturer documents', 0.64], fix: ['Looking for a replacement', 0.8], report: ['Writing summary', 0.92],
  done: ['Writing summary', 0.98],
}
const KIND: Record<string, string> = { product_data: 'Product data', system_drawing: 'System drawing' }
const TRAY_MIME = 'application/x-speccheck-item'
const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const PRIMARY = 'flare h-10 shrink-0 rounded-lg px-4 font-semibold disabled:cursor-not-allowed disabled:opacity-40'
const NBSP = ' '

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
const now = () => `Today ${new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
const longDate = (d: string) =>
  new Date(/^\d{4}-\d\d-\d\d$/.test(d) ? `${d}T00:00` : d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
const ASKS_SEP = ' · '
const fileName = (c: Case) => c.submittal[0]?.file.split('/').pop() ?? ''
const fixOf = (r?: Result) => r?.findings.find((f) => f.fix)?.fix ?? null
// Spec values come lower-cased ("astm e814"); acronyms back to capitals, list items joined.
const ACRONYM = /\b(astm|ul|ulc|can|dlc|cri|voc|fm|its|ic|cpvc|pvc|abs|pex|frpp|pvdf)\b/gi
const show = (v: Value | undefined) => (v === null || v === undefined || v === '' ? '—'
  : (Array.isArray(v) ? v.join(', ') : String(v)).replace(ACRONYM, (m) => m.toUpperCase()).replace(/\b([a-z])(\d{3,})\b/g, (_, a: string, n: string) => a.toUpperCase() + n))
const hostOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url } }
const discontinued = (r?: Result) => r?.findings.find((f) => f.check === 'status' && f.verdict === 'fail')
// "tavily + nvidia/nemotron-3-super-120b-a12b" -> "Tavily + Super"
const modelTag = (m: string | null) => !m || m === 'code' ? ''
  : m.replace(/\S+\/(\S+)/g, (_, id: string) => (/nano/i.test(id) ? 'Nano' : /super/i.test(id) ? 'Super' : id)).replace(/^tavily/i, 'Tavily')

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [failed, setFailed] = useState(false)
  const [step, setStep] = useState<Step>(1)
  const [reached, setReached] = useState<Step>(1)
  const [inbox, setInbox] = useState<Case[]>([])
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<Record<string, Row>>({}) // the scan
  const [loaded, setLoaded] = useState<Record<string, Loaded>>({})
  const [calls, setCalls] = useState<Record<string, Call>>({}) // the reviewer's decisions, client-side only
  const [current, setCurrent] = useState<string | null>(null)
  const [checks, setChecks] = useState<Record<string, Row>>({}) // "Check approved now"
  const [checked, setChecked] = useState<Record<string, Result>>({})
  const [requested, setRequested] = useState<Record<string, boolean>>({}) // substitutions requested

  useEffect(() => { getProject().then(setProject, () => setFailed(true)) }, [])

  function go(s: Step) {
    setStep(s)
    setReached((r) => (s > r ? s : r))
    window.scrollTo({ top: 0 })
  }

  // Stream a run into a row map; onDone gets each item's result.
  function follow(run: string, set: typeof setRows, onDone: (id: string, r: Result) => void) {
    streamEvents(run, (e) => {
      const id = e.case_id
      if (!id) return
      if (e.stage === 'done') getResult(run, id).then((r) => { set((m) => ({ ...m, [id]: { ...m[id], at: now() } })); onDone(id, r) })
      set((m) => ({ ...m, [id]: { ...m[id], stage: e.stage, model: e.model ?? (e.stage === 'done' ? null : m[id]?.model ?? null) } }))
    }, () => {})
  }

  async function add(id: string) {
    setError(null)
    try {
      const c = await addToInbox(id)
      setInbox((i) => (i.some((x) => x.id === c.id) ? i : [...i, c]))
    } catch (e) { setError((e as Error).message) }
  }

  async function upload(files: File[]) {
    setError(null)
    for (const f of files) {
      try {
        const c = await uploadToInbox(f)
        setInbox((i) => [...i, { ...c, received: now() }])
      } catch (e) { setError(`${f.name}: ${(e as Error).message}`) }
    }
  }

  async function startScan() {
    const fresh = inbox.filter((c) => !rows[c.id])
    setError(null)
    try {
      const run = await scan(fresh.map((c) => c.id))
      setRows((m) => ({ ...m, ...Object.fromEntries(fresh.map((c) => [c.id, { stage: 'queued' as Stage, model: null }])) }))
      follow(run, setRows, async (id, result) => {
        const c = fresh.find((x) => x.id === id)!
        const found = await Promise.all(c.submittal.map((d) => getDocPages(id, d.file)))
        const docs = found.length && found.every(Boolean) ? (found as DocPages[]) : null
        const text = docs ? null : await getCaseText(id)
        setLoaded((m) => ({ ...m, [id]: { result, docs, text } }))
      })
      go(2)
    } catch (e) { setError((e as Error).message) }
  }

  const scanned = inbox.filter((c) => rows[c.id])
  const queue = scanned.filter((c) => loaded[c.id])

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

  const watchList = [...queue.filter((c) => calls[c.id]?.act === 'approve'), ...(project?.watched ?? [])]

  async function checkApproved() {
    setError(null)
    try {
      const run = await scan(watchList.map((c) => c.id))
      setChecked({})
      setChecks((m) => ({ ...m, ...Object.fromEntries(watchList.map((c) => [c.id, { stage: 'queued' as Stage, model: null }])) }))
      follow(run, setChecks, (id, r) => setChecked((m) => ({ ...m, [id]: r })))
    } catch (e) { setError((e as Error).message) }
  }

  const sections = project?.specs.map((s) => s.section) ?? []
  return (
    <div className="min-h-screen font-sans text-sm">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 sm:px-6">
          <span className="flex h-10 shrink-0 items-center gap-2 font-semibold"><span className="h-3 w-3 rounded-sm bg-flare" />SpecCheck</span>
          <span className="hidden truncate text-muted lg:inline">{project?.name}</span>
          <StepBar step={step} reached={reached} onGo={go} />
          <span className="ml-auto hidden shrink-0 font-mono text-xs text-muted md:inline">Specs {sections.join(' · ')}</span>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1120px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
        {failed && <p className="text-muted">Couldn't load the project. Check that the API is running, then reload.</p>}
        {!failed && step === 1 && (
          <InboxStep project={project} inbox={inbox} rows={rows} error={error} onAdd={add} onUpload={upload}
            onRemove={(id) => setInbox((i) => i.filter((c) => c.id !== id))} onScan={startScan} />
        )}
        {step === 2 && <ScanStep items={scanned} rows={rows} loaded={loaded} onReview={startReview} />}
        {step === 3 && (
          <ReviewStep queue={queue} loaded={loaded} calls={calls} current={current} onPick={setCurrent} onDecide={decide} />
        )}
        {step === 4 && (
          <OutcomeStep queue={queue} loaded={loaded} calls={calls} rows={rows} watched={project?.watched ?? []} checks={checks}
            checked={checked} requested={requested} error={error} onCheck={checkApproved}
            onRequest={(id) => setRequested((m) => ({ ...m, [id]: true }))} />
        )}
      </main>
    </div>
  )
}

function StepBar({ step, reached, onGo }: { step: Step; reached: Step; onGo: (s: Step) => void }) {
  return (
    <nav aria-label="Steps" className="order-last -ml-2 flex w-full items-center gap-1 overflow-x-auto sm:order-none sm:w-auto">
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
              <span className={on ? '' : 'hidden sm:inline'}>{label}</span>
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

function InboxStep({ project, inbox, rows, error, onAdd, onUpload, onRemove, onScan }: {
  project: Project | null; inbox: Case[]; rows: Record<string, Row>; error: string | null
  onAdd: (id: string) => void; onUpload: (f: File[]) => void; onRemove: (id: string) => void; onScan: () => void
}) {
  const [over, setOver] = useState(false)
  const fresh = inbox.filter((c) => !rows[c.id])
  const senders = new Set(fresh.map((c) => c.from ?? 'You')).size
  const count = fresh.length ? `${plural(fresh.length, 'submittal')} from ${plural(senders, 'subcontractor')}, not scanned`
    : inbox.length ? `${plural(inbox.length, 'submittal')}, all scanned` : 'No submittals'
  const inside = new Set(inbox.map((c) => c.id))

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
        <button className={PRIMARY} onClick={onScan} disabled={!fresh.length}>{fresh.length ? `Scan ${plural(fresh.length, 'submittal')}` : 'Scan'}</button>
      </Heading>

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

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="font-semibold">Sample submittals</h2>
          <span className="text-muted">Public manufacturer documents, as two subcontractors would send them. Drag into the inbox.</span>
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

function ScanStep({ items, rows, loaded, onReview }: {
  items: Case[]; rows: Record<string, Row>; loaded: Record<string, Loaded>; onReview: () => void
}) {
  const failed = items.filter((c) => rows[c.id]?.stage === 'error').length
  const done = items.filter((c) => loaded[c.id]).length + failed
  const complete = items.length > 0 && done === items.length
  const n = (...ds: Decision[]) => items.filter((c) => ds.includes(loaded[c.id]?.result.decision as Decision)).length
  const count = complete
    ? [`${n('send_back')} to send back`, `${n('approve', 'approve_with_note')} to approve`, ...(failed ? [`${failed} couldn't scan`] : [])].join(' · ')
    : `${done} of ${items.length} done`
  const cols = '112px minmax(0,1fr) minmax(0,1.2fr)'
  return (
    <>
      <Heading title={complete ? 'Scan complete' : 'Scanning'} count={count}>
        {complete && <button className={PRIMARY} onClick={onReview} disabled={!items.some((c) => loaded[c.id])}>Start review</button>}
      </Heading>
      <section className="rounded-xl border border-line">
        <Table cols={cols} head={['Number', 'Submittal', 'Result']}>
          {items.map((c) => {
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
                {r.stage === 'error' ? <span className="text-bad">Couldn't scan this one</span>
                  : l ? (
                    <span className="flex min-w-0 flex-col items-start gap-1">
                      <Pill d={l.result.decision} />
                      <span className="w-full truncate text-xs text-muted" title={l.result.summary}>{l.result.summary}</span>
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
      </section>
    </>
  )
}

// ---------- 3 · Review ----------

function ReviewStep({ queue, loaded, calls, current, onPick, onDecide }: {
  queue: Case[]; loaded: Record<string, Loaded>; calls: Record<string, Call>; current: string | null
  onPick: (id: string) => void; onDecide: (id: string, call: Call) => void
}) {
  const c = queue.find((q) => q.id === current) ?? queue[0]
  if (!c) return <Heading title="Review" count="Nothing to review" />
  const i = queue.indexOf(c)
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
      <Reviewing key={c.id} c={c} at={i + 1} of={queue.length} l={loaded[c.id]} call={calls[c.id]}
        onDecide={(call) => onDecide(c.id, call)} />
    </>
  )
}

const TONE_COLOR: Record<Tone, string> = { red: '#e5534b', amber: '#e5a93b', blue: '#7fa7d9', green: '#2e9e68' }
const TONE_RANK: Record<Tone, number> = { red: 0, amber: 1, blue: 2, green: 3 }
const SEVERITY_RANK: Record<Finding['severity'], number> = { critical: 0, major: 1, minor: 2, info: 3 }
const toneOf = (f: Finding): Tone =>
  f.verdict === 'pass' ? 'green' : f.verdict === 'fail' ? 'red' : f.verdict === 'outdated' ? 'amber' : 'blue'
const WEB = new Set(['currency', 'status'])

// What the sub has to send to clear each problem, in the reviewer's words.
const FLAGGED = (f: Finding) => f.verdict === 'fail' || f.verdict === 'outdated'
function asks(r: Result, section: string): string[] {
  const out = r.findings.filter(FLAGGED).map((f) =>
    f.check === 'currency' ? "The manufacturer's current data sheet"
    : f.check === 'status' ? `A current product that meets ${section}`
    : f.check === 'validity' ? `A listed system that covers ${show(f.compare?.left_value)}`
    : /=/.test(show(f.compare?.left_value)) ? `A listed system with ${show(f.compare?.left_value)}`
    : `${f.title}: ${show(f.compare?.left_value)} required`)
  return [...new Set(out)]
}

function returnNote(c: Case, r: Result, best?: { name: string }): string {
  return [
    `Revise and resubmit ${c.number ?? c.title}.`,
    r.summary,
    `Please send:\n${asks(r, c.section).map((a) => `- ${a.charAt(0).toLowerCase()}${a.slice(1)}`).join('\n')}`,
    ...(best ? [`Suggested replacement: ${best.name}.`] : []),
  ].join('\n\n')
}

// Web checks as rows of the one check table: Required is what the maker publishes today.
const WEB_LABEL: Record<string, string> = { 'status-discontinued': 'Product status' }
function webRows(f: Finding): CheckRow[] {
  if (f.compare?.rows.length) return f.compare.rows.map((r: CompareRow): CheckRow => [f, r.label, `Current: ${r.current ?? '—'}`, r.submitted])
  if (f.id === 'status-discontinued') return [[f, WEB_LABEL[f.id], 'In production', f.compare?.right_value]]
  const now = f.compare?.right_value
  const current = f.verdict === 'pass' && (now === 'unknown' || !now) ? 'Same values as current' : `Current: ${show(now)}`
  return [[f, 'Data sheet version', current, f.compare?.left_value]]
}

function Reviewing({ c, at, of, l, call, onDecide }: {
  c: Case; at: number; of: number; l: Loaded; call?: Call; onDecide: (call: Call) => void
}) {
  const { result, docs, text } = l
  // Worst first: must fix, then out of date, then notes and couldn't-confirm.
  const issues = useMemo(() => result.findings.filter((f) => f.verdict !== 'pass' && f.verdict !== 'not_applicable')
    .sort((a, b) => TONE_RANK[toneOf(a)] - TONE_RANK[toneOf(b)] || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]), [result])
  const marks: Placed[] = useMemo(() => result.findings.flatMap((f) =>
    f.highlights.map((h) => ({ ...h, finding: f, tone: h.kind === 'checked' ? 'green' as Tone : toneOf(f) }))), [result])
  const first = issues.find((f) => firstMark(f)) ?? issues[0]
  const [textPage, setTextPage] = useState(() => (first && firstMark(first)?.page) || 1)
  const fix = fixOf(result)
  const best = fix?.candidates.find((x) => x.passes)
  const rec: Act = result.decision === 'send_back' ? 'return' : 'approve'
  const who = c.from ?? 'sender'
  const draft = (a: Act) => a === 'return'
    ? returnNote(c, result, best)
    : `No exceptions taken. Forwarding ${c.number ?? c.title} for approval.${result.decision === 'approve_with_note' && result.note_to_subcontractor ? `\n\n${result.note_to_subcontractor}` : ''}`
  const [message, setMessage] = useState(call?.act === rec ? call.message : draft(rec))
  const spec = result.findings.filter((f) => f.verdict !== 'not_applicable' && !WEB.has(f.check))
  const web = result.findings.filter((f) => WEB.has(f.check))
  const source = web.flatMap((f) => f.evidence)[0]

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
          <span className="text-xs text-muted"><span className="font-mono">{c.number ?? 'Upload'}</span> · {at} of {of} · from {c.from ?? 'you'}</span>
          <h2 className="text-lg font-semibold leading-tight">{c.title}</h2>
          <span className="flex items-center gap-2"><Pill d={result.decision} />{call && <span className="text-xs text-muted">Decided: {call.act === 'return' ? 'sent back' : 'approved'}</span>}</span>
          <p className="text-base text-soft">{result.summary}</p>
        </div>

        <div className="flex flex-col gap-2">
          <Checks head={['Check', 'Required', 'Submitted']}
            rows={[...spec.map((f): CheckRow => [f, f.title, f.compare?.left_value, f.compare?.right_value]), ...web.flatMap(webRows)]
              .sort((x, y) => TONE_RANK[toneOf(x[0])] - TONE_RANK[toneOf(y[0])])} />
          <span className="text-xs leading-5 text-muted">
            Sources: spec {c.section}{result.document_revision ? ` · submitted sheet ${result.document_revision}` : ''}
            {source && <> · <a href={source.url} target="_blank" rel="noreferrer" className="underline decoration-edge underline-offset-2 hover:text-ink">{source.title || hostOf(source.url)} ↗</a></>}
          </span>
        </div>

        {best && (
          <div className="flex flex-col gap-1 rounded-xl border border-good/40 p-4">
            <span className={CAPS}>Suggested replacement</span>
            <a href={best.source_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">{best.name}</a>
            <span className="flex items-center gap-1 text-xs text-good"><Icon kind="check" />Passes all checks</span>
          </div>
        )}

        <div className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-4">
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <label htmlFor="message" className={CAPS}>{rec === 'return' ? `Return to ${who}` : 'Forward to architect'}</label>
            {rec === 'return' && c.email && <span className="font-mono text-xs text-muted">{c.email}</span>}
          </span>
          <textarea id="message" rows={9} value={message} onChange={(e) => setMessage(e.target.value)}
            className="resize-y rounded-lg border border-line bg-well p-3 leading-relaxed text-ink" />
          <div className="flex flex-wrap gap-2">
            {rec === 'return' ? (
              <>
                <button className={PRIMARY} onClick={() => onDecide({ act: 'return', message })}>Send back to {who}</button>
                <button className="btn" onClick={() => onDecide({ act: 'approve', message: draft('approve') })}>Approve</button>
              </>
            ) : (
              <>
                <button className={PRIMARY} onClick={() => onDecide({ act: 'approve', message })}>Approve and forward</button>
                <button className="btn" onClick={() => onDecide({ act: 'return', message: draft('return') })}>Send back</button>
              </>
            )}
          </div>
        </div>
      </aside>
    </div>
  )
}

type CheckRow = [Finding, string, Value | undefined, Value | undefined]

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
            <span className="min-w-0 break-words">{label}</span>
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
                  <span className="min-w-0">{lines[k]}</span>
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

// "None passed. STI W-L-1079 checked: T rating 0 hr." from the fix step, or the passing candidate.
function replacement(fix: Fix | null): [string, boolean] {
  if (!fix) return ['—', false]
  if (fix.suggest) return [fix.suggest, true]
  const c = fix.candidates[0]
  if (!c) return ['None found', false]
  const bad = c.checks.find((k) => k.ok === false) ?? c.checks.find((k) => k.ok === null)
  const name = c.name.split(',')[0].replace(/^(\S+) SpecSeal System No\. /, '$1 ')  // "STI SpecSeal System No. W-L-1079, metallic…" -> "STI W-L-1079"
  const why = bad ? (bad.note || (bad.ok === null ? `${bad.label} not stated` : bad.label)) : ''
  return [`None passed · ${name}${why ? ` fails on ${why}` : ''}`, false]
}

function OutcomeStep({ queue, loaded, calls, rows, watched, checks, checked, requested, error, onCheck, onRequest }: {
  queue: Case[]; loaded: Record<string, Loaded>; calls: Record<string, Call>; rows: Record<string, Row>; watched: Case[]
  checks: Record<string, Row>; checked: Record<string, Result>; requested: Record<string, boolean>; error: string | null
  onCheck: () => void; onRequest: (id: string) => void
}) {
  const returned = queue.filter((c) => calls[c.id]?.act === 'return')
  const approved = [...queue.filter((c) => calls[c.id]?.act === 'approve'), ...watched]
  const checking = approved.some((c) => checks[c.id] && !checked[c.id])
  const ran = approved.some((c) => checked[c.id])
  const alerts = approved.filter((c) => discontinued(checked[c.id]))
  const back = 'minmax(0,0.8fr) minmax(0,1.2fr) minmax(0,1.4fr) minmax(0,1.4fr)'
  const fwd = '112px minmax(0,1.4fr) 112px 140px 128px'
  return (
    <>
      <Heading title="Outcome" count={`${returned.length} returned · ${approved.length - watched.length} approved`}>
        <button className={ran ? 'btn' : PRIMARY} onClick={onCheck} disabled={checking || !approved.length}>
          {checking ? 'Checking…' : 'Check approved now'}
        </button>
      </Heading>
      {error && <p className="text-bad" role="alert">{error}</p>}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Returned to subcontractors</h2>
        <div className="rounded-xl border border-line">
          {returned.length ? (
            <Table cols={back} head={['Number', 'Sent to', 'Requested', 'Suggested replacement']}>
              {returned.map((c) => {
                const r = loaded[c.id].result
                const asked = asks(r, c.section)
                const [text, passes] = replacement(fixOf(r))
                return (
                  <TableRow key={c.id} cols={back}>
                    <span className="font-mono text-xs text-muted">{c.number ?? 'Upload'}</span>
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate">{c.from ?? 'Sender'}</span>
                      <span className="truncate text-xs text-muted">{c.product ?? c.title}</span>
                    </span>
                    <span className="text-soft">{asked.length ? asked.join(ASKS_SEP) : '—'}</span>
                    <span className={passes ? 'flex items-center gap-1 font-medium text-good' : 'text-xs text-muted'}>
                      {passes && <Icon kind="check" />}{text}
                    </span>
                  </TableRow>
                )
              })}
            </Table>
          ) : <p className="px-4 py-6 text-muted">None returned.</p>}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-semibold">Approved and forwarded to the architect</h2>
          <span className="text-xs text-muted">Re-checked against manufacturer documents nightly</span>
        </div>
        <div className="rounded-xl border border-line">
          <Table cols={fwd} head={['Number', 'Product', 'Approved', 'Last checked', 'Status']}>
            {approved.map((c) => {
              const w = checks[c.id]
              const res = checked[c.id]
              const scannedAt = c.watch ? undefined : rows[c.id]?.at
              const status = w && !res ? <span className="flex items-center gap-2 text-soft"><span className="blink h-2 w-2 rounded-full bg-flare" />Checking</span>
                : res ? (discontinued(res) ? <span className="font-medium text-bad">Discontinued</span> : <span className="text-good">No change</span>)
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
  const best = fixOf(result)?.candidates.find((x) => x.passes)
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
          <span className="text-base text-soft">“{f.quote}”</span>
          {src && <a href={src.url} target="_blank" rel="noreferrer" className="truncate text-xs text-muted underline decoration-edge underline-offset-2 hover:text-ink">{src.title || hostOf(src.url)} ↗</a>}
        </blockquote>
      )}
      {best && (
        <div className="flex flex-col gap-1 rounded-lg border border-good/40 p-3">
          <span className={CAPS}>Suggested replacement</span>
          <a href={best.source_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">{best.name}</a>
          <span className="flex items-center gap-1 text-xs text-good"><Icon kind="check" />Passes all checks</span>
        </div>
      )}
      <button className={`${PRIMARY} self-start`} onClick={onRequest} disabled={sent}>
        {sent ? `Sent to ${who}` : `Request substitution from ${who}`}
      </button>
    </section>
  )
}
