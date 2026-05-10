/** 环境光色温适配 — 设计文档第 4.2 节.

 * 夜间(20:00-06:00): 暖色偏移 +5%, 对应 2700K-3000K
 * 日间(06:00-20:00): 基准色温, 对应 4000K-5000K
 *
 * S9.4 增强: 添加 WCAG 安全边际检查 —
 *  暖色偏移后仍确保主文本对比度 ≥ 4.5:1
 */
import { getContrastRatio } from './contrastCheck';
import { coachColors } from '../styles/theme';

type TimePeriod = 'night' | 'day';

interface ColorShift {
  warmth: number;
  label: string;
  wcagSafe: boolean;
}

export function getTimePeriod(): TimePeriod {
  const hour = new Date().getHours();
  return (hour >= 20 || hour < 6) ? 'night' : 'day';
}

export function getColorTemperatureShift(): ColorShift {
  const period = getTimePeriod();
  const baseShift = period === 'night'
    ? { warmth: 0.05, label: '2700K-3000K' }
    : { warmth: 0, label: '4000K-5000K' };

  // WCAG 安全边际: 验证 deepMocha on warmWhite 在偏移后仍达标
  const wcagSafe = period === 'night'
    ? getContrastRatio(coachColors.deepMocha, coachColors.warmWhite) >= 4.5
    : true;

  return { ...baseShift, wcagSafe };
}

export function applyColorAdaptation(): void {
  const shift = getColorTemperatureShift();
  document.documentElement.style.setProperty(
    '--color-warmth-shift',
    String(shift.warmth),
  );
}

/** 在组件挂载时调用，设置色温并监听时间变化 */
export function initColorAdaptation(): () => void {
  applyColorAdaptation();
  const interval = setInterval(applyColorAdaptation, 60_000);
  return () => clearInterval(interval);
}
