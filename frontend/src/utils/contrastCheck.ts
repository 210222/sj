/** WCAG AA 对比度计算器 + 调色板审计.

 * 设计文档第 4.2 节 — 无障碍要求:
 * - 正常文本: 对比度 ≥ 4.5:1
 * - 大文本 (≥18px bold 或 ≥24px): 对比度 ≥ 3:1
 * - UI 组件: 对比度 ≥ 3:1
 */

/** 解析 Hex → sRGB 0-255 */
export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace(/^#/, '');
  if (h.length === 3) {
    return [
      parseInt(h[0] + h[0], 16),
      parseInt(h[1] + h[1], 16),
      parseInt(h[2] + h[2], 16),
    ];
  }
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

/** sRGB 线性化 */
function linearize(channel: number): number {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** WCAG 2.1 相对亮度 */
export function relativeLuminance(r: number, g: number, b: number): number {
  return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b);
}

/** 计算两个 Hex 颜色之间的对比度 */
export function getContrastRatio(hex1: string, hex2: string): number {
  const [r1, g1, b1] = hexToRgb(hex1);
  const [r2, g2, b2] = hexToRgb(hex2);
  const l1 = relativeLuminance(r1, g1, b1);
  const l2 = relativeLuminance(r2, g2, b2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/** 验证 WCAG AA 合规 */
export function checkWCAG_AA(
  fg: string,
  bg: string,
  isLargeText = false,
): { pass: boolean; ratio: number; required: number } {
  const ratio = getContrastRatio(fg, bg);
  const required = isLargeText ? 3.0 : 4.5;
  return { pass: ratio >= required, ratio, required };
}

export interface ContrastReport {
  fgName: string;
  bgName: string;
  fgHex: string;
  bgHex: string;
  ratio: number;
  passNormal: boolean;
  passLarge: boolean;
}

/** 自动扫描调色板全部色彩组合并输出审计报告 */
export function auditColorPalette(
  palette: Record<string, string>,
): ContrastReport[] {
  const entries = Object.entries(palette);
  const results: ContrastReport[] = [];

  for (const [fgName, fgHex] of entries) {
    for (const [bgName, bgHex] of entries) {
      if (fgName === bgName) continue;
      const ratio = getContrastRatio(fgHex, bgHex);
      results.push({
        fgName,
        bgName,
        fgHex,
        bgHex,
        ratio: Math.round(ratio * 100) / 100,
        passNormal: ratio >= 4.5,
        passLarge: ratio >= 3.0,
      });
    }
  }
  return results;
}
