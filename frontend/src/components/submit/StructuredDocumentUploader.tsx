import { useCallback, useRef, useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckSquare, Square, Upload, FileText, X, Download, AlertCircle, Loader2 } from 'lucide-react'
import { useDeclarationTemplateStatus } from '../../hooks/useDeclarationTemplates'
import { generateDeclarationPdf } from '../../lib/api'
import type { DocumentSlot } from '../../lib/documentRequirements'
import type { PartnerInfo } from '../../lib/types'

export interface StructuredSubmitPayload {
  files: Array<{ file: File; slotId: string; label: string }>
  notApplicableSlots: string[]
}

interface SlotState {
  file: File | null
  notApplicable: boolean
  error: string | null
}

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

const ACCEPTED_EXTENSIONS = '.pdf,.jpg,.jpeg,.png,.docx'
const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── Declaration banner — prominent top-of-page call to action ─────────────────

interface DeclarationBannerProps {
  providerType: string
  entityType: string
  partnerInfo: PartnerInfo
}

function DeclarationBanner({ providerType, entityType, partnerInfo }: DeclarationBannerProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useDeclarationTemplateStatus(providerType, entityType)
  const [isGenerating, setIsGenerating] = useState(false)

  // Don't render anything while loading or if no template has been uploaded yet
  if (isLoading || !data) return null

  const handleDownload = async () => {
    setIsGenerating(true)
    try {
      const blob = await generateDeclarationPdf(providerType, entityType, partnerInfo)
      const url = window.URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url
      anchor.download = 'declaracion.pdf'
      window.document.body.appendChild(anchor)
      anchor.click()
      window.document.body.removeChild(anchor)
      window.URL.revokeObjectURL(url)
    } catch {
      // Silently fail — the user can retry
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="rounded-xl border-2 border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start gap-3">
        <Download className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-900">
            {t('structuredUpload.declarationBannerTitle')}
          </p>
          <p className="mt-1 text-sm text-amber-800 leading-relaxed">
            {t('structuredUpload.declarationBannerInstructions')}
          </p>
          <button
            type="button"
            onClick={handleDownload}
            disabled={isGenerating}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-amber-700 transition-colors disabled:opacity-60"
          >
            {isGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {isGenerating
              ? t('structuredUpload.declarationBannerGenerating')
              : t('structuredUpload.declarationBannerDownload')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Single slot ────────────────────────────────────────────────────────────────

interface SingleSlotProps {
  slot: DocumentSlot
  state: SlotState
  showValidation: boolean
  onFileChange: (slotId: string, file: File | null) => void
  onNotApplicableChange: (slotId: string, value: boolean) => void
}

function SingleSlot({
  slot,
  state,
  showValidation,
  onFileChange,
  onNotApplicableChange,
}: SingleSlotProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)

  const isRequired = !slot.isConditional
  const isMissing = showValidation && !state.file && !state.notApplicable

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      const droppedFile = e.dataTransfer.files[0]
      if (!droppedFile) return
      if (!ACCEPTED_MIME_TYPES.includes(droppedFile.type)) {
        onFileChange(slot.id, null)
        return
      }
      if (droppedFile.size > MAX_FILE_SIZE_BYTES) return
      onFileChange(slot.id, droppedFile)
    },
    [slot.id, onFileChange]
  )

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (f.size > MAX_FILE_SIZE_BYTES) return
    onFileChange(slot.id, f)
    e.target.value = ''
  }

  const borderColor = isMissing
    ? 'border-red-300'
    : state.notApplicable
    ? 'border-gray-200 bg-gray-50'
    : state.file
    ? 'border-green-200 bg-green-50'
    : 'border-gray-200'

  return (
    <div className={`rounded-xl border p-4 transition-colors ${borderColor}`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">{slot.label}</p>
          {slot.note && (
            <p className="mt-0.5 text-xs text-gray-500 italic">{slot.note}</p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {isRequired && (
            <span className="text-xs text-red-500 font-medium">{t('structuredUpload.required')}</span>
          )}
          {slot.isConditional && !isRequired && (
            <span className="text-xs text-gray-400">{t('structuredUpload.conditional')}</span>
          )}
        </div>
      </div>

      {/* Not-applicable state */}
      {state.notApplicable ? (
        <div className="flex items-center gap-2">
          <CheckSquare className="h-3.5 w-3.5 text-gray-400" />
          <span className="text-xs text-gray-400 italic">{t('structuredUpload.notApplicableDeclared')}</span>
          <button
            type="button"
            onClick={() => onNotApplicableChange(slot.id, false)}
            className="text-xs text-primary-600 hover:text-primary-800 underline"
          >
            {t('structuredUpload.undoNotApplicable')}
          </button>
        </div>
      ) : state.file ? (
        /* File uploaded */
        <div className="flex items-center gap-2 bg-white rounded-lg border border-gray-200 px-3 py-2">
          <FileText className="h-4 w-4 text-red-500 flex-shrink-0" />
          <span className="flex-1 text-xs text-gray-700 truncate">{state.file.name}</span>
          <span className="text-xs text-gray-400 whitespace-nowrap">{formatBytes(state.file.size)}</span>
          <button
            type="button"
            onClick={() => onFileChange(slot.id, null)}
            className="p-0.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            aria-label={t('structuredUpload.removeFile')}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        /* Empty — show drop zone */
        <div>
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`flex items-center gap-2 rounded-lg border-2 border-dashed px-3 py-2.5 cursor-pointer transition-colors
              ${isMissing ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-primary-400 hover:bg-primary-50'}`}
          >
            <Upload className={`h-4 w-4 flex-shrink-0 ${isMissing ? 'text-red-400' : 'text-gray-400'}`} />
            <span className={`text-xs ${isMissing ? 'text-red-600' : 'text-gray-500'}`}>
              {isMissing ? t('structuredUpload.missingRequired') : t('structuredUpload.clickOrDrop')}
            </span>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            className="hidden"
            onChange={handleInputChange}
          />
          {/* Conditional toggle */}
          {slot.isConditional && (
            <button
              type="button"
              onClick={() => onNotApplicableChange(slot.id, true)}
              className="mt-2 flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              <Square className="h-3.5 w-3.5" />
              {t('structuredUpload.notApplicable')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

interface StructuredDocumentUploaderProps {
  slots: DocumentSlot[]
  providerType: string
  entityType: string
  partnerInfo: PartnerInfo
  onSubmit: (payload: StructuredSubmitPayload) => void
  isSubmitting: boolean
}

export function StructuredDocumentUploader({
  slots,
  providerType,
  entityType,
  partnerInfo,
  onSubmit,
  isSubmitting,
}: StructuredDocumentUploaderProps) {
  const { t } = useTranslation()
  const [showValidation, setShowValidation] = useState(false)

  const initialState = (): Record<string, SlotState> => {
    const map: Record<string, SlotState> = {}
    slots.forEach((s) => {
      map[s.id] = { file: null, notApplicable: false, error: null }
    })
    return map
  }

  const [slotStates, setSlotStates] = useState<Record<string, SlotState>>(initialState)

  // Re-initialize when slots change
  useEffect(() => {
    setSlotStates(initialState())
    setShowValidation(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots.map((s) => s.id).join(',')])

  const handleFileChange = (slotId: string, file: File | null) => {
    setSlotStates((prev) => ({
      ...prev,
      [slotId]: { ...prev[slotId], file, notApplicable: false, error: null },
    }))
  }

  const handleNotApplicableChange = (slotId: string, value: boolean) => {
    setSlotStates((prev) => ({
      ...prev,
      [slotId]: { ...prev[slotId], notApplicable: value, file: null, error: null },
    }))
  }

  const canSubmit = () => {
    return slots.every((slot) => {
      const state = slotStates[slot.id]
      if (!state) return false
      if (state.file) return true
      if (slot.isConditional && state.notApplicable) return true
      if (!slot.isConditional && !state.file) return false
      return false
    })
  }

  const handleSubmit = () => {
    if (!canSubmit()) {
      setShowValidation(true)
      return
    }

    const files: StructuredSubmitPayload['files'] = []
    const notApplicableSlots: string[] = []

    slots.forEach((slot) => {
      const state = slotStates[slot.id]
      if (state.file) {
        files.push({ file: state.file, slotId: slot.id, label: slot.label })
      } else if (state.notApplicable) {
        notApplicableSlots.push(slot.id)
      }
    })

    onSubmit({ files, notApplicableSlots })
  }

  // Show the declaration banner only when at least one slot requires it
  const hasDeclarationSlot = slots.some((s) => s.hasDeclarationTemplate)

  return (
    <div className="space-y-3">
      {hasDeclarationSlot && (
        <DeclarationBanner
          providerType={providerType}
          entityType={entityType}
          partnerInfo={partnerInfo}
        />
      )}

      {slots.map((slot) => (
        <SingleSlot
          key={slot.id}
          slot={slot}
          state={slotStates[slot.id] ?? { file: null, notApplicable: false, error: null }}
          showValidation={showValidation}
          onFileChange={handleFileChange}
          onNotApplicableChange={handleNotApplicableChange}
        />
      ))}

      {showValidation && !canSubmit() && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3">
          <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
          <p className="text-xs text-red-700">{t('structuredUpload.validationError')}</p>
        </div>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={isSubmitting}
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? t('submit.submitting') : t('submit.submit')}
      </button>
    </div>
  )
}
