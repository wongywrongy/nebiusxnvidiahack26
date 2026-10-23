// Types mirror api/schemas.py. Keep them in sync by hand (small surface).

export type Decision = 'approve' | 'approve_with_note' | 'send_back'
export type Stage =
  | 'queued' | 'ingest' | 'triage' | 'extract' | 'spec_check' | 'verify' | 'investigate' | 'fix' | 'report' | 'done' | 'error'

// An item as /api/project, /api/inbox return it (api/main.py _public).
export interface Case {
  id: string; number?: string; title: string; product?: string; from?: string; trade?: string; email?: string
  section: string; received?: string; watch?: { approved: string }; submittal: { role?: string; file: string; url?: string }[]
  pages: number; upload: boolean; ready: boolean
}
export interface Sender { from: string; trade?: string; email?: string; items: Case[] }
export interface Project {
  name: string; specs: { section: string; owner: string }[]; tray: Sender[]; watched: Case[]
  // mock: recorded answers, no API calls (token counts estimated). live: Token Factory and Tavily, cached after the first run.
  mode: 'mock' | 'live'
  // Nightly re-check of approved items (scripts/recheck.py, run as a Nebius Serverless Job): when it last ran, if ever.
  recheck?: Recheck | null
  jobs_available?: boolean
}
export interface Recheck {
  mode: 'mock' | 'live'; job_name?: string | null; duration_ms?: number | null
  checked_at: string; runner: string; items: { id: string; status: 'no_change' | 'changed' | 'discontinued' | 'unverified'; detail: string }[]
}

export interface Event {
  run_id: string
  case_id: string | null
  t_ms: number
  stage: Stage
  message: string
  model: string | null
  data: Record<string, unknown> | null
}

interface Evidence { url: string; tier: string; title: string; retrieved_at?: string; sha256?: string; archived_path?: string | null; cache_hit?: boolean | null; excerpt?: string | null }
export interface Finding {
  id: string
  check: string
  verdict: 'pass' | 'fail' | 'outdated' | 'unverified' | 'note' | 'not_applicable' | 'pending'
  severity: 'critical' | 'major' | 'minor' | 'info'
  title: string
  detail: string
  why_it_matters?: string | null
  spec_ref?: string | null
  requirement_id?: string | null
  claim_ids: string[]
  highlights: Mark[]
  compare?: Compare | null
  evidence: Evidence[]
  quote?: string | null // status findings: the source's exact words
  decided_by: string
  fix?: Fix | null
}
// Send-backs only: what to send instead, each candidate run through the same checks as a new submittal.
interface FixCheck { label: string; ok: boolean | null; note: string; requirement_id?: string | null; evidence?: Evidence[] }
interface FixCandidate { name: string; source_url: string; documents?: Evidence[]; checks: FixCheck[]; passes: boolean;
  selection?: { model: string; page: number; quote: string; origin?: 'submitted' | 'agent_proposal' } | null }
export interface Fix { head: string; query: string; candidates: FixCandidate[]; suggest: string }
export type Value = string | number | string[] | null
// One comparison per finding. rows: currency findings, only the fields that changed.
export interface Compare {
  left_label: string; left_value: Value; right_label: string; right_value: Value
  verdict: 'fail' | 'pass' | 'changed' | 'unverified'; rows: CompareRow[]
}
export interface CompareRow { property: string; label: string; submitted: string | null; current: string | null; changed: boolean }
// One model call (api/schemas.py Usage). thinking: live only, whether the server was asked not to think.
export interface Usage {
  task: string; tier: string; model: string; input_tokens: number; output_tokens: number; cost_usd: number; latency_ms: number
  cached?: boolean; format?: string | null; reasoning_tokens?: number; thinking?: string | null
}
// "nvidia/nemotron-3-super-120b-a12b" -> "Nemotron 3 Super"; anything else keeps its id.
export const modelName = (id: string) => {
  const m = /nemotron[-_ ]?(\d(?:[._]\d)?)[-_ ]?(nano|super|ultra|lightning)/i.exec(id)
  return m ? `Nemotron ${m[1].replace('_', '.')} ${m[2][0].toUpperCase()}${m[2].slice(1).toLowerCase()}` : id.replace(/^.*\//, '')
}
interface Claim { id: string; property: string; value: unknown; unit?: string | null; page?: number | null; quote?: string | null }
export interface Investigation {
  steps: { n: number; tool: string; args: Record<string, unknown>; summary: string; credits: number; ms: number }[]
  outcome: 'found' | 'not_found' | 'capped'
}
export interface Result {
  case_id: string
  title: string
  decision: Decision
  summary: string
  findings: Finding[]
  comparison: CompareRow[]
  claims: Claim[]
  document_revision?: string | null
  note_to_subcontractor: string
  usage: Usage[]
  web_credits: number
  duration_ms: number
  investigation?: Investigation | null
  mode?: 'mock' | 'live' | null
  replayed_from?: string | null
  warnings?: string[]
  diagnostics?: { stage: string; kind: string; message: string }[]
  validity?: 'valid' | 'invalid' | 'legacy'
  fresh_model_cost_usd?: number; fresh_web_credits?: number; queue_ms?: number
  ocr_pages?: number
  evidence_label?: string | null
  archived_submittals?: string[]
  claims_extracted?: number; claims_kept?: number; web_values_read?: number; web_values_kept?: number
}

export interface Health { mode: 'mock' | 'live'; budget: { usd_left: number; credits_left: number } }
export async function getHealth(): Promise<Health> { return ok(await fetch('/api/health')) }

export interface Requirement {
  id: string; section: string; paragraph: string; property: string; operator: string; value: Value
  unit?: string | null; severity: string; applies_to: string[]; text: string
}
export interface Checklist {
  requirements: Requirement[]; drafted_by?: string | null; source_name: string; source_url?: string | null
  source_sha256?: string | null; drafted_at?: string | null; reviewed_at?: string | null
}
export interface SpecSection {
  section: string; title: string; owner: string; control_version: string; source_url: string
  checklist: Checklist; status: 'reviewed' | 'saved' | 'fixture'; note: string; used_by_scans: 'mock' | 'live'
}
export interface Specs { mode: Project['mode']; sections: SpecSection[] }
export async function getSpecs(): Promise<Specs> { return ok(await fetch('/api/specs')) }
export async function draftSpec(file: File, section: string, title: string): Promise<{ draft: Checklist; usage: Usage }> {
  return ok(await fetch(`/api/specs/draft?section=${encodeURIComponent(section)}&title=${encodeURIComponent(title)}&name=${encodeURIComponent(file.name)}`, {
    method: 'POST', headers: { 'content-type': 'application/pdf' }, body: file,
  }))
}

interface Score { n: number; of: number }
export interface Scores {
  runner?: string; job_name?: string | null
  quote_gate?: { claims_extracted: number; claims_kept: number; web_values_read: number; web_values_kept: number
    claims_drop_rate: number | null; web_values_drop_rate: number | null }
  mode: Project['mode']; generated_at: string; run_id: string; models: Record<string, string>
  right_call: Score; caught: Score; false_alarms: Score; fixes_passing: Score
  validity?: { invalid_items: number; requested_items: number }
  unnecessary_notes?: Score
  fresh_model_cost_usd?: number; fresh_web_credits?: number
  release_gate?: { scope?: 'cases'; passed: boolean; issues: string[] }
  rows: { id: string; title: string; product: string; expected: Decision; expected_problems: string[]
    decision?: Decision; found_problems?: string[]; error?: boolean; right_call?: boolean
    valid?: boolean; diagnostics?: { stage: string; message: string }[]
    fix?: { suggest: string | null; passes: boolean; candidates: number } | null
    time_ms?: number; cost_usd?: number }[]
}
export async function getScores(): Promise<Scores> { return ok(await fetch('/api/scores')) }

export interface CloudJob {
  name: string; id?: string | null; created_at: string; state: 'queued' | 'starting' | 'running' | 'done' | 'failed'
  raw_state?: string | null; state_known?: boolean; poll_error?: string
}
export async function getJobs(): Promise<{ available: boolean; jobs: CloudJob[] }> { return ok(await fetch('/api/watch/jobs')) }
export async function getWatch(): Promise<Recheck | null> {
  const r = await fetch('/api/watch')
  return r.status === 404 ? null : ok(r)
}
export const archiveUrl = (path: string) => `/api/evidence/${path.split('/').map(encodeURIComponent).join('/')}`

export async function getProject(): Promise<Project> {
  const project = await ok<Project>(await fetch('/api/project'))
  if (!project || !['mock', 'live'].includes(project.mode) || typeof project.name !== 'string'
    || !Array.isArray(project.specs) || !Array.isArray(project.tray) || !Array.isArray(project.watched)
    || project.specs.some((s) => !s || typeof s.section !== 'string')
    || project.tray.some((sender) => !sender || !Array.isArray(sender.items))) {
    throw new Error('Project response was incomplete. Reload to try again.')
  }
  if ([...project.watched, ...project.tray.flatMap((s) => s.items)].some((c) => !c || typeof c.id !== 'string'
    || typeof c.section !== 'string' || !Array.isArray(c.submittal)
    || c.submittal.some((d) => !d || typeof d.file !== 'string'))) {
    throw new Error('Project attachments were incomplete. Reload to try again.')
  }
  return project
}

async function ok<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Request failed (${r.status})`)
  return r.json()
}

/** Add a tray item to the inbox. Nothing runs until scan(). */
export async function addToInbox(id: string): Promise<Case> {
  return ok(await fetch('/api/inbox', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ id }) }))
}

/** Add an uploaded PDF to the inbox. Nothing runs until scan(). */
export async function uploadToInbox(file: File): Promise<Case> {
  return ok(await fetch(`/api/inbox?name=${encodeURIComponent(file.name)}`, {
    method: 'POST', headers: { 'content-type': 'application/pdf' }, body: file,
  }))
}

/** One run over inbox items. delayMs paces mock mode so the stages are visible. */
export async function scan(ids: string[], delayMs = 700, refreshWeb = false): Promise<{ run_id: string; note?: string | null }> {
  return ok(await fetch('/api/scan', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ids, delay_ms: delayMs, refresh_web: refreshWeb }),
  }))
}

export function streamEvents(runId: string, onEvent: (e: Event) => void, onEnd: () => void, onError: (e: Error) => void): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`)
  es.onmessage = (m) => {
    try { onEvent(JSON.parse(m.data)) }
    catch { es.close(); onError(new Error('Scan updates were unreadable. Retry this item.')) }
  }
  es.onerror = () => { es.close(); onError(new Error('Lost the scan connection. Retry this item.')) }
  es.addEventListener('end', () => { es.close(); onEnd() })
  return () => es.close()
}

export async function getResult(runId: string, caseId: string): Promise<Result> {
  return ok(await fetch(`/api/runs/${runId}/results/${caseId}`))
}

export type Tone = 'red' | 'amber' | 'blue' | 'green'
interface Box { x0: number; y0: number; x1: number; y1: number }
// Where one claim behind a finding sits: file and page in data/raw, boxes as fractions of the page.
export interface Mark {
  claim_id: string; doc_file: string | null; page: number | null; quote: string | null; boxes: Box[]; kind: 'problem' | 'checked'
}
export interface DocPages { file: string; name: string; pages: { width: number; height: number }[] }
export interface TextPage { page: number; text: string }

const basename = (f: string) => f.split('/').pop()!

/** Page sizes of a downloaded submittal PDF, or null when it is not in data/raw. */
export async function getDocPages(caseId: string, file: string): Promise<DocPages | null> {
  const r = await fetch(`/api/docs/${caseId}/${encodeURIComponent(basename(file))}/pages`)
  return r.ok ? { file, name: basename(file), pages: (await r.json()).pages } : null
}

export const pageUrl = (caseId: string, file: string, n: number) =>
  `/api/docs/${caseId}/${encodeURIComponent(basename(file))}/pages/${n}.png`

export async function getCaseText(caseId: string): Promise<TextPage[]> {
  return (await ok<{ pages: TextPage[] }>(await fetch(`/api/cases/${caseId}/text`))).pages
}

export const DECISION_LABEL: Record<Decision, string> = {
  approve: 'Approve',
  approve_with_note: 'Approve with note',
  send_back: 'Send back',
}
export const DECISION_COLOR: Record<Decision, string> = {
  approve: '#2e9e68',
  approve_with_note: '#7fa7d9', // FYI blue: approved, with a note
  send_back: '#d9534f',
}
