import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LogOut, KeyRound, PlusCircle, Copy, Check, X, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useInvitations, useCreateInvitation, useCancelInvitation } from '../hooks/useInvitations'
import { useCurrentAnalyst, useLogout } from '../hooks/useAuth'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'
import { ChangePasswordModal } from '../components/ui/ChangePasswordModal'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { useToast } from '../components/ui/Toast'
import type { InvitationStatus, ProviderType, EntityType } from '../lib/types'

// ── Form schema ────────────────────────────────────────────────────────────────

const schema = z.object({
  provider_name: z.string().min(1).max(255),
  provider_type: z.enum([
    'correduria_seguros',
    'agencia_seguros',
    'colaborador_externo',
    'generador_leads',
  ]),
  entity_type: z.enum(['PJ', 'PF']),
  country: z.string().min(1).max(100),
})

type FormValues = z.infer<typeof schema>

const PROVIDER_TYPE_OPTIONS: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

// ── Status badge ───────────────────────────────────────────────────────────────

function InvitationBadge({ status }: { status: InvitationStatus }) {
  const { t } = useTranslation()
  const map: Record<InvitationStatus, string> = {
    pending: 'bg-amber-100 text-amber-700',
    submitted: 'bg-green-100 text-green-700',
    expired: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${map[status]}`}>
      {t(`invitations.status.${status}`)}
    </span>
  )
}

// ── Copy button ────────────────────────────────────────────────────────────────

function CopyButton({ url }: { url: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback — select the text manually
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-800 transition-colors"
      title={url}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? t('invitations.copied') : t('invitations.copyLink')}
    </button>
  )
}

// ── New invitation modal ───────────────────────────────────────────────────────

interface NewInvitationModalProps {
  onClose: () => void
}

function NewInvitationModal({ onClose }: NewInvitationModalProps) {
  const { t } = useTranslation()
  const { toast } = useToast()
  const createMutation = useCreateInvitation()
  const [createdUrl, setCreatedUrl] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { entity_type: 'PJ' },
  })

  const entityType = watch('entity_type')

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values as { provider_name: string; provider_type: ProviderType; entity_type: EntityType; country: string }, {
      onSuccess: (data) => {
        setCreatedUrl(data.invitation_url)
      },
      onError: () => {
        toast({
          title: t('invitations.createError'),
          variant: 'error',
        })
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {t('invitations.newInvitation')}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {createdUrl ? (
          /* Success state — show the URL */
          <div className="p-6 space-y-4">
            <p className="text-sm text-gray-700">{t('invitations.createdSuccess')}</p>
            <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 break-all text-xs text-gray-600 font-mono">
              {createdUrl}
            </div>
            <button
              onClick={async () => {
                await navigator.clipboard.writeText(createdUrl)
                toast({ title: t('invitations.copied'), variant: 'success' })
              }}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 transition-colors"
            >
              <Copy className="h-4 w-4" />
              {t('invitations.copyLink')}
            </button>
            <button
              onClick={onClose}
              className="w-full text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              {t('invitations.close')}
            </button>
          </div>
        ) : (
          /* Form state */
          <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
            {/* Provider name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('submit.providerName')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                placeholder={t('submit.providerNamePlaceholder')}
                className={`w-full rounded-lg border px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${errors.provider_name ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
                {...register('provider_name')}
              />
            </div>

            {/* Provider type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('submit.providerType')} <span className="text-red-500">*</span>
              </label>
              <select
                className={`w-full rounded-lg border px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${errors.provider_type ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
                {...register('provider_type')}
              >
                <option value="">{t('submit.selectProviderType')}</option>
                {PROVIDER_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Entity type */}
            <div>
              <span className="block text-sm font-medium text-gray-700 mb-2">
                {t('submit.entityType')} <span className="text-red-500">*</span>
              </span>
              <div className="grid grid-cols-2 gap-3">
                {([
                  { value: 'PJ', label: t('submit.entityPJ'), desc: t('submit.entityPJDesc') },
                  { value: 'PF', label: t('submit.entityPF'), desc: t('submit.entityPFDesc') },
                ] as const).map((opt) => {
                  const isSelected = entityType === opt.value
                  return (
                    <label
                      key={opt.value}
                      className={`relative flex cursor-pointer rounded-lg border p-3 transition-colors ${isSelected ? 'border-primary-600 bg-primary-50' : 'border-gray-200 bg-white hover:border-gray-300'}`}
                    >
                      <input type="radio" value={opt.value} className="sr-only" {...register('entity_type')} />
                      <div>
                        <p className={`text-sm font-medium ${isSelected ? 'text-primary-900' : 'text-gray-900'}`}>{opt.label}</p>
                        <p className={`text-xs mt-0.5 ${isSelected ? 'text-primary-600' : 'text-gray-500'}`}>{opt.desc}</p>
                      </div>
                    </label>
                  )
                })}
              </div>
            </div>

            {/* Country */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('submit.country')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                placeholder={t('submit.countryPlaceholder')}
                className={`w-full rounded-lg border px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${errors.country ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
                {...register('country')}
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {t('invitations.cancelButton')}
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 transition-colors disabled:opacity-60"
              >
                {createMutation.isPending ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  t('invitations.createButton')
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function InvitationsPage() {
  const { t } = useTranslation()
  const { data: analyst } = useCurrentAnalyst()
  const logout = useLogout()
  const { toast } = useToast()
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const { data, isLoading } = useInvitations({
    status_filter: statusFilter || undefined,
    page,
    size: PAGE_SIZE,
  })

  const cancelMutation = useCancelInvitation()

  const handleCancel = (id: string, providerName: string) => {
    if (!confirm(t('invitations.confirmCancel', { name: providerName }))) return
    cancelMutation.mutate(id, {
      onSuccess: () => {
        toast({ title: t('invitations.cancelSuccess'), variant: 'success' })
      },
      onError: () => {
        toast({ title: t('invitations.cancelError'), variant: 'error' })
      },
    })
  }

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
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {t('nav.submissions')}
                </Link>
                <Link
                  to="/invitations"
                  className="px-3 py-1.5 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg"
                >
                  {t('nav.invitations')}
                </Link>
                <Link
                  to="/team"
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {t('nav.team')}
                </Link>
                <Link
                  to="/declaration-templates"
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {t('nav.declarationTemplates')}
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
        <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{t('invitations.title')}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{t('invitations.subtitle')}</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">{t('invitations.filterAll')}</option>
              <option value="pending">{t('invitations.status.pending')}</option>
              <option value="submitted">{t('invitations.status.submitted')}</option>
              <option value="expired">{t('invitations.status.expired')}</option>
            </select>

            <button
              onClick={() => setShowNewModal(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition-colors"
            >
              <PlusCircle className="h-4 w-4" />
              {t('invitations.newInvitation')}
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {data && !isLoading && (
          <>
            {data.items.length === 0 ? (
              <div className="text-center py-20 text-sm text-gray-400">
                {t('invitations.empty')}
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50">
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                          {t('submission.table.provider')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                          {t('submission.table.type')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden md:table-cell">
                          {t('submission.table.entity')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                          {t('submission.table.country')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                          {t('submission.table.status')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                          {t('invitations.createdBy')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden md:table-cell">
                          {t('invitations.expiresOn')}
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                          {t('invitations.actions')}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {data.items.map((inv) => (
                        <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                            {inv.provider_name}
                          </td>
                          <td className="px-4 py-3 text-gray-600 whitespace-nowrap hidden sm:table-cell text-xs">
                            {inv.provider_type.replace(/_/g, ' ')}
                          </td>
                          <td className="px-4 py-3 text-gray-600 whitespace-nowrap hidden md:table-cell">
                            {inv.entity_type}
                          </td>
                          <td className="px-4 py-3 text-gray-600 whitespace-nowrap hidden lg:table-cell">
                            {inv.country}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <InvitationBadge status={inv.status} />
                          </td>
                          <td className="px-4 py-3 text-gray-500 whitespace-nowrap hidden sm:table-cell text-xs">
                            {inv.created_by_analyst?.full_name ?? '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-500 whitespace-nowrap hidden md:table-cell text-xs">
                            {formatDate(inv.expires_at)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-right">
                            <div className="flex items-center justify-end gap-3">
                              {inv.status === 'pending' && (
                                <>
                                  <CopyButton
                                    url={`${window.location.origin}/invite/${inv.token}`}
                                  />
                                  <button
                                    onClick={() => handleCancel(inv.id, inv.provider_name)}
                                    disabled={cancelMutation.isPending}
                                    className="inline-flex items-center gap-1 text-xs font-medium text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                                  >
                                    <X className="h-3.5 w-3.5" />
                                    {t('invitations.cancel')}
                                  </button>
                                </>
                              )}
                              {inv.status === 'submitted' && inv.submission_id && (
                                <Link
                                  to={`/submissions/${inv.submission_id}`}
                                  className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-800 transition-colors"
                                >
                                  <ExternalLink className="h-3.5 w-3.5" />
                                  {t('invitations.viewSubmission')}
                                </Link>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {data.total > PAGE_SIZE && (
                  <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
                    <span>
                      {t('submission.pagination.showing')} {(page - 1) * PAGE_SIZE + 1}–
                      {Math.min(page * PAGE_SIZE, data.total)} {t('submission.pagination.of')} {data.total}
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50 disabled:opacity-40"
                      >
                        {t('submission.pagination.previous')}
                      </button>
                      <button
                        onClick={() => setPage((p) => p + 1)}
                        disabled={page * PAGE_SIZE >= data.total}
                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50 disabled:opacity-40"
                      >
                        {t('submission.pagination.next')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      {showPasswordModal && <ChangePasswordModal onClose={() => setShowPasswordModal(false)} />}
      {showNewModal && <NewInvitationModal onClose={() => setShowNewModal(false)} />}
    </div>
  )
}
