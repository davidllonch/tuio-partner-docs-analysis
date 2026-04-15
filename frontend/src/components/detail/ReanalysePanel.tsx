import { useState, useEffect } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useReanalyse, useModels } from '../../hooks/useSubmissions'
import { useToast } from '../ui/Toast'
import type { ProviderType, Analysis } from '../../lib/types'
import { PROVIDER_TYPE_LABELS } from '../../lib/types'

interface ReanalysePanelProps {
  submissionId: string
  currentProviderType: ProviderType
  analyses: Analysis[]
}

const PROVIDER_TYPE_OPTIONS: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ReanalysePanel({
  submissionId,
  currentProviderType,
  analyses,
}: ReanalysePanelProps) {
  const [selectedType, setSelectedType] = useState<ProviderType>(currentProviderType)
  const [selectedModel, setSelectedModel] = useState<string>('')
  const { toast } = useToast()
  const { t } = useTranslation()
  const mutation = useReanalyse(submissionId)
  const { data: modelsData, isLoading: modelsLoading } = useModels()
  const models = modelsData?.models ?? []

  // Pre-select the first (most recent) model once the list loads
  useEffect(() => {
    if (models.length > 0 && !selectedModel) {
      setSelectedModel(models[0].id)
    }
  }, [models, selectedModel])

  const handleReanalyse = () => {
    mutation.mutate(
      {
        provider_type: selectedType,
        model: selectedModel || undefined,
      },
      {
        onSuccess: () => {
          toast({
            title: t('detail.reanalyseSuccess'),
            description: 'Email sent to david.llonch@tuio.com.',
            variant: 'success',
          })
        },
        onError: (error) => {
          const message =
            error instanceof Error ? error.message : 'Please try again.'
          toast({
            title: t('detail.errorReport'),
            description: message,
            variant: 'error',
          })
        },
      }
    )
  }

  return (
    <>
      {/* Re-analyse card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{t('detail.reanalyseTitle')}</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {t('detail.reanalyseHint')}
          </p>
        </div>

        <div className="p-5 space-y-4">
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2.5">
            <p className="text-xs text-gray-500">{t('detail.originalType')}</p>
            <p className="text-sm font-medium text-gray-800 mt-0.5">
              {PROVIDER_TYPE_LABELS[currentProviderType]}
            </p>
          </div>

          <div>
            <label
              htmlFor="reanalyse-type"
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              {t('detail.reanalyseType')}
            </label>
            <select
              id="reanalyse-type"
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value as ProviderType)}
              disabled={mutation.isPending}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-60"
            >
              {PROVIDER_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="reanalyse-model"
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              {t('detail.reanalyseModel')}
            </label>
            <select
              id="reanalyse-model"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={mutation.isPending || modelsLoading || models.length === 0}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-60"
            >
              {modelsLoading && (
                <option value="">{t('detail.loadingModels')}</option>
              )}
              {!modelsLoading && models.length === 0 && (
                <option value="">{t('detail.noModels')}</option>
              )}
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name || m.id}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleReanalyse}
            disabled={mutation.isPending || modelsLoading || models.length === 0}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t('detail.reanalyseRunning')}
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" />
                {t('detail.reanalyseAndSend')}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Analysis history card */}
      {analyses.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">{t('detail.analysisHistory')}</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {t('submission.table.date')}
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {t('submission.table.type')}
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {t('detail.triggeredBy')}
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {t('detail.reanalyseModel')}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {analyses.map((analysis) => (
                  <tr key={analysis.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2.5 text-gray-600 whitespace-nowrap">
                      {formatDate(analysis.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-gray-700 whitespace-nowrap">
                      {PROVIDER_TYPE_LABELS[analysis.provider_type]}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          analysis.triggered_by === 'analyst'
                            ? 'bg-primary-100 text-primary-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {analysis.triggered_by === 'analyst' ? t('detail.triggeredByAnalyst') : t('detail.triggeredByPartner')}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap font-mono">
                      {analysis.ai_model_used ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
