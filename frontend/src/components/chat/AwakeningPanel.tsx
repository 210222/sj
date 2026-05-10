/** AwakeningPanel — Phase 17 知情同意面板，推荐模块 + 高级模块分组展示 */

import { coachColors } from '../../styles/theme';

interface Capability {
  key: string;
  name: string;
  purpose: string;
  impact: string;
  risk: string;
  recommended: boolean;
}

interface AwakeningPanelProps {
  recommended: Capability[];
  advanced: Capability[];
  totalModules: number;
  hint: string;
  onEnableRecommended: () => void;
  onSkip: () => void;
}

export function AwakeningPanel({
  recommended,
  advanced,
  totalModules,
  hint,
  onEnableRecommended,
  onSkip,
}: AwakeningPanelProps) {
  const hasRecommended = recommended && recommended.length > 0;
  const hasAdvanced = advanced && advanced.length > 0;

  if (!hasRecommended && !hasAdvanced) return null;

  return (
    <div style={{
      margin: '16px',
      padding: '20px',
      borderRadius: '16px',
      background: `linear-gradient(135deg, ${coachColors.softBlue}22, ${coachColors.sageGreen}15)`,
      border: `1px solid ${coachColors.lavenderGray}`,
    }}>
      <h4 style={{ fontSize: 15, fontWeight: 600, color: coachColors.deepMocha, marginBottom: 4 }}>
        I have {totalModules} advanced capabilities you can enable
      </h4>

      {/* ── 推荐启用区 ── */}
      {hasRecommended && (
        <div style={{ marginTop: 12 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: coachColors.sageGreen,
            marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: coachColors.sageGreen,
            }} />
            推荐启用
          </div>
          <p style={{ fontSize: 11, color: coachColors.clayBrown, marginBottom: 10 }}>
            动机评估 + 学习阶段检测组合可显著提升个性化教学效果（S15 验证: +8.8%）
          </p>

          {recommended.map((cap) => (
            <div key={cap.key} style={{
              padding: '10px 14px', marginBottom: 8,
              borderRadius: 'var(--radius-md)',
              background: coachColors.warmWhite,
              border: `1px solid ${coachColors.sageGreen}40`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: coachColors.deepMocha }}>
                  {cap.name}
                </span>
                <span style={{
                  fontSize: 10, padding: '2px 8px', borderRadius: 10,
                  background: coachColors.sageGreen + '25',
                  color: coachColors.sageGreen, fontWeight: 600,
                }}>
                  RECOMMENDED
                </span>
              </div>
              <p style={{ fontSize: 11, color: coachColors.clayBrown, margin: '4px 0 0' }}>
                {cap.purpose}
              </p>
              <p style={{ fontSize: 10, color: coachColors.warmSand, margin: '2px 0 0' }}>
                {cap.impact}
              </p>
            </div>
          ))}

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              onClick={onEnableRecommended}
              style={{
                flex: 1, padding: '10px 16px', borderRadius: 'var(--radius-md)',
                background: coachColors.sageGreen, color: '#fff',
                border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}
            >
              启用推荐能力
            </button>
            <button
              onClick={onSkip}
              style={{
                padding: '10px 16px', borderRadius: 'var(--radius-md)',
                background: 'transparent', color: coachColors.clayBrown,
                border: `1px solid ${coachColors.lavenderGray}`,
                fontSize: 13, cursor: 'pointer',
              }}
            >
              跳过
            </button>
          </div>
        </div>
      )}

      {/* ── 高级能力区 ── */}
      {hasAdvanced && (
        <div style={{ marginTop: hasRecommended ? 18 : 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: coachColors.warmSand,
            marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: coachColors.warmSand,
            }} />
            高级能力
          </div>
          <p style={{ fontSize: 11, color: coachColors.clayBrown, marginBottom: 10 }}>
            这些能力适合进阶用户，可在设置面板中按需启用
          </p>

          {advanced.map((cap) => (
            <div key={cap.key} style={{
              padding: '10px 14px', marginBottom: 8,
              borderRadius: 'var(--radius-md)',
              background: coachColors.warmWhite,
              border: `1px solid ${coachColors.creamPaper}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: coachColors.deepMocha }}>
                  {cap.name}
                </span>
                <span style={{
                  fontSize: 10, padding: '2px 8px', borderRadius: 10,
                  background: cap.risk === '中' ? coachColors.sandalwoodMist :
                    cap.risk === '高' ? coachColors.coralCandy : coachColors.sageGreen + '30',
                  color: coachColors.deepMocha,
                }}>
                  {cap.risk === '高' ? 'advanced' : cap.risk === '中' ? 'moderate' : 'safe'}
                </span>
              </div>
              <p style={{ fontSize: 11, color: coachColors.clayBrown, margin: '4px 0 0' }}>
                {cap.purpose}
              </p>
            </div>
          ))}
        </div>
      )}

      <p style={{ fontSize: 10, color: coachColors.clayBrown, marginTop: 12, textAlign: 'center' }}>
        {hint}
      </p>
    </div>
  );
}
