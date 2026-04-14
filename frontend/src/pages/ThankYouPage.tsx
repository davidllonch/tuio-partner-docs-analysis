import { useEffect, useState } from 'react'
import { CheckCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'

const REDIRECT_SECONDS = 5
const REDIRECT_URL = 'https://www.tuio.com'

export function ThankYouPage() {
  const [countdown, setCountdown] = useState(REDIRECT_SECONDS)
  const { t } = useTranslation()

  useEffect(() => {
    if (countdown <= 0) {
      window.location.replace(REDIRECT_URL)
      return
    }

    const timer = setTimeout(() => {
      setCountdown((prev) => prev - 1)
    }, 1000)

    return () => clearTimeout(timer)
  }, [countdown])

  return (
    <div className="relative min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-md text-center">
        {/* Success icon */}
        <div className="flex justify-center mb-6">
          <div className="h-20 w-20 rounded-full bg-green-100 flex items-center justify-center">
            <CheckCircle className="h-12 w-12 text-green-600" strokeWidth={1.5} />
          </div>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-3">{t('thankyou.title')}</h1>

        <p className="text-gray-600 text-base leading-relaxed">
          {t('thankyou.subtitle')}
        </p>

        <div className="mt-8 inline-flex items-center gap-2 text-sm text-gray-500 bg-white rounded-full px-5 py-2.5 border border-gray-200 shadow-sm">
          <span
            className="h-2 w-2 rounded-full bg-primary-500 animate-pulse"
            aria-hidden="true"
          />
          Redirecting to tuio.com in{' '}
          <span className="font-semibold text-gray-700 tabular-nums">{countdown}</span>
          {countdown === 1 ? ' second' : ' seconds'}…
        </div>

        <p className="mt-5 text-xs text-gray-400">
          Not redirected?{' '}
          <a
            href={REDIRECT_URL}
            className="text-primary-600 hover:text-primary-800 underline"
          >
            Click here
          </a>
        </p>
      </div>
    </div>
  )
}
