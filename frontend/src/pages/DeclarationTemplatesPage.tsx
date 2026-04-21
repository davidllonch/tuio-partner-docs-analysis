import { useRef, useState } from 'react'
import { Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAllDeclarationTemplates, useUploadDeclarationTemplate } from '../hooks/useDeclarationTemplates'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { useToast } from '../components/ui/Toast'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import type { ProviderType } from '../lib/types'

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

const ENTITY_TYPES = [
  { value: 'PJ', label: 'Persona Jurídica' },
  { value: 'PF', label: 'Persona Física' },
]

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

function isDocxFile(file: File): boolean {
  // Some browsers/OS return an empty or wrong MIME type for DOCX — fall back to extension
  if (file.type === DOCX_MIME) return true
  if (file.name.toLowerCase().endsWith('.docx')) return true
  return false
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function DeclarationTemplatesPage() {
  const { t } = useTranslation()
  const { toast } = useToast()

  const { data, isLoading } = useAllDeclarationTemplates()
  const uploadMutation = useUploadDeclarationTemplate()
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const handleUpload = (providerType: string, entityType: string, file: File) => {
    if (!isDocxFile(file)) {
      toast({ title: t('declarationTemplates.errorNotDocx'), variant: 'error' })
      return
    }
    uploadMutation.mutate(
      { providerType, entityType, file },
      {
        onSuccess: () => toast({ title: t('declarationTemplates.uploadSuccess'), variant: 'success' }),
        onError: () => toast({ title: t('declarationTemplates.uploadError'), variant: 'error' }),
      }
    )
  }

  // Build lookup: "providerType__entityType" → template info
  const templateMap = Object.fromEntries(
    (data?.templates ?? []).map((tmpl) => [`${tmpl.provider_type}__${tmpl.entity_type}`, tmpl])
  )

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AnalystHeader />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-900">{t('declarationTemplates.title')}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{t('declarationTemplates.subtitle')}</p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <div className="space-y-6">
            {PROVIDER_TYPES.map(({ value: providerType, label: providerLabel }) => (
              <div key={providerType} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 bg-gray-50 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-800">{providerLabel}</h3>
                </div>

                <div className="divide-y divide-gray-100">
                  {ENTITY_TYPES.map(({ value: entityType, label: entityLabel }) => {
                    const key = `${providerType}__${entityType}`
                    const template = templateMap[key]
                    const isUploading =
                      uploadMutation.isPending &&
                      uploadMutation.variables?.providerType === providerType &&
                      uploadMutation.variables?.entityType === entityType
                    const inputKey = key

                    return (
                      <div key={entityType} className="flex items-start justify-between gap-4 px-5 py-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-700">{entityLabel}</p>
                          {template ? (
                            <div className="mt-1 flex items-center gap-1.5 text-xs text-green-700">
                              <CheckCircle className="h-3.5 w-3.5 flex-shrink-0" />
                              <span>
                                {t('declarationTemplates.uploadedBy', {
                                  name: template.uploaded_by_name ?? t('declarationTemplates.unknownAnalyst'),
                                  date: formatDate(template.uploaded_at.toString()),
                                })}
                                {' — '}<span className="font-medium">{template.original_filename}</span>
                              </span>
                            </div>
                          ) : (
                            <div className="mt-1 flex items-center gap-1.5 text-xs text-gray-400">
                              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                              <span>{t('declarationTemplates.noTemplate')}</span>
                            </div>
                          )}
                        </div>

                        <div className="flex-shrink-0">
                          <input
                            ref={(el) => { fileInputRefs.current[inputKey] = el }}
                            type="file"
                            accept=".docx"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0]
                              if (file) handleUpload(providerType, entityType, file)
                              e.target.value = ''
                            }}
                          />
                          <button
                            onClick={() => fileInputRefs.current[inputKey]?.click()}
                            disabled={isUploading}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-60"
                          >
                            {isUploading ? (
                              <LoadingSpinner size="sm" />
                            ) : (
                              <Upload className="h-3.5 w-3.5" />
                            )}
                            {template
                              ? t('declarationTemplates.replaceDocx')
                              : t('declarationTemplates.uploadDocx')}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

    </div>
  )
}
