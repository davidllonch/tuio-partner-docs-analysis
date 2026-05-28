import { useState, useRef } from 'react'
import {
  Upload,
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Minus,
  Loader2,
  RefreshCw,
  FileText,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import { validateDocuments } from '../lib/api'
import type { ProviderType, EntityType, ValidationResponse, ValidationStatus } from '../lib/types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

const ENTITY_TYPES: { value: EntityType; label: string }[] = [
  { value: 'PJ', label: 'Persona Jurídica (PJ)' },
  { value: 'PF', label: 'Persona Física (PF)' },
]

const ALLOWED_EXTENSIONS = ['.pdf', '.jpeg', '.jpg', '.png', '.docx']
const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const MAX_FILE_BYTES = 20 * 1024 * 1024   // 20 MB
const MAX_TOTAL_BYTES = 100 * 1024 * 1024  // 100 MB

// ---------------------------------------------------------------------------
// Helper: format bytes
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ---------------------------------------------------------------------------
// Status badge component
// ---------------------------------------------------------------------------

function StatusBadge({
  status,
  isConditional,
}: {
  status: ValidationStatus
  isConditional: boolean
}) {
  const { t } = useTranslation()

  if (status === 'covered') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
        <CheckCircle2 className="h-3.5 w-3.5" />
        {t('validateDocuments.statusCovered')}
      </span>
    )
  }
  if (status === 'partial') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
        <AlertTriangle className="h-3.5 w-3.5" />
        {t('validateDocuments.statusPartial')}
      </span>
    )
  }
  // missing
  if (isConditional) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
        <Minus className="h-3.5 w-3.5" />
        {t('validateDocuments.statusConditional')}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
      <XCircle className="h-3.5 w-3.5" />
      {t('validateDocuments.statusMissing')}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ValidateDocumentsPage() {
  const { t } = useTranslation()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // --- Form state ---
  const [providerType, setProviderType] = useState<ProviderType | ''>('')
  const [entityType, setEntityType] = useState<EntityType | ''>('')
  const [files, setFiles] = useState<File[]>([])
  const [fileErrors, setFileErrors] = useState<string[]>([])
  const [isDragging, setIsDragging] = useState(false)

  // --- Request state ---
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ValidationResponse | null>(null)

  // ---------------------------------------------------------------------------
  // File handling
  // ---------------------------------------------------------------------------

  const totalSize = files.reduce((acc, f) => acc + f.size, 0)
  const totalTooLarge = totalSize > MAX_TOTAL_BYTES

  function addFiles(incoming: FileList | File[]) {
    const errors: string[] = []
    const candidates: File[] = []

    Array.from(incoming).forEach((file) => {
      if (!ALLOWED_MIME_TYPES.has(file.type)) {
        errors.push(
          t('validateDocuments.invalidType', { name: file.name })
        )
        return
      }
      if (file.size > MAX_FILE_BYTES) {
        errors.push(t('validateDocuments.fileTooLarge', { name: file.name }))
        return
      }
      candidates.push(file)
    })

    // Duplicate check must run inside the updater so it sees the latest state,
    // not a stale closure — prevents missed duplicates when called twice quickly.
    setFiles((prev) => {
      const deduped = candidates.filter(
        (f) => !prev.some((p) => p.name === f.name && p.size === f.size)
      )
      return [...prev, ...deduped]
    })
    setFileErrors(errors)
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
    setFileErrors([])
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      addFiles(e.target.files)
      e.target.value = ''
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files)
  }

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  const isFormValid =
    providerType !== '' && entityType !== '' && files.length > 0 && !totalTooLarge

  async function handleSubmit() {
    if (!isFormValid) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await validateDocuments(providerType, entityType, files)
      setResult(data)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t('validateDocuments.errorGeneric')
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  function handleReset() {
    setResult(null)
    setFiles([])
    setFileErrors([])
    setError(null)
    setProviderType('')
    setEntityType('')
  }

  // ---------------------------------------------------------------------------
  // Render: results table
  // ---------------------------------------------------------------------------

  if (result) {
    const providerLabel =
      PROVIDER_TYPES.find((p) => p.value === result.provider_type)?.label ?? result.provider_type
    const entityLabel =
      ENTITY_TYPES.find((e) => e.value === result.entity_type)?.label ?? result.entity_type

    const covered = result.results.filter((r) => r.status === 'covered').length
    const partial = result.results.filter((r) => r.status === 'partial').length
    const missing = result.results.filter(
      (r) => r.status === 'missing' && !r.is_conditional
    ).length

    return (
      <div className="min-h-screen bg-gray-50">
        <AnalystHeader />
        <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900">
              {t('validateDocuments.resultTitle')}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {providerLabel} — {entityLabel}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {t('validateDocuments.modelUsed', { model: result.model_used })}
            </p>
          </div>

          {/* Summary chips */}
          <div className="flex flex-wrap gap-3 mb-6">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-700">
              <CheckCircle2 className="h-4 w-4" />
              {covered} {t('validateDocuments.statusCovered')}
            </span>
            {partial > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-amber-100 text-amber-700">
                <AlertTriangle className="h-4 w-4" />
                {partial} {t('validateDocuments.statusPartial')}
              </span>
            )}
            {missing > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-700">
                <XCircle className="h-4 w-4" />
                {missing} {t('validateDocuments.statusMissing')}
              </span>
            )}
          </div>

          {/* Results table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    {t('validateDocuments.colStatus')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('validateDocuments.colDocument')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('validateDocuments.colFile')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('validateDocuments.colObservation')}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.results.map((row) => (
                  <tr
                    key={row.slot_id}
                    className={
                      row.status === 'missing' && !row.is_conditional
                        ? 'bg-red-50/40'
                        : row.status === 'partial'
                        ? 'bg-amber-50/40'
                        : ''
                    }
                  >
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} isConditional={row.is_conditional} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-800">{row.slot_label}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {row.matched_filename ? (
                        <span className="inline-flex items-center gap-1">
                          <FileText className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                          {row.matched_filename}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {row.observation ?? <span className="text-gray-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Unmatched files */}
          {result.unmatched_files.length > 0 && (
            <div className="mb-6 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
              <p className="font-medium mb-1">{t('validateDocuments.unmatchedFiles')}:</p>
              <ul className="list-disc list-inside space-y-0.5">
                {result.unmatched_files.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reset button */}
          <button
            onClick={handleReset}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
          >
            <RefreshCw className="h-4 w-4" />
            {t('validateDocuments.newValidation')}
          </button>
        </main>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: form
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-gray-50">
      <AnalystHeader />
      <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            {t('validateDocuments.title')}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{t('validateDocuments.subtitle')}</p>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 flex items-start gap-2">
            <XCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-6">
          {/* Selectors */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('validateDocuments.providerType')}
              </label>
              <select
                value={providerType}
                onChange={(e) => setProviderType(e.target.value as ProviderType)}
                disabled={isLoading}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
              >
                <option value="">— Selecciona un tipo —</option>
                {PROVIDER_TYPES.map((pt) => (
                  <option key={pt.value} value={pt.value}>
                    {pt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('validateDocuments.entityType')}
              </label>
              <select
                value={entityType}
                onChange={(e) => setEntityType(e.target.value as EntityType)}
                disabled={isLoading}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
              >
                <option value="">— Selecciona un tipo —</option>
                {ENTITY_TYPES.map((et) => (
                  <option key={et.value} value={et.value}>
                    {et.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Drop zone */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => !isLoading && fileInputRef.current?.click()}
              className={`
                relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed
                px-6 py-8 cursor-pointer transition-colors
                ${isDragging
                  ? 'border-primary-400 bg-primary-50'
                  : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
                }
                ${isLoading ? 'opacity-50 pointer-events-none' : ''}
              `}
            >
              <Upload className="h-8 w-8 text-gray-400" />
              <p className="text-sm font-medium text-gray-700">
                {t('validateDocuments.dropzone')}
              </p>
              <p className="text-xs text-gray-400">{t('validateDocuments.dropzoneHint')}</p>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ALLOWED_EXTENSIONS.join(',')}
                onChange={handleInputChange}
                className="hidden"
              />
            </div>

            {/* File errors */}
            {fileErrors.length > 0 && (
              <div className="mt-3 space-y-1">
                {fileErrors.map((err, i) => (
                  <p key={i} className="text-xs text-red-600 flex items-center gap-1">
                    <XCircle className="h-3.5 w-3.5 flex-shrink-0" />
                    {err}
                  </p>
                ))}
              </div>
            )}

            {/* File list */}
            {files.length > 0 && (
              <ul className="mt-4 divide-y divide-gray-100">
                {files.map((file, i) => (
                  <li key={i} className="flex items-center gap-3 py-2">
                    <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {formatBytes(file.size)}
                    </span>
                    {!isLoading && (
                      <button
                        onClick={() => removeFile(i)}
                        className="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors"
                        aria-label={`Eliminar ${file.name}`}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {/* Total size */}
            {files.length > 0 && (
              <p className={`mt-3 text-xs ${totalTooLarge ? 'text-red-600 font-medium' : 'text-gray-400'}`}>
                {t('validateDocuments.totalSize', {
                  size: (totalSize / (1024 * 1024)).toFixed(1),
                })}
                {totalTooLarge && ` — ${t('validateDocuments.totalTooLarge')}`}
              </p>
            )}
          </div>

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={!isFormValid || isLoading}
            className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary-600 text-white font-medium text-sm shadow-sm hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t('validateDocuments.validating')}
              </>
            ) : (
              t('validateDocuments.validate')
            )}
          </button>
        </div>
      </main>
    </div>
  )
}
