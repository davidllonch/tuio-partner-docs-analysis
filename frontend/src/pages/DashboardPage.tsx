import { useState } from 'react'
import { LogOut, RefreshCw, FileText } from 'lucide-react'
import { useSubmissions } from '../hooks/useSubmissions'
import { useCurrentAnalyst, useLogout } from '../hooks/useAuth'
import { SubmissionTable } from '../components/dashboard/SubmissionTable'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'

export function DashboardPage() {
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const { data, isLoading, isError, refetch, isFetching } = useSubmissions(page, PAGE_SIZE)
  const { data: analyst } = useCurrentAnalyst()
  const logout = useLogout()

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top navigation bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                <span className="text-white text-sm font-bold">T</span>
              </div>
              <h1 className="text-base font-semibold text-gray-900">KYC/KYB Review</h1>
            </div>

            <div className="flex items-center gap-4">
              {analyst && (
                <span className="hidden sm:block text-sm text-gray-600">
                  {analyst.full_name}
                </span>
              )}
              <button
                onClick={logout}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                aria-label="Log out"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Submissions</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              All partner documentation submissions, newest first
            </p>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Refresh submissions"
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
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
            <p className="text-sm font-medium text-red-800">Failed to load submissions</p>
            <p className="text-xs text-red-600 mt-1">
              Check your connection and try refreshing.
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Try again
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
