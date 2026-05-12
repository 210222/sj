import type { PulseEvent } from './api';

/** 教练引擎类型 */

export type TTMStage =
  | 'precontemplation'
  | 'contemplation'
  | 'preparation'
  | 'action'
  | 'maintenance'
  | 'relapse';

export type ActionType =
  | 'challenge'
  | 'probe'
  | 'scaffold'
  | 'reflect'
  | 'suggest'
  | 'defer'
  | 'pulse'
  | 'excursion'
  | 'awakening';

export type BlockingMode = 'hard' | 'soft' | 'none';

export type ThemeMode = 'minimal' | 'balanced' | 'active' | 'energetic' | 'calm' | 'gentle';

export type InputMode = 'suggest_only' | 'reflect_first' | 'scaffold' | 'checkin' | 'explore' | 'recover';

export type PulseMode = 'disabled' | 'gentle' | 'commitment' | 'high_frequency' | 'milestone' | 'none';

export interface TTMUIMapping {
  theme: ThemeMode;
  components: string[];
  inputMode: InputMode;
  pulseMode: PulseMode;
  description: string;
}

export interface CoachState {
  sessionId: string;
  token: string;
  ttmStage: TTMStage | null;
  sdtProfile: Record<string, number> | null;
  flowChannel: string | null;
  messages: ChatMessage[];
  pulseCount: number;
  blockingMode: BlockingMode;
  excursionActive: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'coach';
  content: string;
  actionType?: ActionType;
  sourceTag?: 'rule' | 'statistical' | 'hypothesis';
  timestamp: string;
  // Phase 19-26: 教学元数据 (展示用)
  llm_generated?: boolean;
  difficulty_contract?: Record<string, unknown>;
  personalization_evidence?: Record<string, unknown> | null;
  memory_status?: Record<string, unknown> | null;
  options?: Array<{ label: string; description: string }>;
  pulse?: PulseEvent;
  awakening?: {
    triggered: boolean;
    total_modules: number;
    recommended: Array<{
      key: string;
      name: string;
      purpose: string;
      impact: string;
      risk: string;
      recommended: boolean;
    }>;
    advanced: Array<{
      key: string;
      name: string;
      purpose: string;
      impact: string;
      risk: string;
      recommended: boolean;
    }>;
    hint: string;
  };
}
