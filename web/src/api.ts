// Types mirror api/schemas.py. Keep them in sync by hand (small surface).

export type Decision = 'approve' | 'approve_with_note' | 'send_back'
export type Stage =
  | 'queued' | 'ingest' | 'triage' | 'extract' | 'spec_check' | 'verify' | 'reconcile' | 'report' | 'done' | 'error'

export interface Case { id: string; title: string; section: string }
export interface Project { name: string; cases: Case[] }

export interface Event {
  run_id: string
  case_id: string | null
  t_ms: number
  stage: Stage
  message: string
  model: string | null
  data: Record<string, unknown> | null
}

export interface Evidence { url: string; tier: string; title: string; retrieved_at?: string; sha256?: string }
export interface Finding {
  id: string
  check: string
  verdict: 'pass' | 'fail' | 'outdated' | 'unverified' | 'note'
  severity: 'critical' | 'major' | 'minor' | 'info'
  title: string
  detail: string
  why_it_matters?: string | null
  spec_ref?: string | null
  requirement_id?: string | null
  claim_ids: string[]
  evidence: Evidence[]
  decided_by: string
}
export interface CompareRow { property: string; label: string; submitted: string | null; current: string | null; changed: boolean }
export interface Usage {
  task: string; tier: string; model: string; input_tokens: number; output_tokens: number; cost_usd: number; latency_ms: number
}
export interface Claim { id: string; property: string; value: unknown; unit?: string | null; page?: number | null; quote?: string | null }
export interface Result {
  case_id: string
  title: string
  decision: Decision
  summary: string
  findings: Finding[]
  comparison: CompareRow[]
  claims: Claim[]
  document_revision?: string | null
  document_source: 'pdf' | 'fixture'
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

export type Tone = 'red' | 'amber' | 'gray'
export interface Highlight { finding_id: string; claim_id: string; page: number; quote: string | null; tone: Tone; rects: number[][] }
export interface Page { page: number; image: boolean; text: string | null }
export interface Highlights { pages: Page[]; highlights: Highlight[] }

export async function getHighlights(runId: string, caseId: string): Promise<Highlights> {
  return (await fetch(`/api/runs/${runId}/results/${caseId}/highlights`)).json()
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
  approve_with_note: '#c98a1b',
  send_back: '#d9534f',
}
