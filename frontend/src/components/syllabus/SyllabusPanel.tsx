/** SyllabusPanel — 课程大纲搜索 + 备课 + 确认 (Phase 86). */

import { useState, useEffect, useRef, useCallback } from 'react';
import { searchSyllabus, prepareChapter, getPrepStatus, confirmSyllabus } from '../../api/client';
import type { SyllabusSearchResponse, PrepStatusResponse } from '../../types/api';

interface Props {
  sessionId: string;
  isMobile: boolean;
  onClose: () => void;
}

const PREP_POLL_MS = 2000;
const PREP_TIMEOUT_MS = 5 * 60 * 1000;

const colors = {
  bg: '#f9f7f3',
  border: '#e0dcd0',
  text: '#3d3226',
  accent: '#7a9e7e',
  warn: '#d4a853',
  error: '#c97b6b',
  dim: '#8a8178',
  white: '#fff',
};

export function SyllabusPanel({ sessionId, isMobile, onClose }: Props) {
  const [syllabus, setSyllabus] = useState<SyllabusSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [subject, setSubject] = useState('');
  const [prepTasks, setPrepTasks] = useState<Record<string, PrepStatusResponse>>({});
  const [prepLoading, setPrepLoading] = useState<Record<string, boolean>>({});
  const [confirmState, setConfirmState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set(['ch1']));
  const prepPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── cleanup on unmount ──
  useEffect(() => {
    return () => {
      if (prepPollRef.current) clearInterval(prepPollRef.current);
    };
  }, []);

  // ── 搜索大纲 ──
  const handleSearch = useCallback(async () => {
    const q = subject.trim();
    if (!q) return;
    setSearching(true);
    setError(null);
    setSyllabus(null);
    // 保留 prepTasks — 新搜索不会冲突(旧 chapter_id 在新大纲中不存在则自然隐藏)
    try {
      const res = await searchSyllabus(q);
      setSyllabus(res);
      setExpandedChapters(new Set(['ch1']));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '搜索失败';
      setError(msg);
    }
    setSearching(false);
  }, [subject]);

  // ── 章节展开/折叠 ──
  const toggleChapter = (id: string) => {
    setExpandedChapters(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ── 开始备课 ──
  const handlePrepare = useCallback(async (chapter: Record<string, unknown>) => {
    const chId = chapter.id as string;
    if (!chId || prepTasks[chId]?.state === 'running') return;

    setPrepLoading(prev => ({ ...prev, [chId]: true }));
    setError(null);
    try {
      const res = await prepareChapter(chapter, subject, '编程语言');
      // 启动后立即拉一次状态
      const status = await getPrepStatus(res.task_id);
      setPrepTasks(prev => ({ ...prev, [chId]: status }));
      setPrepLoading(prev => ({ ...prev, [chId]: false }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '启动备课失败';
      setError(msg);
      setPrepLoading(prev => ({ ...prev, [chId]: false }));
    }
  }, [subject, prepTasks]);

  // ── 轮询备课进度 ──
  useEffect(() => {
    const runningTasks = Object.entries(prepTasks).filter(
      ([, t]) => t.state === 'running',
    );
    if (runningTasks.length === 0) {
      if (prepPollRef.current) clearInterval(prepPollRef.current);
      return;
    }

    prepPollRef.current = setInterval(async () => {
      const updates: Record<string, PrepStatusResponse> = {};
      for (const [chId, task] of runningTasks) {
        // 5min 超时
        const elapsed = Date.now() - (task.started_at ?? 0) * 1000;
        if (task.started_at && elapsed > PREP_TIMEOUT_MS) {
          updates[chId] = {
            ...task,
            state: 'error',
            error: '备课超时，请点击重新检查',
            kps: task.kps,
            result: task.result,
          } as PrepStatusResponse;
          continue;
        }
        try {
          const status = await getPrepStatus(task.task_id);
          updates[chId] = status;
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : '';
          if (msg.includes('NOT_FOUND') || msg.includes('No task found') || msg.includes('404')) {
            updates[chId] = {
              ...task,
              state: 'error',
              error: '任务已过期',
              kps: task.kps,
              result: task.result,
            } as PrepStatusResponse;
          }
          // transient error → skip this round
        }
      }
      if (Object.keys(updates).length > 0) {
        setPrepTasks(prev => ({ ...prev, ...updates }));
      }
    }, PREP_POLL_MS);

    return () => {
      if (prepPollRef.current) clearInterval(prepPollRef.current);
    };
  }, [prepTasks]);

  // ── 重新检查（超时恢复） ──
  const handleRecheck = async (chId: string) => {
    try {
      const task = prepTasks[chId];
      if (!task) return;
      const status = await getPrepStatus(task.task_id);
      setPrepTasks(prev => ({ ...prev, [chId]: status }));
    } catch {
      setError('重新检查失败');
    }
  };

  // ── 确认大纲 ──
  const handleConfirm = async () => {
    if (!syllabus || !sessionId) return;
    setConfirmState('loading');
    try {
      await confirmSyllabus(sessionId, syllabus.syllabus as unknown as Record<string, unknown>);
      setConfirmState('done');
      setTimeout(() => onClose(), 2000);
    } catch {
      setConfirmState('error');
    }
  };

  // ── 渲染 ──
  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.3)',
    zIndex: 100,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  const panelStyle: React.CSSProperties = {
    background: colors.white,
    borderRadius: isMobile ? 0 : 12,
    width: isMobile ? '100vw' : 600,
    height: isMobile ? '100vh' : '80vh',
    maxHeight: isMobile ? '100vh' : '80vh',
    display: 'flex', flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
  };

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={panelStyle}>
        {/* ── 标题栏 ── */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 16px', borderBottom: `1px solid ${colors.border}`,
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: colors.text }}>课程大纲</span>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 14, border: 'none',
            background: colors.bg, fontSize: 16, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: colors.text,
          }}>✕</button>
        </div>

        {/* ── 搜索栏 ── */}
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${colors.border}`, flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
              placeholder="输入学科名称，如 Python入门"
              disabled={searching}
              style={{
                flex: 1, padding: '8px 12px', fontSize: 14,
                border: `1px solid ${colors.border}`, borderRadius: 6,
                outline: 'none', color: colors.text,
              }}
            />
            <button onClick={handleSearch} disabled={searching || !subject.trim()} style={{
              padding: '8px 16px', fontSize: 14, cursor: 'pointer',
              background: colors.accent, color: colors.white, border: 'none',
              borderRadius: 6, opacity: searching ? 0.6 : 1,
            }}>
              {searching ? '搜索中...' : '搜索大纲'}
            </button>
          </div>
        </div>

        {/* ── 内容区 ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
          {error && (
            <div style={{
              padding: '8px 12px', marginBottom: 12, borderRadius: 6,
              background: '#fdf0ed', color: colors.error, fontSize: 13,
            }}>
              {error}
              <button onClick={() => setError(null)} style={{
                marginLeft: 8, background: 'none', border: 'none',
                color: colors.error, cursor: 'pointer', fontSize: 13,
                textDecoration: 'underline',
              }}>关闭</button>
            </div>
          )}

          {!syllabus && !searching && !error && (
            <div style={{ textAlign: 'center', padding: 48, color: colors.dim, fontSize: 14 }}>
              输入学科名称搜索课程大纲
            </div>
          )}

          {searching && (
            <div style={{ textAlign: 'center', padding: 48, color: colors.dim, fontSize: 14 }}>
              正在搜索...
            </div>
          )}

          {syllabus && (
            <>
              {/* needs_review 徽章 */}
              {syllabus.needs_review && (
                <div style={{
                  padding: '6px 12px', marginBottom: 12, borderRadius: 6,
                  background: '#fef9e7', color: colors.warn, fontSize: 13,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  ⚠ 模板生成，建议人工审核
                </div>
              )}

              {/* 课程信息 */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: colors.text }}>
                  {syllabus.syllabus.course_name}
                </div>
                <div style={{ fontSize: 12, color: colors.dim, marginTop: 2 }}>
                  {syllabus.syllabus.subject_category} · {syllabus.syllabus.total_chapters} 章
                </div>
              </div>

              {/* 章节列表 */}
              {syllabus.syllabus.chapters.length === 0 ? (
                <div style={{ color: colors.dim, fontSize: 13 }}>暂无章节</div>
              ) : (
                syllabus.syllabus.chapters.map((ch) => {
                  const isExpanded = expandedChapters.has(ch.id);
                  const prep = prepTasks[ch.id];
                  const loading = prepLoading[ch.id];
                  const isRunning = prep?.state === 'running';
                  const isDone = prep?.state === 'done';
                  const isPrepError = prep?.state === 'error';

                  return (
                    <div key={ch.id} style={{
                      marginBottom: 8, border: `1px solid ${colors.border}`,
                      borderRadius: 8, overflow: 'hidden',
                    }}>
                      {/* 章节标题 */}
                      <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 12px', background: isExpanded ? colors.bg : colors.white,
                        cursor: 'pointer',
                      }} onClick={() => toggleChapter(ch.id)}>
                        <span style={{ fontSize: 14, fontWeight: 500, color: colors.text }}>
                          {isExpanded ? '▼' : '▶'} {ch.title}
                        </span>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          {isRunning && (
                            <span style={{ fontSize: 11, color: colors.accent }}>
                              {Object.keys(prep?.kps ?? {}).length > 0
                                ? `备课中 (${Object.keys(prep.kps).length} 知识点)`
                                : '备课中...'}
                            </span>
                          )}
                          {isDone && (
                            <span style={{ fontSize: 11, color: colors.accent }}>✅ 已完成</span>
                          )}
                          {isPrepError && (
                            <span style={{ fontSize: 11, color: colors.error }}>
                              {prep?.error ? prep.error.slice(0, 20) : '备课失败'}
                            </span>
                          )}
                          {/* 备课按钮 */}
                          {syllabus && !isRunning && !isDone && (
                            <button onClick={(e) => {
                              e.stopPropagation();
                              handlePrepare(ch as unknown as Record<string, unknown>);
                            }} disabled={loading} style={{
                              padding: '4px 10px', fontSize: 12, cursor: 'pointer',
                              background: loading ? colors.dim : colors.accent,
                              color: colors.white, border: 'none', borderRadius: 4,
                            }}>
                              {loading ? '启动中...' : '备课'}
                            </button>
                          )}
                          {/* 超时恢复按钮 */}
                          {isPrepError && prep?.error?.includes('超时') && (
                            <button onClick={(e) => {
                              e.stopPropagation();
                              handleRecheck(ch.id);
                            }} style={{
                              padding: '4px 10px', fontSize: 12, cursor: 'pointer',
                              background: colors.warn, color: colors.white, border: 'none', borderRadius: 4,
                            }}>
                              重新检查
                            </button>
                          )}
                        </div>
                      </div>

                      {/* 节列表（展开时） */}
                      {isExpanded && ch.sections.map((sec, si) => (
                        <div key={`${ch.id}-s${si}`} style={{
                          padding: '8px 12px 8px 28px', borderTop: `1px solid ${colors.border}`,
                          fontSize: 13,
                        }}>
                          <div style={{ color: colors.text, fontWeight: 500 }}>{sec.title}</div>
                          {sec.knowledge_points.length > 0 ? (
                            <ul style={{ margin: '4px 0 0 0', paddingLeft: 16 }}>
                              {sec.knowledge_points.map((kp, ki) => (
                                <li key={ki} style={{ color: colors.dim, fontSize: 12, marginBottom: 2 }}>
                                  {kp}
                                  {prep?.kps?.[kp] && (
                                    <span style={{ marginLeft: 8, fontSize: 11, color: colors.accent }}>
                                      {prep.kps[kp]}
                                    </span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div style={{ color: colors.warn, fontSize: 11, marginTop: 2 }}>
                              {syllabus.needs_review ? '待人工填入知识点' : '暂无知识点'}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })
              )}
            </>
          )}
        </div>

        {/* ── 底部操作区 ── */}
        {syllabus && (
          <div style={{
            padding: '12px 16px', borderTop: `1px solid ${colors.border}`,
            display: 'flex', justifyContent: 'flex-end', gap: 8, flexShrink: 0,
          }}>
            {confirmState === 'done' ? (
              <span style={{ fontSize: 13, color: colors.accent }}>✅ 大纲已确认</span>
            ) : (
              <button onClick={handleConfirm} disabled={confirmState === 'loading'} style={{
                padding: '8px 20px', fontSize: 14, cursor: 'pointer',
                background: confirmState === 'error' ? colors.error : colors.accent,
                color: colors.white, border: 'none', borderRadius: 6,
                opacity: confirmState === 'loading' ? 0.6 : 1,
              }}>
                {confirmState === 'loading' ? '确认中...'
                  : confirmState === 'error' ? '重试确认'
                  : '确认大纲'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
