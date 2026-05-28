import { useState } from 'react'
import { ChevronDown, FileText, AlertCircle, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import { useDocumentRequirements } from '../lib/documentRequirements'
import type { ApiDocumentSlot, ProviderType } from '../lib/types'

// All provider types with their display labels
const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

const ENTITY_TYPES = [
  { value: 'PJ', label: 'Persona Jurídica (PJ)' },
  { value: 'PF', label: 'Persona Física (PF)' },
]

const PROVIDER_COLOURS: Record<ProviderType, string> = {
  correduria_seguros: 'border-blue-500',
  agencia_seguros: 'border-purple-500',
  colaborador_externo: 'border-green-500',
  generador_leads: 'border-orange-500',
}

const PROVIDER_ICON_COLOURS: Record<ProviderType, string> = {
  correduria_seguros: 'text-blue-600',
  agencia_seguros: 'text-purple-600',
  colaborador_externo: 'text-green-600',
  generador_leads: 'text-orange-600',
}

function DocumentList({ slots }: { slots: ApiDocumentSlot[] }) {
  return (
    <ul className="divide-y divide-gray-100">
      {slots.map((slot, index) => (
        <li key={slot.id} className="flex items-start gap-3 py-3">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-medium flex items-center justify-center mt-0.5">
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800">{slot.label}</p>
          </div>
          {slot.is_conditional ? (
            <span className="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
              Condicional
            </span>
          ) : (
            <span className="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
              Obligatorio
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

function ProviderAccordion({ providerType, label }: { providerType: ProviderType; label: string }) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeEntity, setActiveEntity] = useState<'PJ' | 'PF'>('PJ')

  const { data, isLoading, isError } = useDocumentRequirements(
    isOpen ? providerType : '',
    isOpen ? activeEntity : ''
  )

  return (
    <div className={`rounded-xl border-l-4 bg-white shadow-sm overflow-hidden ${PROVIDER_COLOURS[providerType]}`}>
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          <FileText className={`h-5 w-5 flex-shrink-0 ${PROVIDER_ICON_COLOURS[providerType]}`} />
          <span className="font-semibold text-gray-900">{label}</span>
        </div>
        <ChevronDown
          className={`h-5 w-5 text-gray-400 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div className="border-t border-gray-100 px-5 pb-5">
          <div className="flex gap-1 mt-4 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
            {ENTITY_TYPES.map((et) => (
              <button
                key={et.value}
                onClick={() => setActiveEntity(et.value as 'PJ' | 'PF')}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  activeEntity === et.value
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {et.label}
              </button>
            ))}
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 py-6 text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Carregant...</span>
            </div>
          ) : isError ? (
            <div className="flex items-center gap-2 py-6 text-red-500">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span className="text-sm">
                No s'han pogut carregar els requisits. Torna-ho a intentar.
              </span>
            </div>
          ) : data?.slots ? (
            <DocumentList slots={data.slots} />
          ) : null}
        </div>
      )}
    </div>
  )
}

export function DocumentationListPage() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-gray-50">
      <AnalystHeader />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">{t('docList.title')}</h1>
          <p className="mt-1 text-sm text-gray-500">{t('docList.subtitle')}</p>
        </div>

        <div className="flex items-center gap-4 mb-6 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-green-200" />
            Obligatorio — sempre requerit
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-amber-200" />
            <AlertCircle className="h-3 w-3 text-amber-400" />
            Condicional — depèn del cas
          </span>
        </div>

        <div className="space-y-3">
          {PROVIDER_TYPES.map((pt) => (
            <ProviderAccordion key={pt.value} providerType={pt.value} label={pt.label} />
          ))}
        </div>
      </main>
    </div>
  )
}
