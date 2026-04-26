import { useState } from 'react'
import { UserPlus, Loader2, Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAnalysts, useCreateAnalyst } from '../hooks/useAnalysts'
import { useCurrentAnalyst } from '../hooks/useAuth'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { useToast } from '../components/ui/Toast'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import axios from 'axios'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function TeamPage() {
  const { data: analysts, isLoading, isError } = useAnalysts()
  const { data: currentAnalyst } = useCurrentAnalyst()
  const createMutation = useCreateAnalyst()
  const { toast } = useToast()
  const { t } = useTranslation()

  const [showAddForm, setShowAddForm] = useState(false)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    createMutation.mutate(
      { email, full_name: fullName, password },
      {
        onSuccess: () => {
          toast({ title: 'Analyst added', description: `${email} can now log in.`, variant: 'success' })
          setEmail('')
          setFullName('')
          setPassword('')
          setShowAddForm(false)
        },
        onError: (error) => {
          setPassword('')
          if (axios.isAxiosError(error) && error.response?.status === 409) {
            setFormError(t('team.errorDuplicate'))
          } else {
            setFormError(t('team.errorGeneric'))
          }
        },
      }
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AnalystHeader />

      {/* Main content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{t('team.title')}</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {t('team.subtitle')}
            </p>
          </div>
          {currentAnalyst?.is_admin && (
            <button
              onClick={() => { setShowAddForm((v) => !v); setFormError(null) }}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 transition-colors"
            >
              <UserPlus className="h-4 w-4" />
              {t('team.addAnalyst')}
            </button>
          )}
        </div>

        {/* Add analyst form */}
        {showAddForm && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">New analyst</h3>
            <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">{t('team.fullName')}</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  placeholder="Anna García"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">{t('team.email')}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="anna@tuio.com"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('team.password')} <span className="text-gray-400">(min. 8 chars)</span>
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              {formError && (
                <p className="sm:col-span-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {formError}
                </p>
              )}

              <div className="sm:col-span-3 flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => { setShowAddForm(false); setFormError(null); setPassword('') }}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  {t('team.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition-colors disabled:opacity-60"
                >
                  {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  {createMutation.isPending ? t('team.creating') : t('team.create')}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Analysts table */}
        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {isError && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
            <p className="text-sm font-medium text-red-800">{t('dashboard.errorTitle')}</p>
          </div>
        )}

        {analysts && analysts.length === 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-12 text-center">
            <Users className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">{t('dashboard.noSubmissions')}</p>
          </div>
        )}

        {analysts && analysts.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('team.name')}</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('team.email')}</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('team.joined')}</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('team.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {analysts.map((analyst) => (
                  <tr key={analyst.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 font-medium text-gray-900 whitespace-nowrap">
                      {analyst.full_name ?? '—'}
                      {analyst.email === currentAnalyst?.email && (
                        <span className="ml-2 text-xs text-primary-600 font-normal">({t('team.you')})</span>
                      )}
                      {analyst.is_admin && (
                        <span className="ml-2 inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                          {t('team.admin')}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-600 whitespace-nowrap">{analyst.email}</td>
                    <td className="px-5 py-3 text-gray-500 whitespace-nowrap">{formatDate(analyst.created_at)}</td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        analyst.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        {analyst.is_active ? t('team.active') : t('team.inactive')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

    </div>
  )
}
