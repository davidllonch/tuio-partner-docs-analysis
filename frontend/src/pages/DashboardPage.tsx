import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LogOut, RefreshCw, FileText, KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSubmissions } from '../hooks/useSubmissions'
import { useCurrentAnalyst, useLogout } from '../hooks/useAuth'
import { SubmissionTable } from '../components/dashboard/SubmissionTable'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { ChangePasswordModal } from '../components/ui/ChangePasswordModal'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'

export function DashboardPage() {
  const [page, setPage] = useState(1)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const PAGE_SIZE = 20
  const { t } = useTranslation()

  const { data, isLoading, isError, refetch, isFetching } = useSubmissions(page, PAGE_SIZE)
  const { data: analyst } = useCurrentAnalyst()
  const logout = useLogout()

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top navigation bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <img src="/logo-tuio.png" alt="Tuio" className="h-8" />
              </div>
              <nav className="hidden sm:flex items-center gap-1">
                <Link
                  to="/dashboard"
                  className="px-3 py-1.5 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg"
                >
                  {t('nav.submissions')}
                </Link>
                <Link
                  to="/invitations"
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {t('nav.invitations')}
                </Link>
                <Link
                  to="/team"
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {t('nav.team')}
                </Link>
              </nav>
            </div>

            <div className="flex items-center gap-3">
              <LanguageSwitcher />
              {analyst && (
                <span className="hidden sm:block text-sm text-gray-600">
                  {analyst.full_name}
                </span>
              )}
              <button
                onClick={() => setShowPasswordModal(true)}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                aria-label={t('auth.changePassword')}
              >
                <KeyRound className="h-4 w-4" />
                <span className="hidden sm:inline">{t('auth.changePassword')}</span>
              </button>
              <button
                onClick={logout}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                aria-label={t('auth.logout')}
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">{t('auth.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{t('dashboard.title')}</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {t('dashboard.subtitle')}
            </p>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label={t('dashboard.refresh')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            {t('dashboard.refresh')}
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {isError && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
            <FileText className="h-10 w-10 text-red-400 mx-auto mb-3" />
            <p className="text-sm font-medium text-red-800">{t('dashboard.errorTitle')}</p>
            <p className="text-xs text-red-600 mt-1">
              {t('dashboard.errorSubtitle')}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              {t('dashboard.tryAgain')}
            </button>
          </div>
        )}

        {data && !isLoading && (
          <SubmissionTable
            items={data.items}
            total={data.total}
            page={page}
            size={PAGE_SIZE}
            onPageChange={setPage}
          />
        )}
      </main>

      {showPasswordModal && (
        <ChangePasswordModal onClose={() => setShowPasswordModal(false)} />
      )}
    </div>
  )
}
