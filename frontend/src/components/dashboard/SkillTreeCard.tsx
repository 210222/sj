/** Phase 59: 学习地图 — 技能掌握度树形可视化. */
import { useState, useEffect } from 'react';
import { coachColors } from '../../styles/theme';

interface SkillNode {
  id: string;
  name: string;
  prerequisites: string[];
  related: string[];
  level: number;         // 掌握度 0-1
  isUnlocked: boolean;   // 前置全满足
  depth: number;         // 前置层级
}

const CONCEPT_NAMES: Record<string, string> = {
  python_variable: '变量', python_type: '类型', python_condition: '条件',
  python_loop: '循环', python_list: '列表', python_dict: '字典',
  python_tuple: '元组', python_function: '函数', python_comprehension: '推导式',
  python_generator: '生成器', python_class: '类', python_module: '模块',
  python_json: 'JSON', python_lambda: 'Lambda', python_decorator: '装饰器',
  python_recursion: '递归', algorithm_intro: '算法入门',
  sorting: '排序', searching: '搜索',
};

function cn(key: string): string { return CONCEPT_NAMES[key] || key; }

function calcDepth(key: string, graph: Record<string, {prerequisites: string[]}>, cache: Record<string,number>): number {
  if (cache[key] !== undefined) return cache[key];
  const prereqs = graph[key]?.prerequisites || [];
  if (prereqs.length === 0) { cache[key] = 0; return 0; }
  const d = 1 + Math.max(...prereqs.map(p => calcDepth(p, graph, cache)));
  cache[key] = d;
  return d;
}

interface Props {
  masterySnapshot?: Record<string, unknown> | null;
}

export function SkillTreeCard({ masterySnapshot }: Props) {
  const [graph, setGraph] = useState<Record<string, {prerequisites:string[];related:string[]}> | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch('/config/skill_graph.json')
      .then(r => r.json()).then(setGraph).catch(() => setError(true));
  }, []);

  if (error) return null;
  if (!graph) return null;

  const skills = (masterySnapshot as any)?.skills as Record<string, number> | undefined;
  const depthCache: Record<string, number> = {};
  const nodes: SkillNode[] = Object.keys(graph).map(key => ({
    id: key,
    name: cn(key),
    prerequisites: graph[key].prerequisites || [],
    related: graph[key].related || [],
    level: skills?.[key] ?? 0,
    isUnlocked: (graph[key].prerequisites || []).every(p => (skills?.[p] ?? 0) >= 0.6),
    depth: calcDepth(key, graph, depthCache),
  }));
  nodes.sort((a, b) => a.depth - b.depth || a.name.localeCompare(b.name));

  const hasData = skills && Object.keys(skills).length > 0;

  return (
    <div style={{
      background: 'linear-gradient(135deg, #f8f5f0 0%, #fdfaf5 100%)',
      border: `1px solid ${coachColors.lavenderGray}`,
      borderRadius: 10, padding: '12px 14px', marginBottom: 'var(--space-md)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, opacity: 0.7 }}>
        学习地图
      </div>
      {!hasData && (
        <div style={{ fontSize: 11, opacity: 0.4 }}>暂无学习记录。开始对话后自动更新。</div>
      )}
      {!hasData ? null : nodes.map(node => {
        let dotColor: string = coachColors.lavenderGray;
        let dotClass = 'locked';
        if (node.level >= 0.7) { dotColor = '#8a9f87'; dotClass = 'mastered'; }
        else if (node.level >= 0.3) { dotColor = '#c9a04a'; dotClass = 'learning'; }
        else if (!node.isUnlocked && hasData) { dotColor = '#e0dce8'; dotClass = 'prereq'; }
        return (
          <div key={node.id} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            marginLeft: `${node.depth * 16}px`,
            marginBottom: 3, padding: '3px 6px', borderRadius: 6,
            cursor: 'pointer', fontSize: 12,
          }}>
            <span style={{
              width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
              background: dotClass === 'prereq' ? 'transparent' : dotColor,
              border: dotClass === 'prereq' ? `2px dashed #c9a04a` : 'none',
            }} />
            <span style={{ flex: 1 }}>{node.name}</span>
            <span style={{ fontSize: 10, opacity: 0.4 }}>
              {node.level > 0 ? `${Math.round(node.level * 100)}%` : '--'}
            </span>
          </div>
        );
      })}
    </div>
  );
}
