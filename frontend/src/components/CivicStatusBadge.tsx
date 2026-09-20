import { useI18n } from '../lib/i18n'
import type { CivicStatus } from '../lib/types'

const STYLE: Record<CivicStatus, { bg: string; fg: string }> = {
  submitted: { bg: 'var(--color-brand-soft)', fg: 'var(--color-brand-ink)' },
  under_review: { bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)' },
  action_taken: { bg: 'var(--color-good-soft)', fg: 'var(--color-good)' },
  dismissed: { bg: 'var(--color-canvas)', fg: 'var(--color-ink-soft)' },
}

export function CivicStatusBadge({ status }: { status: CivicStatus }) {
  const { t } = useI18n()
  const style = STYLE[status]
  return (
    <span className="chip" style={{ background: style.bg, color: style.fg, borderColor: style.fg }}>
      {t(`civic.status.${status}` as never)}
    </span>
  )
}
