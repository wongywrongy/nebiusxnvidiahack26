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
}
export interface Recheck {
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

interface Evidence { url: string; tier: string; title: string; retrieved_at?: string; sha256?: string }
export interface Finding {
  id: string
  check: string
  verdict: 'pass' | 'fail' | 'outdated' | 'unverified' | 'note' | 'not_applicable'
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
interface FixCheck { label: string; ok: boolean | null; note: string }
interface FixCandidate { name: string; source_url: string; checks: FixCheck[]; passes: boolean }
export interface Fix { head: string; query: string; candidates: FixCandidate[]; suggest: string }
export type Value = string | number | string[] | null
// One comparison per finding. rows: currency findings, only the fields that changed.
export interface Compare {
  left_label: string; left_value: Value; right_label: string; right_value: Value
  verdict: 'fail' | 'pass' | 'changed'; rows: CompareRow[]
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
}

export interface Health { mode: 'mock' | 'live'; budget: { usd_left: number; credits_left: number } }
export async function getHealth(): Promise<Health> { return ok(await fetch('/api/health')) }

export async function getProject(): Promise<Project> {
  return (await fetch('/api/project')).json()
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
export async function scan(ids: string[], delayMs = 700): Promise<{ run_id: string; note?: string | null }> {
  return ok(await fetch('/api/scan', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ids, delay_ms: delayMs }),
  }))
}

export function streamEvents(runId: string, onEvent: (e: Event) => void, onEnd: () => void): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`)
  es.onmessage = (m) => onEvent(JSON.parse(m.data))
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
  return (await (await fetch(`/api/cases/${caseId}/text`)).json()).pages
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
