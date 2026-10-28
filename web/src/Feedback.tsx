// Customer-feedback building blocks. Presentational only: every value comes from code-decided fields
// (Result.findings, Fix.alternates, /api/runs/{id}/package). Used by Review, Scan-complete and the memo.
import type { CSSProperties, ReactNode } from 'react'
import { namedLabel, type Alternate, type Case, type Decision, type Finding, type Fix, type FixCandidate, type NamedReplacement, type PackageRow, type Project, type Result } from './api'

const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const SPEC_CHECKS = new Set(['spec', 'validity', 'completeness'])

export const KIND: Record<string, string> = {
  product_data: 'Product data', system_drawing: 'System drawing', listing: 'Listing', test_report: 'Test report',
  installation: 'Installation', warranty: 'Warranty',
}

// The spec rules that apply to this item.
const requirementFindings = (result: Result) =>
  result.findings.filter((f) => SPEC_CHECKS.has(f.check) && f.requirement_id && f.verdict !== 'not_applicable')

// One state per finding, drawn as an 18 px square. Not confirmed is an outline, so it differs in shape as well as color.
export type RuleState = 'meets' | 'fails' | 'option' | 'unconfirmed'
export const ruleState = (f: Finding): RuleState => f.verdict === 'pass' ? 'meets'
  : f.verdict === 'fail' || f.verdict === 'outdated' ? 'fails' : f.configure?.length || f.verdict === 'note' ? 'option' : 'unconfirmed'
const GLYPH: Record<RuleState, [string, CSSProperties]> = {
  meets: ['✓', { background: '#2e9e68', color: '#06150d' }], fails: ['✕', { background: '#e5534b', color: '#1d0606' }],
  option: ['!', { background: '#e5a93b', color: '#1e1403' }], unconfirmed: ['?', { border: '1.5px dashed #a9c8f0', color: '#a9c8f0' }],
}
export function Glyph({ s, size = 18 }: { s: RuleState; size?: number }) {
  return <span aria-hidden className="inline-flex shrink-0 items-center justify-center rounded-[3px] text-xs font-bold leading-none"
    style={{ width: size, height: size, ...GLYPH[s][1] }}>{GLYPH[s][0]}</span>
}

export function requirementCounts(result: Result) {
  const rf = requirementFindings(result)
  return {
    meets: rf.filter((f) => f.verdict === 'pass').length,
    doesntMeet: rf.filter((f) => f.verdict === 'fail').length,
    couldntConfirm: rf.filter((f) => f.verdict === 'unverified' || f.verdict === 'pending').length,
  }
}

// Three numbers under the decision: the first thing a reviewer reads.
export function SummaryCounters({ result }: { result: Result }) {
  const c = requirementCounts(result)
  const cell = (n: number, label: string, color: string) => (
    <div className="flex flex-1 flex-col gap-0.5 rounded-lg border border-line bg-well px-3 py-2">
      <span className="text-2xl font-semibold tabular-nums" style={{ color: n ? color : 'var(--color-muted)' }}>{n}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  )
  return (
    <div className="flex gap-2">
      {cell(c.meets, 'Meets spec', 'var(--color-good)')}
      {cell(c.doesntMeet, "Doesn't meet", 'var(--color-bad)')}
      {cell(c.couldntConfirm, "Couldn't confirm", 'var(--color-fyi)')}
    </div>
  )
}

// "Specify option" lines: the exact configuration to request, with its quote.
export function ConfigureLines({ findings }: { findings: Finding[] }) {
  const lines = findings.filter((f) => f.configure?.length)
  if (!lines.length) return null
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-warn/40 p-4">
      <span className={CAPS}>Configuration to request</span>
      {lines.map((f) => f.configure!.map((o) => (
        <div key={`${f.id}-${o.claim_id}`} className="flex flex-col gap-1">
          <span><span className="font-semibold">Specify {o.option}</span> <span className="text-muted">→ {f.title.replace('Specify option: ', '').replace(/^\w(?![A-Z])/, (ch) => ch.toLowerCase())} {o.value}
            {f.compare?.left_value != null && ` (spec ${Array.isArray(f.compare.left_value) ? f.compare.left_value.join(', ') : f.compare.left_value})`}
            {f.spec_ref ? ` · ${f.spec_ref}` : ''}</span></span>
          {o.quote && <blockquote className="border-l-2 border-edge pl-3 text-sm text-muted">“{o.quote}”{o.page ? ` · page ${o.page}` : ''}</blockquote>}
        </div>
      )))}
    </div>
  )
}

const RANK_LABEL: Record<Alternate['rank'], string> = { meets_spec: 'Meets spec', possible: 'Possible alternate', failed: "Doesn't meet spec" }
const RANK_COLOR: Record<Alternate['rank'], string> = { meets_spec: 'var(--color-good)', possible: 'var(--color-warn)', failed: 'var(--color-bad)' }
const MARK: Record<string, [string, string]> = {
  better: ['▲ better', 'var(--color-good)'], meets: ['= meets', 'var(--color-soft)'],
  worse: ['▼ weaker', 'var(--color-warn)'], unknown: ['?', 'var(--color-muted)'],
}

const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url } }
const unmark = (q: string) => q.replace(/\*\*|__/g, '')

// c: the checked candidate behind the alternate, for its quotes and a configuration SpecCheck proposed.
function AlternateRow({ a, c, named }: { a: Alternate; c?: FixCandidate; named?: NamedReplacement | null }) {
  const proposal = c?.selection?.origin === 'agent_proposal' ? c.selection : null
  return (
    <li className="flex flex-col gap-1.5 border-b border-line py-3 last:border-b-0">
      <span className="flex flex-wrap items-center gap-2">
        <span className="rounded-full px-2 text-xs font-semibold" style={{ color: RANK_COLOR[a.rank], boxShadow: `inset 0 0 0 1px ${RANK_COLOR[a.rank]}` }}>{RANK_LABEL[a.rank]}</span>
        <a href={a.source_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">{a.name} ↗</a>
        {a.origin === 'current_document' && <span className="text-xs text-muted">current sheet of the same product</span>}
        {a.origin === 'named_replacement' && <span className="text-xs text-muted">{namedLabel(named)}</span>}
      </span>
      {a.origin === 'named_replacement' && named && <span className="text-xs text-muted">
        Notice: “{named.quote}” · <a href={named.url} target="_blank" rel="noreferrer" className="underline">{host(named.url)} ↗</a></span>}
      {a.better.length > 0 && <span className="flex flex-wrap gap-x-4 gap-y-1 text-sm">{a.better.map((m) => (
        <span key={m.requirement_id}><span className="text-muted">{m.label} </span><span style={{ color: MARK[m.mark][1] }}>{m.alternate} {MARK[m.mark][0]}</span>{m.submitted && <span className="text-faint"> (submitted {m.submitted})</span>}</span>
      ))}</span>}
      {proposal && <span className="text-sm text-soft">Proposed by SpecCheck: {proposal.model}. Confirm configuration before ordering.</span>}
      {a.rank === 'possible' && <span className="text-sm text-soft">Confirm: {a.confirm.join(', ')}</span>}
      {c && <details className="text-sm">
        <summary className="cursor-pointer text-muted">Evidence</summary>
        <ul className="mt-2 flex flex-col gap-3">
          {proposal && <li><span className="font-medium">Proposed configuration · page {proposal.page}</span>
            <blockquote className="mt-1 border-l-2 border-edge pl-3 text-muted">“{unmark(proposal.quote)}”</blockquote></li>}
          {c.checks.map((k, n) => <li key={n}>
            <span className="font-medium">{k.label}</span>{k.ok === false ? ' · fails' : k.ok === null ? ' · not confirmed' : ''}
            {k.evidence?.map((e, i) => <blockquote key={i} className="mt-1 border-l-2 border-edge pl-3 text-muted">
              {e.excerpt && <p>“{unmark(e.excerpt)}”</p>}
              <a href={e.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">{host(e.url)} ↗</a>
            </blockquote>)}
          </li>)}
        </ul>
      </details>}
    </li>
  )
}

// "What to send instead": ranked in code; failed candidates stay behind a disclosure.
export function AlternatesCard({ fix }: { fix: Fix }) {
  const alts = fix.alternates ?? []
  const shown = alts.filter((a) => a.rank !== 'failed').slice(0, 3)
  const failed = alts.filter((a) => a.rank === 'failed')
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-line bg-panel p-4">
      <span className={CAPS}>What to send instead</span>
      {shown.length ? <ul className="flex flex-col">{shown.map((a) => <AlternateRow key={a.source_url} a={a}
        c={fix.candidates.find((c) => c.source_url === a.source_url)} named={fix.named} />)}</ul>
        : <p className="text-soft">No alternate found that meets the spec. Ask the sub for a product that does.</p>}
      {failed.length > 0 && <details className="text-sm text-muted">
        <summary className="cursor-pointer">{failed.length} other candidate{failed.length > 1 ? 's' : ''} didn't meet spec</summary>
        <ul className="mt-2 flex flex-col gap-1">{failed.map((a) => <li key={a.source_url}>{a.name}: {a.failed.join(', ')}</li>)}</ul>
      </details>}
      {shown.length > 0 && <span className="text-xs text-muted">Compared point by point against the spec, as a CSI 13.1A substitution request asks.</span>}
      {fix.query && <span className="text-xs text-faint">Searched: {fix.query}</span>}
    </div>
  )
}

// ---------- the package view ----------

const CELL: Record<string, [string, string, string]> = {
  meets: ['✓', 'Meets', 'var(--color-good)'], fails: ['✕', 'Fails', 'var(--color-bad)'],
  configure: ['!', 'Option', 'var(--color-warn)'], unconfirmed: ['?', 'Unconfirmed', 'var(--color-fyi)'],
  not_checked: ['–', 'Not checked', 'var(--color-muted)'],
  current: ['✓', 'Current', 'var(--color-good)'], outdated: ['✕', 'Outdated', 'var(--color-bad)'],
  newer: ['!', 'Newer exists', 'var(--color-warn)'], unknown: ['?', 'Unknown', 'var(--color-muted)'],
  active: ['✓', 'Made', 'var(--color-good)'], discontinued: ['✕', 'Discontinued', 'var(--color-bad)'],
}

// label: the column name, shown only on a phone where the cells stack.
function Cell({ v, label }: { v: string; label: string }) {
  const [icon, word, color] = CELL[v] ?? ['?', v, 'var(--color-muted)']
  return <span data-cell={v} className="flex items-center gap-1.5 text-sm" style={{ color }}>
    <span className="w-20 text-xs text-muted sm:hidden">{label}</span><span className="font-semibold">{icon}</span>{word}</span>
}

export function PackageMatrix({ rows, onOpen, decision }: {
  rows: PackageRow[]; onOpen?: (caseId: string) => void; decision?: (row: PackageRow) => ReactNode
}) {
  const cols = 'minmax(0,2fr) 110px 110px 120px minmax(0,2.2fr) 150px'
  return (
      <div className="rounded-xl border border-line">
        <div className={`hidden h-10 items-center gap-4 border-b border-line px-4 sm:grid ${CAPS}`} style={{ gridTemplateColumns: cols }}>
          <span>Submittal</span><span>Spec</span><span>Sheet</span><span>Still made</span><span>What to send</span><span>Decision</span>
        </div>
        {rows.map((r) => (
          <div key={r.case_id} className="flex flex-col gap-2 border-b border-line px-4 py-3 last:border-b-0 sm:grid sm:items-center sm:gap-4"
            style={{ gridTemplateColumns: cols }}>
            <button className="text-left" onClick={() => onOpen?.(r.case_id)} aria-label={`Review ${r.number ?? r.title}`}>
              <span className="block font-medium hover:underline">{r.title}</span>
              <span className="block text-xs text-muted"><span className="font-mono">{r.number ?? 'Upload'}</span>{r.sender ? ` · ${r.sender}` : ''}</span>
            </button>
            <Cell v={r.spec} label="Spec" /><Cell v={r.current_sheet} label="Sheet" /><Cell v={r.still_made} label="Still made" />
            <span className="text-sm text-soft">{r.what_to_send[0] ?? '—'}{r.what_to_send.length > 1 && <span className="text-faint"> +{r.what_to_send.length - 1}</span>}</span>
            <span className="flex flex-col items-start gap-1">{decision ? decision(r) : <span className="text-sm font-semibold">{r.stamp}</span>}
              {r.manual_review_suggested && <span className="text-xs text-fyi">Worth a manual look</span>}</span>
          </div>
        ))}
      </div>
  )
}

// ---------- the package, grouped by spec section (Scan complete) ----------

const ORDER: Decision[] = ['send_back', 'approve_with_note', 'approve', 'not_applicable']
const STATE_ORDER: RuleState[] = ['fails', 'meets', 'option', 'unconfirmed']
const STATE_WORDS: Record<RuleState, [string, string]> = {
  fails: ["doesn't meet", "don't meet"], meets: ['meets', 'meet'], option: ['with an option', 'with an option'], unconfirmed: ['not confirmed', 'not confirmed'],
}

// "1 doesn't meet · 3 not confirmed": the squares in plain words, zeros left out.
export function ruleLine(states: RuleState[]) {
  return STATE_ORDER.map((s) => [s, states.filter((x) => x === s).length] as const).filter(([, n]) => n)
    .map(([s, n]) => `${n} ${STATE_WORDS[s][n === 1 ? 0 : 1]}`).join(' · ')
}

// The one status line under the documents, only when there is news. Unknown and not checked say nothing.
const news = (r: PackageRow): [RuleState, string] | null => r.still_made === 'discontinued' ? ['fails', 'Discontinued']
  : r.current_sheet === 'outdated' ? ['fails', 'Sheet out of date'] : r.current_sheet === 'newer' ? ['option', 'Newer sheet online'] : null

export function PackageBands({ rows, cases, results, specs, onOpen, decision }: {
  rows: PackageRow[]; cases: Record<string, Case>; results: Record<string, Result | undefined>; specs: Project['specs']
  onOpen: (caseId: string) => void; decision: (row: PackageRow) => ReactNode
}) {
  const known = new Set(specs.map((s) => s.section))
  const sectionOf = (r: PackageRow) => { const s = cases[r.case_id]?.section; return s && known.has(s) ? s : '' }
  const bands = [...specs.map((s) => s.section), ''].map((section) => ({
    section, title: specs.find((s) => s.section === section)?.title,
    rows: rows.filter((r) => sectionOf(r) === section)
      .sort((a, b) => ORDER.indexOf(a.decision) - ORDER.indexOf(b.decision) || (a.number ?? '').localeCompare(b.number ?? '', undefined, { numeric: true })),
  })).filter((b) => b.rows.length)
  const cols = 'minmax(0,1.5fr) minmax(0,1.2fr) minmax(0,1.3fr) minmax(0,1.5fr) 170px'
  return (
    <div className="flex flex-col gap-4">
      {bands.map((b) => {
        const senders = [...new Set(b.rows.map((r) => cases[r.case_id]?.from).filter(Boolean))].join(', ')
        const stamps = ORDER.map((d) => [b.rows.filter((r) => r.decision === d), d] as const).filter(([rs]) => rs.length)
          .map(([rs]) => `${rs.length} ${rs[0].stamp.split(':')[0].toLowerCase()}`)
        return (
          <section key={b.section} className="overflow-hidden rounded-xl border border-line bg-well" aria-label={b.section ? `${b.section} ${b.title}` : 'Your uploads'}>
            <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3">
              {b.section ? <span className="font-semibold"><span className="mr-3 font-mono">{b.section}</span>{b.title}</span>
                : <span className="font-semibold">Your uploads</span>}
              <span className="text-xs text-soft">{[senders, `${b.rows.length} submittal${b.rows.length === 1 ? '' : 's'}`, ...stamps].filter(Boolean).join(' · ')}</span>
            </header>
            <div className="overflow-x-auto border-t border-line bg-panel">
              <div className="min-w-[780px]">
                <div className={`grid h-10 items-center gap-4 border-b border-line px-4 ${CAPS}`} style={{ gridTemplateColumns: cols }}>
                  <span>Submittal</span><span>Documents</span><span>Spec rules</span><span>What to send</span><span>Decision</span>
                </div>
                {b.rows.map((r) => {
                  const c = cases[r.case_id]
                  const result = results[r.case_id]
                  const states = result ? requirementFindings(result).map(ruleState)
                    .sort((x, y) => STATE_ORDER.indexOf(x) - STATE_ORDER.indexOf(y)) : []
                  const line = ruleLine(states)
                  const status = news(r)
                  return (
                    <div key={r.case_id} onClick={() => onOpen(r.case_id)}
                      className="grid cursor-pointer items-start gap-4 border-b border-line px-4 py-3 last:border-b-0 hover:bg-raised" style={{ gridTemplateColumns: cols }}>
                      <button className="min-w-0 text-left" aria-label={`Review ${r.number ?? r.title}`}>
                        <span className="block font-medium hover:underline">{r.title}</span>
                        <span className="block text-xs text-muted"><span className="font-mono">{r.number ?? 'Upload'}</span>{c?.product ? ` · ${c.product}` : ''}</span>
                      </button>
                      <span className="flex min-w-0 flex-col gap-1.5">
                        <span className="flex flex-wrap gap-1">{(c?.submittal ?? []).map((d) =>
                          <span key={d.file} title={d.file.split('/').pop()} className="rounded border border-edge px-1.5 text-xs leading-5 text-soft">{KIND[d.role ?? ''] ?? 'Document'}</span>)}</span>
                        {status && <span className="flex items-center gap-1.5 text-xs text-soft" data-status={status[1]}><Glyph s={status[0]} size={14} />{status[1]}</span>}
                      </span>
                      <span className="flex min-w-0 flex-col gap-1.5">
                        {states.length ? <>
                          <span className="flex flex-wrap gap-1" role="img" aria-label={line}>{states.map((s, i) => <Glyph key={i} s={s} />)}</span>
                          <span className="text-xs text-soft">{line}</span>
                        </> : <span className="text-xs text-muted">No rules checked</span>}
                      </span>
                      <span className="text-sm text-soft">{r.what_to_send[0] ?? '—'}{r.what_to_send.length > 1 && <span className="text-muted"> +{r.what_to_send.length - 1} more</span>}</span>
                      <span className="flex items-start">{decision(r)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </section>
        )
      })}
    </div>
  )
}
