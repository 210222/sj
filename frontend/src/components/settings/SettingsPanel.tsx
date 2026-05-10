/** SettingsPanel — 快捷配置开关面板. */

import { useState, useEffect, useCallback } from 'react';
import { coachColors } from '../../styles/theme';

interface ConfigItem {
  key: string;
  label: string;
  description: string;
  group: string;
}

const CONFIG_ITEMS: ConfigItem[] = [
  { key: 'llm.enabled', label: 'AI 教练', description: '启用 DeepSeek 智能回复', group: 'LLM' },
  { key: 'llm.streaming', label: '流式输出', description: 'AI 回复逐字显示', group: 'LLM' },
  { key: 'ttm.enabled', label: '学习阶段检测', description: '自动判断你的学习阶段', group: '行为科学' },
  { key: 'sdt.enabled', label: '动机评估', description: '评估自主性/胜任感/关联性', group: '行为科学' },
  { key: 'flow.enabled', label: '心流调节', description: '动态调节学习难度', group: '行为科学' },
  { key: 'diagnostic_engine.enabled', label: '诊断引擎', description: '自动出诊断题评估掌握度', group: '诊断' },
  { key: 'counterfactual.enabled', label: '反事实仿真', description: '高风险动作模拟降级', group: '诊断' },
  { key: 'diagnostics.enabled', label: '因果实验', description: '实验诊断三件套', group: '诊断' },
  { key: 'mapek.enabled', label: 'MAPE-K 闭环', description: '自适应外循环控制', group: '自适应' },
  { key: 'mrt.enabled', label: '微随机实验', description: '教学策略 A/B 实验', group: '自适应' },
  { key: 'precedent_intercept.enabled', label: '先例拦截', description: '失败模式自动拦截', group: '安全' },
  { key: 'sovereignty_pulse.enabled', label: '主权脉冲', description: '高影响建议前确认', group: '安全' },
  { key: 'excursion.enabled', label: '探索模式', description: '支持 /excursion 自由探索', group: '安全' },
  { key: 'relational_safety.enabled', label: '关系安全', description: '过滤权威拟人语言', group: '安全' },
];

export function SettingsPanel() {
  const [config, setConfig] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/config')
      .then((r) => r.json())
      .then((d) => { setConfig(d.config || {}); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const toggle = useCallback(async (key: string, value: boolean) => {
    setConfig((c) => ({ ...c, [key]: value }));
    try {
      await fetch('/api/v1/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      });
    } catch {
      setConfig((c) => ({ ...c, [key]: !value })); // 回滚
    }
  }, []);

  const groups = [...new Set(CONFIG_ITEMS.map((i) => i.group))];

  if (loading) return <div style={{ padding: 20, color: coachColors.clayBrown }}>加载设置...</div>;

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      {groups.map((group) => (
        <div key={group} style={{ marginBottom: 'var(--space-xl)' }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: coachColors.deepMocha, marginBottom: 'var(--space-md)', borderBottom: `2px solid ${coachColors.lavenderGray}`, paddingBottom: 8 }}>
            {group}
          </h4>
          {CONFIG_ITEMS.filter((i) => i.group === group).map((item) => (
            <div key={item.key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: `1px solid ${coachColors.creamPaper}` }}>
              <div>
                <div style={{ fontSize: 14, color: coachColors.deepMocha }}>{item.label}</div>
                <div style={{ fontSize: 12, color: coachColors.clayBrown, marginTop: 2 }}>{item.description}</div>
              </div>
              <button
                onClick={() => toggle(item.key, !config[item.key])}
                style={{
                  width: 52, height: 28, borderRadius: 14, border: 'none',
                  background: config[item.key] ? coachColors.sageGreen : coachColors.lavenderGray,
                  position: 'relative', cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
              >
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', background: '#fff',
                  position: 'absolute', top: 3,
                  left: config[item.key] ? 27 : 3,
                  transition: 'left 0.2s ease',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                }} />
              </button>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
