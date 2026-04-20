import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'

export function LandingPage() {
  const { t } = useTranslation()
  return (
    <div className="relative min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm text-center">
        <img src="/logo-tuio.png" alt="Tuio" className="h-14 mx-auto mb-6" />
        <h1 className="text-2xl font-bold text-gray-900">{t('landing.title')}</h1>
        <p className="text-sm text-gray-500 mt-2 leading-relaxed">{t('landing.subtitle')}</p>
        <div className="mt-8">
          <Link
            to="/login"
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 transition-colors"
          >
            {t('landing.analystAccess')}
          </Link>
        </div>
      </div>
    </div>
  )
}
