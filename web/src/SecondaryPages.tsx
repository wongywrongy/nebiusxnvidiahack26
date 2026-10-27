import { useEffect, useState, type DragEvent } from 'react'
import { DECISION_LABEL, draftSpec, saveChecklist, getScores, getSpecs, modelName, type Checklist, type Requirement, type SavedChecklist, type Scores, type Specs } from './api'

const link = 'text-muted underline underline-offset-4 hover:text-ink'
const cell = 'border-b border-line px-3 py-3 text-left align-top'
const date = (value: string) => new Date(value.length === 10 ? `${value}T00:00:00` : value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })

function provenance(checklist: Checklist) {
  const drafted = checklist.drafted_by
    ? `Drafted by ${modelName(checklist.drafted_by)} from ${checklist.source_name || 'the spec'}${checklist.drafted_at ? ` on ${date(checklist.drafted_at)}` : ' (date not recorded)'}`
    : 'Draft provenance not recorded'
  return `${drafted}; ${checklist.reviewed_at ? `reviewed on ${date(checklist.reviewed_at)}` : 'review date not recorded'}.`
}

function RequirementTable({ checklist, onChange, disabled }: { checklist: Checklist; onChange?: (requirements: Requirement[]) => void; disabled?: boolean }) {
  const typed = checklist.requirements.some((r) => r.product_type)
  const edit = (id: string, patch: Partial<Requirement>) => onChange?.(checklist.requirements.map((r) => r.id === id ? { ...r, ...patch } : r))
  const input = 'w-full min-w-24 rounded-md border border-edge bg-well px-2 py-1 text-ink disabled:opacity-50'
  return (
    <div className="overflow-x-auto rounded-xl border border-line" role="region" aria-label="Checklist requirements" tabIndex={0}>
      <table className="w-full min-w-[880px] text-xs">
        <thead className="bg-well text-muted"><tr>
          {['Paragraph', 'Property', 'Operator', 'Value', 'Unit', 'Severity', 'Applies to', 'Text'].map((label) => <th scope="col" className={cell} key={label}>{label}</th>)}
          {typed && <th scope="col" className={cell}>Product type</th>}
          {onChange && <th scope="col" className={cell}>Edit</th>}
        </tr></thead>
        <tbody>{checklist.requirements.map((r) => (
          <tr key={r.id}>
            <td className={cell}>{r.paragraph || '—'}</td><td className={`${cell} font-mono`}>{r.property}</td>
            <td className={cell}>{onChange ? <select aria-label={`Operator for ${r.id}`} value={r.operator} disabled={disabled}
              className={input} onChange={(e) => edit(r.id, { operator: e.target.value })}>
              {['gte', 'lte', 'eq', 'eq_ref', 'contains', 'any_of', 'exists'].map((op) => <option key={op}>{op}</option>)}
            </select> : r.operator}</td>
            <td className={cell}>{onChange ? <input aria-label={`Value for ${r.id}`} disabled={disabled} className={input}
              value={Array.isArray(r.value) ? r.value.join(', ') : r.value ?? ''} onChange={(e) => edit(r.id, { value: e.target.value })} />
              : Array.isArray(r.value) ? r.value.join(', ') : r.value ?? '—'}</td>
            <td className={cell}>{r.unit || '—'}</td><td className={cell}>{onChange ? <select aria-label={`Severity for ${r.id}`}
              value={r.severity} disabled={disabled} className={input} onChange={(e) => edit(r.id, { severity: e.target.value })}>
              {['critical', 'major', 'minor'].map((s) => <option key={s}>{s}</option>)}
            </select> : r.severity}</td>
            <td className={cell}>{r.applies_to.length ? r.applies_to.join(', ') : 'All submittal roles'}</td>
            <td className={`${cell} min-w-64`}>{r.text}</td>
            {typed && <td className={cell}>{r.product_type?.replace(/_/g, ' ') || 'All product types'}</td>}
            {onChange && <td className={cell}><button className="btn" disabled={disabled} aria-label={`Delete requirement ${r.id}`}
              onClick={() => onChange(checklist.requirements.filter((rule) => rule.id !== r.id))}>Delete</button></td>}
          </tr>
        ))}</tbody>
      </table>
      {!checklist.requirements.length && <p className="px-3 py-4 text-muted">No requirements were found.</p>}
    </div>
  )
}

export function SpecsPage({ back, onUse }: { back: string; onUse: (checklist: SavedChecklist) => void }) {
  const [specs, setSpecs] = useState<Specs | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [section, setSection] = useState('07 84 00')
  const [title, setTitle] = useState('Firestopping')
  const [draft, setDraft] = useState<Checklist | null>(null)
  const [used, setUsed] = useState<SavedChecklist | null>(null)
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  useEffect(() => { getSpecs().then(setSpecs).catch((e: Error) => setError(e.message)) }, [])
  const live = specs?.mode === 'live'

  async function upload(file?: File) {
    if (!file || !live || busy) return
    setBusy(true); setError(null); setDraft(null); setUsed(null)
    if (!/^\d{2} \d{2} \d{2}$/.test(section) || !title.trim()) {
      setError('Enter a section in 00 00 00 format and a title.'); setBusy(false); return
    }
    try { setDraft((await draftSpec(file, section, title.trim())).draft) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  function drop(e: DragEvent) { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]) }
  async function useChecklist() {
    if (!draft || busy) return
    setBusy(true); setError(null)
    try {
      const checklist = await saveChecklist({ ...draft, requirements: draft.requirements.map((r) => ({ ...r,
        value: typeof r.value !== 'string' ? r.value : r.operator === 'any_of'
          ? r.value.split(',').map((v) => v.trim()).filter(Boolean)
          : !r.value.trim() ? null : /^-?\d+(\.\d+)?$/.test(r.value.trim()) ? Number(r.value) : r.value,
      })) })
      onUse(checklist); setUsed(checklist)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

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
        <p className="text-muted">{live ? 'Draft rules, edit them, then use the checklist for your uploaded product sheets. Drafts expire after 14 days.'
          : 'Live only. Drafting uses Nemotron 3 Super on Token Factory. Mock mode cannot create a draft, so “Use this checklist” is unavailable.'}</p>
        {specs?.try?.filter((d) => d.kind === 'spec').map((d) => <p key={d.url} className="text-muted">Try a spec: <a href={d.url}
          target="_blank" rel="noreferrer" className={link} onClick={() => { setSection(d.fits); setTitle(d.title.replace(/ \d{2} \d{2} \d{2}$/, '')) }}>{d.title} ↗</a>.
          {' '}Pair with the Schlage ND Series product sheet linked in the Inbox.</p>)}
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
          <p className="font-medium">Drafted by Nemotron 3 Super · edited by you · unreviewed · this browser only</p>
          <p className="text-xs text-muted">{draft.source_name}{draft.drafted_at ? ` · ${date(draft.drafted_at)}` : ''}</p>
          <p className="text-xs text-muted">Edit values, operators and severity, or delete a rule. For any_of, separate allowed values with commas. Keep 1–30 rules.</p>
          <RequirementTable checklist={draft} disabled={busy} onChange={(requirements) => { setDraft({ ...draft, requirements }); setUsed(null) }} />
          {used ? <p role="status" className="text-muted">{used.section} {used.title} is ready in this browser’s upload spec menu. <a href="#" className={link}>Return to {back} →</a></p>
            : <button className="btn self-start" disabled={busy || !draft.requirements.length || draft.requirements.length > 30}
              onClick={useChecklist}>{busy ? 'Saving checklist…' : 'Use this checklist for my uploads'}</button>}
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
        <p className="text-muted">{scores.validity
          ? `${scores.validity.invalid_items} of ${scores.validity.requested_items} items invalid for acceptance. ${scores.unnecessary_notes?.n ?? 0} unnecessary notes.`
          : 'Legacy recording: acceptance validity was not recorded.'}</p>
        {scores.release_gate && <p className="text-muted">Case evidence: {scores.release_gate.passed ? 'prerequisites passed; full release review still required' : scores.release_gate.issues.join('; ')}.</p>}
        {scores.fresh_model_cost_usd !== undefined && <p className="text-muted">Fresh charges for scored items: ${scores.fresh_model_cost_usd.toFixed(6)} model usage · {scores.fresh_web_credits ?? 0} Tavily credits. Incomplete accounting is marked invalid.</p>}
        {scores.job_name && <p className="text-muted">Evaluated on {scores.runner || 'Nebius Serverless Job'} {scores.job_name}, {date(scores.generated_at)}.</p>}
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {([
            ['Right call', scores.right_call], ['Planted problems caught', scores.caught],
            ['Major false alarms on clean packages', scores.false_alarms], ['Fixes that pass the spec', scores.fixes_passing],
          ] as const).map(([label, score]) => (
            <div key={label} className="flex flex-col gap-2 border-t border-line py-4">
              <dt className="text-muted">{label}</dt><dd className="font-mono text-2xl">{score.n} <span className="text-sm text-muted">of {score.of}</span></dd>
            </div>
          ))}
        </dl>
        <p className="text-muted">{scores.mode === 'mock' ? 'Fixture answers for: ' : 'Models on Nebius Token Factory: '}{[...new Set(Object.values(scores.models))].map(modelName).join(' · ')}.</p>
        {scores.quote_gate ? <p className="text-muted">Quote gate: {scores.quote_gate.claims_kept} of {scores.quote_gate.claims_extracted} extracted claims kept
          {' '}({scores.quote_gate.claims_drop_rate == null ? 'no claims read' : `${(scores.quote_gate.claims_drop_rate * 100).toFixed(1)}% dropped`});
          {' '}{scores.quote_gate.web_values_kept} of {scores.quote_gate.web_values_read} web values kept
          {' '}({scores.quote_gate.web_values_drop_rate == null ? 'no values read' : `${(scores.quote_gate.web_values_drop_rate * 100).toFixed(1)}% dropped`}).
          Includes replacement candidates and investigated value reads.</p>
          : <p className="text-muted">Quote-gate counts were not recorded in this score file.</p>}
        <p className="max-w-3xl leading-6 text-muted">The answer key is the hand-authored expected decision and problem types for each bundled case. It includes clean packages, outdated documents, a discontinued product and spec mismatches. Scores compare the pipeline's computed findings with that fixed key; they measure this small demonstration set, not performance on unseen submittals.</p>
        <div className="overflow-x-auto rounded-xl border border-line" role="region" aria-label="Per-case scores" tabIndex={0}>
          <table className="w-full min-w-[880px] text-xs">
            <thead className="bg-well text-muted"><tr>{['Case', 'Expected', 'Got', 'Problems expected', 'Problems found', 'Fix', 'Time', 'Cost'].map((s) => <th key={s} className={cell} scope="col">{s}</th>)}</tr></thead>
            <tbody>{scores.rows.map((r) => <tr key={r.id}>
              <th className={`${cell} min-w-40 font-normal`} scope="row"><span className="font-mono text-muted">{r.id}</span><br />{r.product || r.title}</th>
              <td className={cell}>{DECISION_LABEL[r.expected]}</td>
              <td className={cell}>{r.error ? "Couldn't scan" : r.decision ? DECISION_LABEL[r.decision] : '—'}
                {r.valid === false && <p className="mt-1 text-muted">Invalid evidence: {r.diagnostics?.map(d => `${d.stage}: ${d.message}`).join('; ') || 'Incomplete item'}</p>}</td>
              <td className={cell}>{r.expected_problems.join(', ') || 'None'}</td>
              <td className={cell}>{r.error ? '—' : r.found_problems?.join(', ') || 'None'}</td>
              <td className={`${cell} min-w-40`}>{r.fix ? r.fix.passes ? r.fix.suggest : `None passed (${r.fix.candidates} checked)` : '—'}</td>
              <td className={`${cell} whitespace-nowrap`}>{r.time_ms === undefined ? '—' : `${(r.time_ms / 1000).toFixed(1)} s`}</td>
              <td className={`${cell} font-mono`}>{r.cost_usd === undefined ? '—' : `$${r.cost_usd.toFixed(4)}`}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="text-xs text-muted">Cost includes model usage and Tavily credits. {scores.mode === 'mock' ? 'Mock values are estimates; no tokens or credits were spent.' : 'Usage and time belong to the recorded run. Cached cost and credits are usage equivalents, not fresh charges; warm-cache times are not uncached provider latency. Unnecessary notes still count as wrong calls.'}</p>
      </>}
    </>
  )
}
