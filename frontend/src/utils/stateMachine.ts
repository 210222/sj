/** TTM 五阶段 → UI 组件精确映射表.

 * 设计文档第 1.1 节 — 行为科学驱动的界面转化策略.
 */
import type { TTMStage, TTMUIMapping } from '../types/coach';

export const TTM_UI_MAP: Record<TTMStage, TTMUIMapping> = {
  precontemplation: {
    theme: 'minimal',
    components: ['PassiveDashboard'],
    inputMode: 'suggest_only',
    pulseMode: 'disabled',
    description: '极简环境数据看板; 低频微轻推(Nudges); 客观信息图表',
  },
  contemplation: {
    theme: 'balanced',
    components: ['DecisionBalanceCard', 'SuccessStoryCarousel', 'BenefitProgressBar'],
    inputMode: 'reflect_first',
    pulseMode: 'gentle',
    description: '对比式Pros vs Cons决策平衡卡片; 用户故事轮播; 动态预估收益进度条',
  },
  preparation: {
    theme: 'active',
    components: ['GoalStepper', 'MicroHabitSchedule', 'CommitButton'],
    inputMode: 'scaffold',
    pulseMode: 'commitment',
    description: '交互式目标拆解向导(Stepper); 微习惯日程表; 一键承诺确认按钮',
  },
  action: {
    theme: 'energetic',
    components: ['ProgressRing', 'CelebrationEffect', 'OneClickCheckin'],
    inputMode: 'checkin',
    pulseMode: 'high_frequency',
    description: '动态发光进度环; 全屏撒花动效; 一键式学习签到',
  },
  maintenance: {
    theme: 'calm',
    components: ['StreakHeatmap', 'BadgeWall', 'AdvancedAdventureUnlock'],
    inputMode: 'explore',
    pulseMode: 'milestone',
    description: '连续打卡日历热力图; 数字成就徽章墙; 高阶探险解锁通知',
  },
  relapse: {
    theme: 'gentle',
    components: ['IcebreakerCareCard', 'TimeMachineButton'],
    inputMode: 'recover',
    pulseMode: 'none',
    description: '破冰式关怀对话卡片("重新开始是旅程的一部分"); 一键恢复历史进度时光机',
  },
};

export function getTTMUI(stage: TTMStage | null): TTMUIMapping {
  if (stage && stage in TTM_UI_MAP) {
    return TTM_UI_MAP[stage];
  }
  return TTM_UI_MAP.precontemplation;
}
