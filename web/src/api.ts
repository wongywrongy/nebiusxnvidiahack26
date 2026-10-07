// Types mirror api/schemas.py. Keep them in sync by hand (small surface).

export type Decision = 'approve' | 'approve_with_note' | 'send_back'
export type Stage =
  | 'queued' | 'ingest' | 'triage' | 'extract' | 'spec_check' | 'verify' | 'fix' | 'report' | 'done' | 'error'

export interface Case {
  id: string; number?: string; title: string; product?: string; from?: string; section: string
  submittal: { file: string }[]; watch?: { approved: string }; upload?: boolean; mock_fixture?: string | null
}
export interface Project { name: string; cases: Case[]; specs: { section: string; owner: string }[] }

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
interface Usage {
  task: string; tier: string; model: string; input_tokens: number; output_tokens: number; cost_usd: number; latency_ms: number
}
interface Claim { id: string; property: string; value: unknown; unit?: string | null; page?: number | null; quote?: string | null }
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
}

export async function getProject(): Promise<Project> {
  return (await fetch('/api/project')).json()
}

export async function startRun(caseIds?: string[], delayMs = 700): Promise<string> {
  const r = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ case_ids: caseIds, delay_ms: delayMs }),
  })
  return (await r.json()).run_id
}

export function streamEvents(runId: string, onEvent: (e: Event) => void, onEnd: () => void): () => void {
  const es = new EventSource(`/api/runs/${runId}/events`)
  es.onmessage = (m) => onEvent(JSON.parse(m.data))
  es.addEventListener('end', () => { es.close(); onEnd() })
  return () => es.close()
}

export async function getResult(runId: string, caseId: string): Promise<Result> {
  return (await fetch(`/api/runs/${runId}/results/${caseId}`)).json()
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

/** Upload a PDF: it becomes a new item checked against the project specs, on its own run. */
export async function uploadPdf(file: File, delayMs = 700): Promise<{ run_id: string; case: Case }> {
  const r = await fetch(`/api/uploads?name=${encodeURIComponent(file.name)}&delay_ms=${delayMs}`, {
    method: 'POST', headers: { 'content-type': 'application/pdf' }, body: file,
  })
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Upload failed (${r.status})`)
  return r.json()
}

interface Ratio { n: number; of: number }
interface ScoreRow {
  id: string; title: string; product: string; expected: Decision; expected_problems: string[]; error?: boolean
  decision?: Decision; found_problems?: string[]; right_call?: boolean; caught?: number; false_alarm?: boolean
  fix?: { suggest: string | null; passes: boolean; candidates: number } | null
  time_ms?: number; cost_usd?: number; web_credits?: number
}
export interface Scores {
  generated_at: string; mode: string; run_id: string; models: Record<string, string>
  right_call: Ratio; caught: Ratio; false_alarms: Ratio; fixes_passing: Ratio
  time_ms_per_item: number; cost_usd_per_item: number; rows: ScoreRow[]
}

/** Server mode, and the newest recorded live run (null before scripts/record_live.py has run). */
export async function getHealth(): Promise<{ mode: string; recorded: string | null }> {
  return (await fetch('/api/health')).json()
}

/** Run all cases now and rewrite the scores (the Results page's "Run the scoring set"). */
export async function runScores(): Promise<Scores> {
  const r = await fetch('/api/scores/run', { method: 'POST' })
  if (!r.ok) throw new Error(`Scoring failed (${r.status})`)
  return r.json()
}

/** The answer-key scores from scripts/eval.py, or null before it has been run. */
export async function getScores(): Promise<Scores | null> {
  const r = await fetch('/api/scores')
  return r.ok ? r.json() : null
}

export async function startReplay(sourceRunId: string): Promise<string> {
  const r = await fetch('/api/runs/replay', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ source_run_id: sourceRunId }),
  })
  return (await r.json()).run_id
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
