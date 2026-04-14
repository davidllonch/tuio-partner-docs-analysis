import { useTranslation } from 'react-i18next'

export function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const current = i18n.language

  const toggle = (lang: string) => {
    i18n.changeLanguage(lang)
    localStorage.setItem('lang', lang)
  }

  return (
    <div className="flex items-center gap-1 text-sm font-medium">
      <button
        onClick={() => toggle('es')}
        className={current === 'es' ? 'text-primary-600 font-semibold' : 'text-gray-400 hover:text-gray-600 transition-colors'}
      >
        ES
      </button>
      <span className="text-gray-300">|</span>
      <button
        onClick={() => toggle('en')}
        className={current === 'en' ? 'text-primary-600 font-semibold' : 'text-gray-400 hover:text-gray-600 transition-colors'}
      >
        EN
      </button>
    </div>
  )
}
