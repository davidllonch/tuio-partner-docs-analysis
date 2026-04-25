import { useParams, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Calendar, MapPin, Building2, User, ClipboardList, FileSignature, Loader2, X, Download } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useSubmission } from '../hooks/useSubmissions'
import { AIReportPanel } from '../components/detail/AIReportPanel'
import { DocumentDownloadList } from '../components/detail/DocumentDownloadList'
import { ReanalysePanel } from '../components/detail/ReanalysePanel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import { useToast } from '../components/ui/Toast'
import { updateContractData, generateContractPdfFull, fetchContractPlaceholderContext, fetchSiNoFields } from '../lib/api'
import { PROVIDER_TYPE_LABELS, ENTITY_TYPE_LABELS } from '../lib/types'

const CONTRACT_PROVIDER_TYPES = ['colaborador_externo', 'generador_leads', 'correduria_seguros']

interface CommissionRow {
  producto: string
  prima: string
  comision_np: string
  comision_cartera: string
}

interface ContractFormState {
  actividad: string
  commissions: CommissionRow[]
  siNoFields: Record<string, string>  // { "Vida": "Sí", "Auto": "No" }
}

const EMPTY_ROW: CommissionRow = { producto: '', prima: '', comision_np: '', comision_cartera: '' }

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
  const { data: submission, isLoading, isError, refetch: refetchSubmission } = useSubmission(id!)
  const { t } = useTranslation()
  const { toast } = useToast()

  const [contractState, setContractState] = useState<ContractFormState>({
    actividad: '',
    commissions: [{ ...EMPTY_ROW }],
    siNoFields: {},
  })
  const [isSavingContract, setIsSavingContract] = useState(false)
  const [isDownloadingContract, setIsDownloadingContract] = useState(false)

  // Initialise contract form from saved data when submission loads or changes
  useEffect(() => {
    if (!submission) return
    if (submission.contract_data) {
      try {
        const parsed = JSON.parse(submission.contract_data)
        setContractState({
          actividad: parsed.fields?.actividad ?? '',
          commissions:
            Array.isArray(parsed.commissions) && parsed.commissions.length > 0
              ? parsed.commissions
              : [{ ...EMPTY_ROW }],
          siNoFields: parsed.si_no_fields ?? {},
        })
      } catch {
        setContractState({ actividad: '', commissions: [{ ...EMPTY_ROW }], siNoFields: {} })
      }
    } else {
      setContractState({ actividad: '', commissions: [{ ...EMPTY_ROW }], siNoFields: {} })
    }
  }, [submission?.contract_data])

  // Fetch the [ACTIVIDAD] context phrase and SI/NO fields from the template
  const { data: placeholderContextData } = useQuery({
    queryKey: ['contract-placeholder-context', submission?.provider_type, submission?.entity_type],
    queryFn: () => fetchContractPlaceholderContext(submission!.provider_type, submission!.entity_type),
    enabled: !!submission && CONTRACT_PROVIDER_TYPES.includes(submission.provider_type),
    staleTime: 60_000,
  })
  const actividadContext = placeholderContextData?.context?.ACTIVIDAD ?? null

  const { data: siNoFieldsData } = useQuery({
    queryKey: ['contract-si-no-fields', submission?.provider_type, submission?.entity_type],
    queryFn: () => fetchSiNoFields(submission!.provider_type, submission!.entity_type),
    enabled: !!submission && CONTRACT_PROVIDER_TYPES.includes(submission.provider_type),
    staleTime: 60_000,
  })
  const siNoProducts = siNoFieldsData?.fields ?? []

  const updateCommissionRow = (idx: number, field: keyof CommissionRow, value: string) => {
    setContractState((prev) => {
      const updated = prev.commissions.map((row, i) =>
        i === idx ? { ...row, [field]: value } : row
      )
      return { ...prev, commissions: updated }
    })
  }

  const addCommissionRow = () => {
    setContractState((prev) => ({
      ...prev,
      commissions: [...prev.commissions, { ...EMPTY_ROW }],
    }))
  }

  const removeCommissionRow = (idx: number) => {
    setContractState((prev) => ({
      ...prev,
      commissions: prev.commissions.filter((_, i) => i !== idx),
    }))
  }

  const handleSaveContractData = async () => {
    if (!submission) return
    setIsSavingContract(true)
    try {
      await updateContractData(submission.id, {
        fields: { actividad: contractState.actividad },
        commissions: contractState.commissions,
        si_no_fields: contractState.siNoFields,
      })
      toast({ title: t('detail.saveContractSuccess'), variant: 'success' })
    } catch {
      toast({ title: t('detail.saveContractError'), variant: 'error' })
    } finally {
      setIsSavingContract(false)
    }
  }

  const handleDownloadContractPdf = async () => {
    if (!submission) return
    setIsDownloadingContract(true)
    try {
      const partnerInfo = submission.partner_info ? JSON.parse(submission.partner_info) : {}
      const contractData = {
        fields: { actividad: contractState.actividad },
        commissions: contractState.commissions,
        si_no_fields: contractState.siNoFields,
      }
      const blob = await generateContractPdfFull(
        submission.provider_type,
        submission.entity_type,
        partnerInfo,
        contractData
      )
      const url = window.URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url
      anchor.download = 'contrato.pdf'
      window.document.body.appendChild(anchor)
      anchor.click()
      window.document.body.removeChild(anchor)
      window.URL.revokeObjectURL(url)
    } catch {
      // Silently fail — user can retry
    } finally {
      setIsDownloadingContract(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AnalystHeader />

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
                    <span>{t('detail.submitted')} {formatDate(submission.created_at)}</span>
                  </div>
                </div>
              </div>

              {/* Partner information card */}
              {submission.partner_info && (() => {
                let info: Record<string, string> = {}
                try { info = JSON.parse(submission.partner_info) } catch { return null }
                const isPJ = info.entity_type === 'PJ'
                const fields = isPJ
                  ? [
                      { key: 'razon_social', label: t('partnerInfo.razon_social') },
                      { key: 'cif', label: t('partnerInfo.cif') },
                      { key: 'domicilio_social', label: t('partnerInfo.domicilio_social') },
                      { key: 'nombre_representante', label: t('partnerInfo.nombre_representante') },
                      { key: 'nif_representante', label: t('partnerInfo.nif_representante') },
                    ]
                  : [
                      { key: 'nombre_apellidos', label: t('partnerInfo.nombre_apellidos') },
                      { key: 'nif', label: t('partnerInfo.nif') },
                      { key: 'domicilio', label: t('partnerInfo.domicilio') },
                    ]

                return (
                  <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <ClipboardList className="h-4 w-4 text-gray-400" />
                      <h3 className="text-sm font-semibold text-gray-700">{t('detail.partnerInfo')}</h3>
                    </div>
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
                      {fields.map(({ key, label }) => (
                        <div key={key}>
                          <dt className="text-xs text-gray-500">{label}</dt>
                          <dd className="mt-0.5 text-sm text-gray-900 font-medium">{info[key] || '—'}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )
              })()}

              {/* AI analysis report */}
              <AIReportPanel
                submissionId={submission.id}
                status={submission.status}
                aiResponse={submission.ai_response}
                errorMessage={submission.error_message}
                providerName={submission.provider_name}
              />

              {/* Contract management section — only for provider types that use contracts */}
              {CONTRACT_PROVIDER_TYPES.includes(submission.provider_type) && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
                  <div className="flex items-center gap-2 mb-5">
                    <FileSignature className="h-4 w-4 text-gray-400" />
                    <h3 className="text-sm font-semibold text-gray-700">
                      {t('detail.contractSection')}
                    </h3>
                  </div>

                  {/* Activity field */}
                  <div className="mb-5">
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      {t('detail.contractActivity')}
                    </label>
                    <input
                      type="text"
                      value={contractState.actividad}
                      onChange={(e) =>
                        setContractState((prev) => ({ ...prev, actividad: e.target.value }))
                      }
                      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                    {actividadContext && (
                      <p className="mt-1 text-xs text-gray-400 italic">
                        {actividadContext}
                      </p>
                    )}
                  </div>

                  {/* Annex I — SI/NO per product */}
                  {siNoProducts.length > 0 && (
                    <div className="mb-5">
                      <p className="text-xs font-medium text-gray-500 mb-2">
                        {t('detail.siNoSection')}
                      </p>
                      <div className="space-y-2">
                        {siNoProducts.map((product) => (
                          <div key={product} className="flex items-center justify-between gap-4">
                            <span className="text-sm text-gray-700 flex-1">{product}</span>
                            <select
                              value={contractState.siNoFields[product] ?? ''}
                              onChange={(e) =>
                                setContractState((prev) => ({
                                  ...prev,
                                  siNoFields: { ...prev.siNoFields, [product]: e.target.value },
                                }))
                              }
                              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300 min-w-[90px]"
                            >
                              <option value="">—</option>
                              <option value="Sí">Sí</option>
                              <option value="No">No</option>
                            </select>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Commission table */}
                  <div className="mb-4">
                    <p className="text-xs font-medium text-gray-500 mb-2">
                      {t('detail.commissions')}
                    </p>
                    <div className="border border-gray-200 rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 bg-gray-50">
                            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                              {t('detail.commissionProduct')}
                            </th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                              {t('detail.commissionPrima')}
                            </th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                              {t('detail.commissionNP')}
                            </th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500">
                              {t('detail.commissionCartera')}
                            </th>
                            <th className="w-8" />
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {contractState.commissions.map((row, idx) => (
                            <tr key={idx}>
                              <td className="py-1.5 px-2">
                                <input
                                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                  value={row.producto}
                                  onChange={(e) =>
                                    updateCommissionRow(idx, 'producto', e.target.value)
                                  }
                                />
                              </td>
                              <td className="py-1.5 px-2">
                                <input
                                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                  value={row.prima}
                                  onChange={(e) =>
                                    updateCommissionRow(idx, 'prima', e.target.value)
                                  }
                                />
                              </td>
                              <td className="py-1.5 px-2">
                                <input
                                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                  value={row.comision_np}
                                  onChange={(e) =>
                                    updateCommissionRow(idx, 'comision_np', e.target.value)
                                  }
                                />
                              </td>
                              <td className="py-1.5 px-2">
                                <input
                                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                  value={row.comision_cartera}
                                  onChange={(e) =>
                                    updateCommissionRow(idx, 'comision_cartera', e.target.value)
                                  }
                                />
                              </td>
                              <td className="py-1.5 px-2 text-center">
                                <button
                                  type="button"
                                  onClick={() => removeCommissionRow(idx)}
                                  className="p-0.5 rounded text-gray-400 hover:text-red-500 transition-colors"
                                  aria-label="Remove row"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Add row button */}
                    <button
                      type="button"
                      onClick={addCommissionRow}
                      className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
                    >
                      + {t('detail.addCommissionRow')}
                    </button>
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
                    <button
                      type="button"
                      onClick={handleSaveContractData}
                      disabled={isSavingContract}
                      className="inline-flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-gray-900 transition-colors disabled:opacity-60"
                    >
                      {isSavingContract && <Loader2 className="h-4 w-4 animate-spin" />}
                      {isSavingContract
                        ? t('detail.savingContractData')
                        : t('detail.saveContractData')}
                    </button>
                    <button
                      type="button"
                      onClick={handleDownloadContractPdf}
                      disabled={isDownloadingContract}
                      className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {isDownloadingContract ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      {isDownloadingContract
                        ? t('detail.downloadingContract')
                        : t('detail.downloadContract')}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Right / sidebar column */}
            <div className="space-y-6">
              {/* Documents */}
              <DocumentDownloadList
                submissionId={submission.id}
                documents={submission.documents}
                onRefetch={() => refetchSubmission()}
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
