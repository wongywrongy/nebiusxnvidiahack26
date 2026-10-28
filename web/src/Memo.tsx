// The package review memo: one printable page per run (/memo/<runId>), letter size. Every line comes from the
// package view and the results the run already stored; nothing is written by a model here.
import { useEffect, useState } from 'react'
import { DECISION_LABEL, getPackage, getProject, modelName, namedLabel, type Alternate, type Finding, type Fix, type PackageRow,
  type PackageSummary, type Result } from './api'
import { ConfigureLines, PackageMatrix } from './Feedback'

const CAPS = 'font-mono text-xs font-medium uppercase tracking-[0.08em] text-faint'
const ACTION = (f: Finding) => ['fail', 'outdated', 'note'].includes(f.verdict)
  || (['unverified', 'pending'].includes(f.verdict) && ['critical', 'major'].includes(f.severity))
const RANK: Record<Alternate['rank'], string> = { meets_spec: 'Meets spec', possible: 'Possible alternate', failed: "Doesn't meet spec" }
const show = (v: unknown) => v === null || v === undefined || v === '' ? '—' : Array.isArray(v) ? v.join(', ') : String(v)
const day = (iso?: string) => iso ? iso.slice(0, 10) : ''
const runDate = (id: string) => `${id.slice(0, 4)}-${id.slice(4, 6)}-${id.slice(6, 8)}`

function modeLabel(results: Result[]): string {
  const labels = new Set<string>()
  for (const r of results) {
    labels.add(r.replayed_from ? `replay of the ${r.mode ?? 'live'} run from ${runDate(r.replayed_from)}` : r.mode === 'mock' ? 'mock (fixture answers)' : 'live')
    if (r.checklist_id) labels.add('unreviewed draft checklist')
  }
  return [...labels].join(' · ')
}

function checkedBy(r: Result): string {
  const models = [...new Set(r.usage.map((u) => modelName(u.model)))]
  return [models.join(' and ') + (r.mode === 'live' ? ' on Nebius Token Factory' : r.mode === 'mock' ? ' (mock fixtures)' : ''),
    r.web_credits > 0 ? 'Tavily' : '', 'every pass/fail computed in code from quoted values'].filter(Boolean).join(' · ')
}

// One requirement row: the quote that decided it, from the submittal page or the web source.
function FindingRow({ f }: { f: Finding }) {
  const mark = f.highlights.find((h) => h.quote)
  const web = f.evidence[0]
  const quote = f.quote ?? mark?.quote ?? web?.excerpt
  return (
    <tr className="border-t border-line align-top">
      <td className="py-1.5 pr-3">{f.title}{f.spec_ref && <span className="block text-xs text-muted">{f.spec_ref}</span>}</td>
      <td className="py-1.5 pr-3">{show(f.compare?.left_value)}</td>
      <td className="py-1.5 pr-3">{show(f.compare?.right_value)}</td>
      <td className="py-1.5 text-xs text-muted">
        {quote && <>“{quote.replace(/\*\*|__/g, '').slice(0, 240)}”</>}{mark?.page ? ` · page ${mark.page}` : ''}
        {['currency', 'status'].includes(f.check) && web && <> · <a href={web.url} className="underline">{web.title || web.url}</a>
          {web.retrieved_at ? ` · retrieved ${day(web.retrieved_at)}` : ''}</>}
      </td>
    </tr>
  )
}

// CSI 13.1A-style point-by-point comparison: specified, submitted, proposed, result, per check.
function PointByPoint({ a, fix, result }: { a: Alternate; fix: Fix; result: Result }) {
  const c = fix.candidates.find((x) => x.source_url === a.source_url)
  const better = Object.fromEntries(a.better.map((m) => [m.requirement_id, m]))
  return (
    <div className="flex flex-col gap-1">
      <span className="font-semibold">{RANK[a.rank]}: <a href={a.source_url} className="underline">{a.name}</a>
        {a.origin === 'current_document' ? ' (current sheet of the same product)' : a.origin === 'named_replacement' ? ` (${namedLabel(fix.named)}: “${fix.named?.quote ?? ''}”)` : ''}</span>
      {c?.selection?.origin === 'agent_proposal' && <span className="text-sm">Proposed by SpecCheck: {c.selection.model}. Confirm configuration before ordering.</span>}
      {c && <table className="w-full text-sm">
        <thead><tr className={CAPS}><th className="py-1 text-left">Item</th><th className="text-left">Specified</th>
          <th className="text-left">Submitted</th><th className="text-left">Proposed</th><th className="text-left">Result</th></tr></thead>
        <tbody>{c.checks.map((k, i) => {
          const f = result.findings.find((x) => k.requirement_id && x.requirement_id === k.requirement_id)
          const m = k.requirement_id ? better[k.requirement_id] : undefined
          const quote = k.evidence?.[0]?.excerpt
          return (
            <tr key={i} className="border-t border-line align-top">
              <td className="py-1 pr-3">{k.label}</td>
              <td className="pr-3">{show(f?.compare?.left_value)}</td>
              <td className="pr-3">{show(m?.submitted ?? f?.compare?.right_value)}</td>
              <td className="pr-3">{show(m?.alternate ?? k.note)}{quote && <span className="block text-xs text-muted">“{quote.replace(/\*\*|__/g, '').slice(0, 160)}”</span>}</td>
              <td>{k.ok === true ? (m?.mark === 'better' ? 'Better' : 'Meets') : k.ok === false ? 'Fails' : 'Not confirmed'}</td>
            </tr>
          )
        })}</tbody>
      </table>}
    </div>
  )
}

function Item({ row, result }: { row: PackageRow; result: Result }) {
  const fix = result.findings.find((f) => f.fix)?.fix
  const alts = (fix?.alternates ?? []).filter((a) => a.rank !== 'failed')
  const acting = result.findings.filter((f) => ACTION(f) && !(row.still_made === 'discontinued' && f.configure?.length))
  const note = row.decision === 'send_back' ? row.return_note : row.approval_note
  return (
    <section className="memo-item flex flex-col gap-3 border-t-2 border-edge pt-4">
      <div>
        <span className="font-mono text-xs text-muted">{row.number ?? 'Upload'} · from {row.sender ?? 'you'}</span>
        <h2 className="text-lg font-semibold">{row.title}</h2>
        <p><span className="font-semibold">{row.stamp}</span> <span className="text-muted">({DECISION_LABEL[row.decision]} · {row.meets} meet, {row.doesnt_meet} don't, {row.couldnt_confirm} couldn't be confirmed)</span></p>
      </div>
      {row.what_to_send.length > 0 && <div><span className={CAPS}>What to send</span>
        <ol className="ml-5 list-decimal">{row.what_to_send.map((t) => <li key={t}>{t}</li>)}</ol></div>}
      {row.still_made !== 'discontinued' && <ConfigureLines findings={result.findings} />}
      {acting.length > 0 && <div><span className={CAPS}>Findings needing action</span>
        <table className="w-full text-sm"><thead><tr className={CAPS}><th className="py-1 text-left">Requirement</th>
          <th className="text-left">Required</th><th className="text-left">Submitted</th><th className="text-left">Evidence</th></tr></thead>
          <tbody>{acting.map((f) => <FindingRow key={f.id} f={f} />)}</tbody></table></div>}
      {fix && alts.length > 0 && <div className="flex flex-col gap-3"><span className={CAPS}>Alternates, ranked in code</span>
        {alts.map((a) => <PointByPoint key={a.source_url} a={a} fix={fix} result={result} />)}</div>}
      {note && <div><span className={CAPS}>{row.decision === 'send_back' ? 'Note to the sub' : 'Note to the architect'}</span>
        <pre className="whitespace-pre-wrap font-sans">{note}</pre></div>}
      <p className="text-xs text-muted">Checked by {checkedBy(result)}.</p>
    </section>
  )
}

export default function Memo({ runId }: { runId: string }) {
  const [data, setData] = useState<{ pkg: PackageSummary; results: Result[]; project: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    Promise.all([getPackage(runId), fetch(`/api/runs/${runId}/results`).then((r) => r.ok ? r.json() : Promise.reject(new Error('No such run'))),
      getProject().catch(() => null)])
      .then(([pkg, res, project]) => setData({ pkg, results: res.results, project: project?.name ?? '' }))
      .catch((e: Error) => setError(e.message))
  }, [runId])
  if (error) return <main className="memo p-8">Couldn't load this run: {error}</main>
  if (!data) return <main className="memo p-8">Loading…</main>
  const byId = Object.fromEntries(data.results.map((r) => [r.case_id, r]))
  const specs = [...new Set(data.results.map((r) => [r.spec_section, r.spec_title].filter(Boolean).join(' ')).filter(Boolean))]
  const { pkg } = data
  return (
    <main className="memo mx-auto flex max-w-[8.5in] flex-col gap-6 p-8 text-sm">
      <a href="/" className="no-print text-muted underline">← Back to SpecCheck</a>
      <header className="flex flex-col gap-1">
        <span className={CAPS}>Package review memo</span>
        <h1 className="text-2xl font-bold">{data.project}</h1>
        <p className="text-muted">Spec {specs.join(' · ')} · run {runId} on {runDate(runId)} · {modeLabel(data.results)}</p>
        <p>{pkg.rows.length} submittals · {pkg.ready} ready to forward · {pkg.need_changes} need changes
          {pkg.not_checked ? ` · ${pkg.not_checked} not checked` : ''}{pkg.manual_review_suggested ? ` · ${pkg.manual_review_suggested} worth a manual look` : ''}</p>
        <button className="btn no-print self-start" onClick={() => window.print()}>Print or save as PDF</button>
      </header>
      <PackageMatrix rows={pkg.rows} />
      {pkg.rows.map((row) => byId[row.case_id] && <Item key={row.case_id} row={row} result={byId[row.case_id]} />)}
      <footer className="memo-item flex flex-col gap-6 border-t-2 border-edge pt-6">
        <p className="text-xs text-muted">Decisions above are SpecCheck's recommendations; models read and quote, code decides. A person signs below.</p>
        <p>Reviewer: ______________________________ Date: ______________</p>
      </footer>
    </main>
  )
}
