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
