/** API 响应类型 */

export interface SessionResponse {
  session_id: string;
  token: string;
  ttm_stage: string | null;
  sdt_scores: Record<string, number> | null;
  created_at_utc: string;
}

export interface ChatResponse {
  action_type: string;
  payload: Record<string, unknown>;
  trace_id: string;
  intent: string;
  domain_passport: Record<string, unknown>;
  safety_allowed: boolean;
  gate_decision: string;
  audit_level: string;
  premise_rewrite_rate: number;
  ttm_stage: string | null;
  sdt_profile: Record<string, number> | null;
  flow_channel: string | null;
  pulse: PulseEvent | null;
  diagnostic_result: Record<string, unknown> | null;
  diagnostic_probe: Record<string, unknown> | null;
  // Phase 19-26: 教学元数据
  llm_generated?: boolean;
  llm_model?: string;
  llm_tokens?: number;
  personalization_evidence?: Record<string, unknown> | null;
  memory_status?: Record<string, unknown> | null;
  difficulty_contract?: Record<string, unknown> | null;
  awakening?: Record<string, unknown> | null;
  // Phase 36: LLM observability
  llm_observability?: LLMObservability | null;
  // Phase 41: returning user
  is_returning_user?: boolean;
}

export interface CacheObservability {
  cache_eligible: boolean;
  cache_eligibility_reason: string;
  stable_prefix_hash: string;
  stable_prefix_chars: number;
  stable_prefix_share: number;
  prefix_shape_version: string;
}

export interface RuntimeObservability {
  path: string;
  streaming: boolean;
  latency_ms: number;
  tokens_total: number;
  tokens_prompt: number | null;
  tokens_completion: number | null;
  token_usage_available: boolean;
  prompt_cache_hit_tokens: number | null;
  prompt_cache_miss_tokens: number | null;
  cost_usd: number | null;
  transport_status: string;
  finish_reason: string;
}

export interface LLMObservability {
  cache: CacheObservability;
  runtime: RuntimeObservability;
  retention?: Record<string, unknown>;
}

export interface LLMRuntimeSummary {
  sample_size: number;
  path_distribution: Record<string, number>;
  cache_eligible_rate: number;
  transport_status_distribution: Record<string, number>;
  avg_latency_ms?: number;
  p50_latency_ms?: number;
  p95_latency_ms?: number;
  p99_latency_ms?: number;
  max_latency_ms?: number;
  avg_tokens_total?: number;
  avg_stable_prefix_share?: number;
}

export interface SessionLLMSummary {
  session_id: string;
  total_calls: number;
  cache_eligible_rate: number;
  avg_latency_ms: number;
  avg_tokens: number;
  first_call_utc: string | null;
  last_call_utc: string | null;
}

export interface PulseEvent {
  pulse_id: string;
  statement: string;
  accept_label: string;
  rewrite_label: string;
  blocking_mode: 'hard' | 'soft' | 'none';
}

export interface PulseRespondResponse {
  status: string;
  next_action: Record<string, unknown> | null;
  blocking_mode: string;
}

export interface ExcursionEnterResponse {
  status: string;
  excursion_id: string;
  theme: string;
}

export interface TTMRadarData {
  precontemplation: number;
  contemplation: number;
  preparation: number;
  action: number;
  maintenance: number;
  current_stage: string;
}

export interface SDTRingsData {
  autonomy: number;
  competence: number;
  relatedness: number;
}

export interface ProgressData {
  total_sessions: number;
  total_turns: number;
  no_assist_avg: number | null;
  last_active_utc: string | null;
}

export interface UserDashboardResponse {
  session_id: string;
  ttm_radar: TTMRadarData;
  sdt_rings: SDTRingsData;
  progress: ProgressData;
  mastery_snapshot?: Record<string, unknown> | null;
  review_queue?: Array<Record<string, unknown>> | null;
  // Phase 36-37: LLM runtime
  llm_runtime_summary?: LLMRuntimeSummary | null;
  session_llm_summary?: SessionLLMSummary | null;
  // Phase 40: strategy quality
  strategy_quality?: Record<string, { effective_rate: number; n: number; structured_rate: number }> | null;
}

export interface GateStatusItem {
  id: number;
  name: string;
  status: 'pass' | 'warn' | 'block';
  metric: string;
  detail?: Record<string, unknown>;
}

export interface AdminGatesResponse {
  gates: GateStatusItem[];
  overall: 'pass' | 'warn' | 'block';
}

export interface AuditLogItem {
  event_id: string;
  timestamp_utc: string;
  severity: string;
  summary: string;
  trace_id?: string | null;
}

export interface AdminAuditResponse {
  logs: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp_utc: string;
}
