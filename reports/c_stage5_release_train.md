# C5 Release Train

- **Stage**: C5
- **Status**: GO
- **Time (UTC)**: 2026-05-02T10:42:26.768401+00:00

## Train Governance
- Cadence: biweekly (Wednesday)
- Freeze window: 48h pre-release, 2h post-release
- Exception policy: max 7-day validity, project_owner approval
- Rollback: outer_A_v1.0.0_frozen / outer_B_v1.0.0_frozen

## Intake Rules
| Tier | Min Gates | Recommended | Tests | Approval |
|------|-----------|-------------|-------|----------|
| P0 | release + health + rollback | — | full 698 | project_owner |
| P1 | release + health | rollback | outer 29+ | project_owner |
| P2 | release | healthcheck | smoke 12+ | auto |

## Final Decision: GO
