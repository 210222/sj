/** 色彩系统 — 精确对照设计文档第 4.1 节 Hex 矩阵.

 * 6 主色 + 5 檀香辅助色，WCAG AA 合规。
 */
export const coachColors = {
  // 主背景/空间留白 — 替代纯白
  warmWhite: '#F5F1EA',       // 245,241,234

  // 主品牌色/系统组件
  softBlue: '#AFC7E2',        // 175,199,226 — AI气泡/导航/CTA

  // 探索模式/成功标记
  sageGreen: '#9CB59B',       // 156,181,155 — excursion/成功高亮

  // 次级界面/数据图表
  lavenderGray: '#C6C1D2',    // 198,193,210 — 次要填充/卡片投影

  // 主文本/高对比度
  deepMocha: '#6E5B4E',       // 110,91,78 — 替代纯黑字色

  // 高亮强调/警示缓和(替代纯红)
  coralCandy: '#FEDDD8',      // 254,221,216 — 柔性警告

  // 檀香薄雾辅助色(冥想/放松场景)
  sandalwoodMist: '#D8CBB8',
  creamPaper: '#F4EFE7',
  warmSand: '#B39A7C',
  clayBrown: '#8A7C70',
  charcoal: '#2F2C2A',
} as const;

export type CoachColorKey = keyof typeof coachColors;
export type CoachColorHex = (typeof coachColors)[CoachColorKey];

/** 语义色映射 */
export const semanticColors = {
  pass: coachColors.sageGreen,
  warn: coachColors.coralCandy,
  block: '#FF8A80',  // 柔和红 — 仅阻断用
  info: coachColors.softBlue,
  muted: coachColors.lavenderGray,
} as const;

/** TTM 阶段色 */
export const ttmStageColors: Record<string, string> = {
  precontemplation: coachColors.lavenderGray,
  contemplation: coachColors.softBlue,
  preparation: coachColors.sageGreen,
  action: coachColors.coralCandy,
  maintenance: coachColors.sandalwoodMist,
  relapse: coachColors.clayBrown,
} as const;
