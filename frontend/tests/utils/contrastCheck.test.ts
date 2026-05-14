import { describe, it, expect } from 'vitest';
import * as cc from '../../src/utils/contrastCheck';
import { coachColors } from '../../src/styles/theme';

describe('hexToRgb', () => {
  it('parses 6-digit hex', () => {
    expect(cc.hexToRgb('#F5F1EA')).toEqual([245, 241, 234]);
  });

  it('parses 3-digit hex', () => {
    expect(cc.hexToRgb('#FFF')).toEqual([255, 255, 255]);
  });

  it('parses without hash', () => {
    expect(cc.hexToRgb('000000')).toEqual([0, 0, 0]);
  });
});

describe('relativeLuminance', () => {
  it('white is ~1', () => {
    const lum = cc.relativeLuminance(255, 255, 255);
    expect(lum).toBeCloseTo(1.0, 1);
  });

  it('black is ~0', () => {
    const lum = cc.relativeLuminance(0, 0, 0);
    expect(lum).toBeCloseTo(0.0, 1);
  });
});

describe('WCAG AA compliance', () => {
  // 关键色彩对 — 设计文档第 4.2 节指定
  it('deepMocha on warmWhite passes normal text AA', () => {
    const result = cc.checkWCAG_AA(coachColors.deepMocha, coachColors.warmWhite);
    expect(result.pass).toBe(true);
    expect(result.ratio).toBeGreaterThanOrEqual(4.5);
  });

  it('deepMocha on warmWhite passes large text AA', () => {
    const result = cc.checkWCAG_AA(coachColors.deepMocha, coachColors.warmWhite, true);
    expect(result.pass).toBe(true);
    expect(result.ratio).toBeGreaterThanOrEqual(3.0);
  });

  // 验证实际 UI 文本-背景组合 — 设计文档采用柔和调色板
  // 部分组合通过大文本 AA (≥3:1) 但未达正常文本 AA (≥4.5:1)
  // 这是已知的"降低视觉疲劳"设计权衡
  it('deepMocha on softBlue bubble — passes large text AA (≥3:1)', () => {
    const ratio = cc.getContrastRatio(coachColors.deepMocha, coachColors.softBlue);
    expect(ratio).toBeGreaterThanOrEqual(3.0);
  });

  it('deepMocha on lavenderGray bubble — passes large text AA (≥3:1)', () => {
    const ratio = cc.getContrastRatio(coachColors.deepMocha, coachColors.lavenderGray);
    expect(ratio).toBeGreaterThanOrEqual(3.0);
  });

  it('deepMocha on sandalwoodMist — passes large text AA (≥3:1)', () => {
    const ratio = cc.getContrastRatio(coachColors.deepMocha, coachColors.sandalwoodMist);
    expect(ratio).toBeGreaterThanOrEqual(3.0);
  });

  it('charcoal on creamPaper — passes normal text AA', () => {
    const ratio = cc.getContrastRatio(coachColors.charcoal, coachColors.creamPaper);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it('charcoal on creamPaper has high contrast', () => {
    const ratio = cc.getContrastRatio(coachColors.charcoal, coachColors.creamPaper);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});

describe('auditColorPalette', () => {
  it('returns report for all color pairs', () => {
    const report = cc.auditColorPalette(coachColors as Record<string, string>);
    expect(report.length).toBeGreaterThan(0);
    // 每个结果都有必要字段
    for (const r of report) {
      expect(r.fgName).toBeDefined();
      expect(r.bgName).toBeDefined();
      expect(r.ratio).toBeGreaterThan(0);
      expect(typeof r.passNormal).toBe('boolean');
      expect(typeof r.passLarge).toBe('boolean');
    }
  });
});
