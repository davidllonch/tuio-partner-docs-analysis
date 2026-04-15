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
        title="Español"
        className={`text-xl leading-none transition-opacity ${current === 'es' ? 'opacity-100' : 'opacity-40 hover:opacity-70'}`}
      >
        🇪🇸
      </button>
      <button
        onClick={() => toggle('en')}
        title="English"
        className={`text-xl leading-none transition-opacity ${current === 'en' ? 'opacity-100' : 'opacity-40 hover:opacity-70'}`}
      >
        🇬🇧
      </button>
    </div>
  )
}
