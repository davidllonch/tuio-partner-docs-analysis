import { useTranslation } from 'react-i18next'

export function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const current = i18n.language

  const toggle = (lang: string) => {
    i18n.changeLanguage(lang)
    localStorage.setItem('lang', lang)
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => toggle('es')}
        className={`text-sm font-medium transition-colors ${current === 'es' ? 'text-primary-600' : 'text-gray-400 hover:text-gray-600'}`}
      >
        Castellano
      </button>
      <span className="text-gray-300 text-sm">|</span>
      <button
        onClick={() => toggle('en')}
        className={`text-sm font-medium transition-colors ${current === 'en' ? 'text-primary-600' : 'text-gray-400 hover:text-gray-600'}`}
      >
        English
      </button>
    </div>
  )
}
