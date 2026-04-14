import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, LogOut, Calendar, MapPin, Building2, User } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSubmission } from '../hooks/useSubmissions'
import { useCurrentAnalyst, useLogout } from '../hooks/useAuth'
import { AIReportPanel } from '../components/detail/AIReportPanel'
import { DocumentDownloadList } from '../components/detail/DocumentDownloadList'
import { ReanalysePanel } from '../components/detail/ReanalysePanel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'
import { PROVIDER_TYPE_LABELS, ENTITY_TYPE_LABELS } from '../lib/types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: submission, isLoading, isError } = useSubmission(id!)
  const { data: analyst } = useCurrentAnalyst()
  const logout = useLogout()
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top navigation bar — same as dashboard */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <img src="/logo-tuio.png" alt="Tuio" className="h-8" />
            </div>

            <div className="flex items-center gap-4">
              <LanguageSwitcher />
              {analyst && (
                <span className="hidden sm:block text-sm text-gray-600">
                  {analyst.full_name}
                </span>
              )}
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

      {/* Sub-header: back link */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-primary-600 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            {t('detail.back')}
          </Link>
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {isError && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center max-w-md mx-auto">
            <p className="text-sm font-medium text-red-800">
              {t('dashboard.errorTitle')}
            </p>
            <p className="text-xs text-red-600 mt-1">
              {t('dashboard.errorSubtitle')}
            </p>
          </div>
        )}

        {submission && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left / main column */}
            <div className="lg:col-span-2 space-y-6">
              {/* Provider information card */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <h2 className="text-xl font-bold text-gray-900 leading-tight">
                    {submission.provider_name}
                  </h2>
                  <StatusBadge status={submission.status} />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Building2 className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span>{PROVIDER_TYPE_LABELS[submission.provider_type]}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <User className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span>{ENTITY_TYPE_LABELS[submission.entity_type]}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <MapPin className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span>{submission.country}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Calendar className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span>Submitted {formatDate(submission.created_at)}</span>
                  </div>
                </div>
              </div>

              {/* AI analysis report */}
              <AIReportPanel
                submissionId={submission.id}
                status={submission.status}
                aiResponse={submission.ai_response}
                errorMessage={submission.error_message}
                providerName={submission.provider_name}
              />
            </div>

            {/* Right / sidebar column */}
            <div className="space-y-6">
              {/* Documents */}
              <DocumentDownloadList
                submissionId={submission.id}
                documents={submission.documents}
              />

              {/* Re-analyse + history */}
              <ReanalysePanel
                submissionId={submission.id}
                currentProviderType={submission.provider_type}
                analyses={submission.analyses}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
