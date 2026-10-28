// Customer-feedback building blocks (scaffold). Presentational only: every value comes from code-decided fields
// (Result.findings, Fix.alternates, /api/runs/{id}/package). Not wired yet — see the handoff prompt for where each
// one goes. They use the app's tokens only (index.css), so they drop into Review, Scan-complete and the memo as-is.
import type { ReactNode } from 'react'
import type { Alternate, Finding, Fix, PackageRow, PackageSummary, Result } from './api'

const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const SPEC_CHECKS = new Set(['spec', 'validity', 'completeness'])

export function requirementCounts(result: Result) {
  const rf = result.findings.filter((f) => SPEC_CHECKS.has(f.check) && f.requirement_id && f.verdict !== 'not_applicable')
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
          <span><span className="font-semibold">Specify {o.option}</span> <span className="text-muted">· {f.title.replace('Specify option: ', '')} {o.value}{f.spec_ref ? ` · ${f.spec_ref}` : ''}</span></span>
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

function AlternateRow({ a }: { a: Alternate }) {
  return (
    <li className="flex flex-col gap-1.5 border-b border-line py-3 last:border-b-0">
      <span className="flex flex-wrap items-center gap-2">
        <span className="rounded-full px-2 text-xs font-semibold" style={{ color: RANK_COLOR[a.rank], boxShadow: `inset 0 0 0 1px ${RANK_COLOR[a.rank]}` }}>{RANK_LABEL[a.rank]}</span>
        <a href={a.source_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">{a.name} ↗</a>
        {a.origin === 'current_document' && <span className="text-xs text-muted">current sheet of the same product</span>}
      </span>
      {a.better.length > 0 && <span className="flex flex-wrap gap-x-4 gap-y-1 text-sm">{a.better.map((m) => (
        <span key={m.requirement_id}><span className="text-muted">{m.label} </span><span style={{ color: MARK[m.mark][1] }}>{m.alternate} {MARK[m.mark][0]}</span>{m.submitted && <span className="text-faint"> (submitted {m.submitted})</span>}</span>
      ))}</span>}
      {a.rank === 'possible' && <span className="text-sm text-soft">Confirm: {a.confirm.join(', ')}</span>}
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
      {shown.length ? <ul className="flex flex-col">{shown.map((a) => <AlternateRow key={a.source_url} a={a} />)}</ul>
        : <p className="text-soft">No alternate found that meets the spec. Ask the sub for a product that does.</p>}
      {failed.length > 0 && <details className="text-sm text-muted">
        <summary className="cursor-pointer">{failed.length} other candidate{failed.length > 1 ? 's' : ''} didn't meet spec</summary>
        <ul className="mt-2 flex flex-col gap-1">{failed.map((a) => <li key={a.source_url}>{a.name}: {a.failed.join(', ')}</li>)}</ul>
      </details>}
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

function Cell({ v }: { v: string }) {
  const [icon, word, color] = CELL[v] ?? ['?', v, 'var(--color-muted)']
  return <span className="flex items-center gap-1.5 text-sm" style={{ color }}><span className="font-semibold">{icon}</span>{word}</span>
}

export function PackageMatrix({ summary, onOpen, decision }: {
  summary: PackageSummary; onOpen?: (caseId: string) => void; decision?: (row: PackageRow) => ReactNode
}) {
  const cols = 'minmax(0,2fr) 110px 110px 120px minmax(0,2.2fr) 150px'
  return (
    <div className="flex flex-col gap-3">
      <p className="text-soft">
        {summary.rows.length} submittals · {summary.ready} ready to forward · {summary.need_changes} need changes
        {summary.not_checked ? ` · ${summary.not_checked} not checked` : ''}
        {summary.manual_review_suggested ? ` · ${summary.manual_review_suggested} worth a manual look` : ''}
      </p>
      <div className="rounded-xl border border-line">
        <div className={`hidden h-10 items-center gap-4 border-b border-line px-4 sm:grid ${CAPS}`} style={{ gridTemplateColumns: cols }}>
          <span>Submittal</span><span>Spec</span><span>Sheet</span><span>Still made</span><span>What to send</span><span>Decision</span>
        </div>
        {summary.rows.map((r) => (
          <div key={r.case_id} className="flex flex-col gap-2 border-b border-line px-4 py-3 last:border-b-0 sm:grid sm:items-center sm:gap-4"
            style={{ gridTemplateColumns: cols }}>
            <button className="text-left" onClick={() => onOpen?.(r.case_id)}>
              <span className="block font-medium hover:underline">{r.title}</span>
              <span className="block text-xs text-muted"><span className="font-mono">{r.number ?? 'Upload'}</span>{r.sender ? ` · ${r.sender}` : ''}</span>
            </button>
            <Cell v={r.spec} /><Cell v={r.current_sheet} /><Cell v={r.still_made} />
            <span className="text-sm text-soft">{r.what_to_send[0] ?? '—'}{r.what_to_send.length > 1 && <span className="text-faint"> +{r.what_to_send.length - 1}</span>}</span>
            <span className="flex flex-col gap-0.5">{decision ? decision(r) : <span className="text-sm font-semibold">{r.stamp}</span>}
              {r.manual_review_suggested && <span className="text-xs text-fyi">Worth a manual look</span>}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
