import { useEffect, useState, type DragEvent } from 'react'
import { DECISION_LABEL, draftSpec, getScores, getSpecs, modelName, type Checklist, type Scores, type Specs } from './api'

const link = 'text-muted underline underline-offset-4 hover:text-ink'
const cell = 'border-b border-line px-3 py-3 text-left align-top'
const date = (value: string) => new Date(value.length === 10 ? `${value}T00:00:00` : value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })

function provenance(checklist: Checklist) {
  const drafted = checklist.drafted_by
    ? `Drafted by ${modelName(checklist.drafted_by)} from ${checklist.source_name || 'the spec'}${checklist.drafted_at ? ` on ${date(checklist.drafted_at)}` : ' (date not recorded)'}`
    : 'Draft provenance not recorded'
  return `${drafted}; ${checklist.reviewed_at ? `reviewed on ${date(checklist.reviewed_at)}` : 'review date not recorded'}.`
}

function RequirementTable({ checklist }: { checklist: Checklist }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line" role="region" aria-label="Checklist requirements" tabIndex={0}>
      <table className="w-full min-w-[880px] text-xs">
        <thead className="bg-well text-muted"><tr>
          {['Paragraph', 'Property', 'Operator', 'Value', 'Unit', 'Severity', 'Applies to', 'Text'].map((label) => <th scope="col" className={cell} key={label}>{label}</th>)}
        </tr></thead>
        <tbody>{checklist.requirements.map((r) => (
          <tr key={r.id}>
            <td className={cell}>{r.paragraph || '—'}</td><td className={`${cell} font-mono`}>{r.property}</td>
            <td className={cell}>{r.operator}</td><td className={cell}>{Array.isArray(r.value) ? r.value.join(', ') : r.value ?? '—'}</td>
            <td className={cell}>{r.unit || '—'}</td><td className={cell}>{r.severity}</td>
            <td className={cell}>{r.applies_to.length ? r.applies_to.join(', ') : 'All submittal roles'}</td>
            <td className={`${cell} min-w-64`}>{r.text}</td>
          </tr>
        ))}</tbody>
      </table>
      {!checklist.requirements.length && <p className="px-3 py-4 text-muted">No requirements were found.</p>}
    </div>
  )
}

export function SpecsPage({ back }: { back: string }) {
  const [specs, setSpecs] = useState<Specs | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [section, setSection] = useState('07 84 00')
  const [title, setTitle] = useState('Firestopping')
  const [draft, setDraft] = useState<Checklist | null>(null)
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  useEffect(() => { getSpecs().then(setSpecs).catch((e: Error) => setError(e.message)) }, [])
  const live = specs?.mode === 'live'

  async function upload(file?: File) {
    if (!file || !live || busy) return
    setBusy(true); setError(null); setDraft(null)
    if (!/^\d{2} \d{2} \d{2}$/.test(section) || !title.trim()) {
      setError('Enter a section in 00 00 00 format and a title.'); setBusy(false); return
    }
    try { setDraft((await draftSpec(file, section, title.trim())).draft) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  function drop(e: DragEvent) { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]) }

  return (
    <>
      <a className={link} href="#">← Back to {back}</a>
      <h1 className="text-2xl font-bold tracking-tight">Specs</h1>
      {!specs && !error && <p className="text-muted" role="status">Loading checklists…</p>}
      {specs?.sections.map((spec) => (
        <section key={spec.section} className="flex min-w-0 flex-col gap-3">
          <div>
            <h2 className="text-lg font-semibold">{spec.section} · {spec.title}</h2>
            <p className="text-muted">{spec.owner} · {spec.control_version} · <a className={link} href={spec.source_url} target="_blank" rel="noreferrer">Source PDF ↗</a></p>
          </div>
          <p className="text-muted">{spec.status === 'fixture'
            ? `Mock stand-in · not reviewed. ${specs.mode === 'mock' ? 'Used by mock scans.' : 'Live scans extract the source spec until a reviewed checklist is saved.'}`
            : `${spec.status === 'reviewed' ? 'Reviewed' : 'Saved'} checklist for live scans.${specs.mode === 'mock' ? ' Mock scans use fixture checklists.' : ''} ${provenance(spec.checklist)}`}</p>
          {spec.note && <p className="text-xs leading-5 text-muted">{spec.note}</p>}
          <RequirementTable checklist={spec.checklist} />
        </section>
      ))}
      <section className="flex min-w-0 flex-col gap-3 border-t border-line pt-6">
        <h2 className="text-lg font-semibold">Draft a checklist from a spec PDF</h2>
        <p className="text-muted">{live ? 'The draft stays in this browser view until you leave. It is not saved as a project checklist or used by scans.' : 'Live only. Drafting uses Nemotron 3 Super on Token Factory.'}</p>
        <label className="flex items-center gap-3 text-muted">Spec section
          <input list="spec-sections" value={section} onChange={(e) => {
            setSection(e.target.value)
            const known = specs?.sections.find((s) => s.section === e.target.value)
            if (known) setTitle(known.title)
          }} disabled={!live || busy} pattern="\d{2} \d{2} \d{2}" maxLength={8} placeholder="00 00 00"
            className="min-w-0 rounded-lg border border-edge bg-well px-3 py-2 text-ink disabled:opacity-50" />
          <datalist id="spec-sections">
            {specs?.sections.map((spec) => <option key={spec.section} value={spec.section}>{spec.title}</option>)}
          </datalist>
        </label>
        <label className="flex items-center gap-3 text-muted">Section title
          <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={!live || busy} maxLength={160} required
            className="min-w-0 rounded-lg border border-edge bg-well px-3 py-2 text-ink disabled:opacity-50" />
        </label>
        <label onDragOver={(e) => { e.preventDefault(); if (live && !busy) setOver(true) }} onDragLeave={() => setOver(false)} onDrop={drop}
          className={`flex min-h-32 flex-col items-center justify-center gap-1 rounded-xl border border-dashed px-4 text-center ${over ? 'border-flare bg-flare/5' : 'border-edge'} ${live && !busy ? 'cursor-pointer' : 'text-muted'}`}>
          <span>{busy ? 'Drafting checklist…' : live ? 'Drop a spec PDF here or browse' : 'Live only'}</span>
          <input type="file" accept="application/pdf,.pdf" disabled={!live || busy} className="sr-only" aria-label="Draft a checklist from a spec PDF"
            onChange={(e) => { upload(e.target.files?.[0]); e.target.value = '' }} />
        </label>
        {busy && <p className="text-muted" role="status">Nemotron 3 Super is reading the spec.</p>}
        {error && <p className="text-bad" role="alert">{error}</p>}
        {draft && <>
          <p className="font-medium">Drafted by {modelName(draft.drafted_by ?? '')} · not reviewed · not used by scans</p>
          <p className="text-xs text-muted">{draft.source_name}{draft.drafted_at ? ` · ${date(draft.drafted_at)}` : ''}</p>
          <RequirementTable checklist={draft} />
        </>}
      </section>
    </>
  )
}

export function ScoreboardPage({ back }: { back: string }) {
  const [scores, setScores] = useState<Scores | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { getScores().then(setScores).catch((e: Error) => setError(e.message)) }, [])
  return (
    <>
      <a className={link} href="#">← Back to {back}</a>
      <h1 className="text-2xl font-bold tracking-tight">Scoreboard</h1>
      {error && <p className="text-muted" role="alert">{error}</p>}
      {!scores && !error && <p className="text-muted" role="status">Loading scores…</p>}
      {scores && <>
        <p className="-mt-3 text-muted">{scores.mode === 'live' ? `Live run recorded ${date(scores.generated_at)}` : `Mock · ${date(scores.generated_at)} · fixture answers, estimated token counts and cost`}</p>
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {([
            ['Right call', scores.right_call], ['Planted problems caught', scores.caught],
            ['Clean packages wrongly flagged', scores.false_alarms], ['Fixes that pass the spec', scores.fixes_passing],
          ] as const).map(([label, score]) => (
            <div key={label} className="flex flex-col gap-2 border-t border-line py-4">
              <dt className="text-muted">{label}</dt><dd className="font-mono text-2xl">{score.n} <span className="text-sm text-muted">of {score.of}</span></dd>
            </div>
          ))}
        </dl>
        <p className="text-muted">Models: {[...new Set(Object.values(scores.models))].map(modelName).join(' · ')} on Nebius Token Factory.</p>
        <p className="max-w-3xl leading-6 text-muted">The answer key is the hand-authored expected decision and problem types for each bundled case. It includes clean packages, outdated documents, a discontinued product and spec mismatches. Scores compare the pipeline's computed findings with that fixed key; they measure this small demonstration set, not performance on unseen submittals.</p>
        <div className="overflow-x-auto rounded-xl border border-line" role="region" aria-label="Per-case scores" tabIndex={0}>
          <table className="w-full min-w-[880px] text-xs">
            <thead className="bg-well text-muted"><tr>{['Case', 'Expected', 'Got', 'Problems expected', 'Problems found', 'Fix', 'Time', 'Cost'].map((s) => <th key={s} className={cell} scope="col">{s}</th>)}</tr></thead>
            <tbody>{scores.rows.map((r) => <tr key={r.id}>
              <th className={`${cell} min-w-40 font-normal`} scope="row"><span className="font-mono text-muted">{r.id}</span><br />{r.product || r.title}</th>
              <td className={cell}>{DECISION_LABEL[r.expected]}</td>
              <td className={cell}>{r.error ? "Couldn't scan" : r.decision ? DECISION_LABEL[r.decision] : '—'}</td>
              <td className={cell}>{r.expected_problems.join(', ') || 'None'}</td>
              <td className={cell}>{r.error ? '—' : r.found_problems?.join(', ') || 'None'}</td>
              <td className={`${cell} min-w-40`}>{r.fix ? r.fix.passes ? r.fix.suggest : `None passed (${r.fix.candidates} checked)` : '—'}</td>
              <td className={`${cell} whitespace-nowrap`}>{r.time_ms === undefined ? '—' : `${(r.time_ms / 1000).toFixed(1)} s`}</td>
              <td className={`${cell} font-mono`}>{r.cost_usd === undefined ? '—' : `$${r.cost_usd.toFixed(4)}`}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="text-xs text-muted">Cost includes model usage and Tavily credits. {scores.mode === 'mock' ? 'Mock values are estimates; no tokens or credits were spent.' : 'Usage and time belong to the recorded run.'}</p>
      </>}
    </>
  )
}
