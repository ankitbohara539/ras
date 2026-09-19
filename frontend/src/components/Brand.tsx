import { Link } from 'react-router-dom'
import { Contrast, Languages } from 'lucide-react'
import { useI18n } from '../lib/i18n'
import { usePrefs } from '../lib/prefs'
import headerLogo from '../../assets/Compact/Header/Compact/Header.svg'
import iconLogo from '../../assets/Icon/Companions/Open path.svg'

export function Brand({ to = '/', compact = false }: { to?: string; compact?: boolean }) {
  const { t } = useI18n()
  return (
    <Link
      to={to}
      className="flex shrink-0 items-center"
      aria-label={t('app.name')}
    >
      <img
        src={compact ? iconLogo : headerLogo}
        alt=""
        aria-hidden="true"
        className={compact ? 'size-10' : 'h-10 w-auto max-w-[157px] sm:h-11 sm:max-w-[173px]'}
      />
    </Link>
  )
}

export function DisplayControls() {
  const { t, language, setLanguage } = useI18n()
  const { largeText, highContrast, setLargeText, setHighContrast } = usePrefs()
  return (
    <div
      className="flex flex-wrap items-center gap-1"
      role="group"
      aria-label={t('a11y.language')}
    >
      <button
        type="button"
        className="btn btn-ghost px-2"
        onClick={() => setLanguage(language === 'en' ? 'ne' : 'en')}
        aria-label={t('a11y.language')}
      >
        <Languages size={16} aria-hidden="true" />
        {language === 'en' ? 'नेपाली' : 'English'}
      </button>
      <button
        type="button"
        className="btn btn-ghost px-2"
        onClick={() => setLargeText(!largeText)}
        aria-pressed={largeText}
        aria-label={t('a11y.largeText')}
      >
        A+
      </button>
      <button
        type="button"
        className="btn btn-ghost px-2"
        onClick={() => setHighContrast(!highContrast)}
        aria-pressed={highContrast}
        aria-label={t('a11y.highContrast')}
      >
        <Contrast size={17} aria-hidden="true" />
      </button>
    </div>
  )
}
