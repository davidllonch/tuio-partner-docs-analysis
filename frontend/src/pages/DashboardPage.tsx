import { useState } from 'react'
import { RefreshCw, FileText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSubmissions } from '../hooks/useSubmissions'
import { SubmissionTable } from '../components/dashboard/SubmissionTable'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { AnalystHeader } from '../components/layout/AnalystHeader'

export function DashboardPage() {
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20
  const { t } = useTranslation()

  const { data, isLoading, isError, refetch, isFetching } = useSubmissions(page, PAGE_SIZE)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AnalystHeader />

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

    </div>
  )
}
