import { useState } from 'react'
import { ChevronDown, FileText, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { AnalystHeader } from '../components/layout/AnalystHeader'
import { getRequiredSlots } from '../lib/documentRequirements'
import type { ProviderType } from '../lib/types'

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

// Colour accents per provider type
const PROVIDER_COLOURS: Record<ProviderType, string> = {
  correduria_seguros: 'border-blue-500 bg-blue-50',
  agencia_seguros: 'border-purple-500 bg-purple-50',
  colaborador_externo: 'border-green-500 bg-green-50',
  generador_leads: 'border-orange-500 bg-orange-50',
}

const PROVIDER_ICON_COLOURS: Record<ProviderType, string> = {
  correduria_seguros: 'text-blue-600',
  agencia_seguros: 'text-purple-600',
  colaborador_externo: 'text-green-600',
  generador_leads: 'text-orange-600',
}

function DocumentList({ providerType, entityType }: { providerType: ProviderType; entityType: string }) {
  const slots = getRequiredSlots(providerType, entityType)

  return (
    <ul className="divide-y divide-gray-100">
      {slots.map((slot, index) => (
        <li key={slot.id} className="flex items-start gap-3 py-3">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-medium flex items-center justify-center mt-0.5">
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800">{slot.label}</p>
            {slot.note && (
              <p className="mt-0.5 flex items-center gap-1 text-xs text-amber-600">
                <AlertCircle className="h-3 w-3 flex-shrink-0" />
                {slot.note}
              </p>
            )}
          </div>
          {slot.isConditional ? (
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

  const pjCount = getRequiredSlots(providerType, 'PJ').length
  const pfCount = getRequiredSlots(providerType, 'PF').length

  return (
    <div className={`rounded-xl border-l-4 bg-white shadow-sm overflow-hidden ${PROVIDER_COLOURS[providerType]}`}>
      {/* Accordion header */}
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          <FileText className={`h-5 w-5 flex-shrink-0 ${PROVIDER_ICON_COLOURS[providerType]}`} />
          <div>
            <span className="font-semibold text-gray-900">{label}</span>
            <span className="ml-3 text-xs text-gray-400">
              {pjCount} docs (PJ) · {pfCount} docs (PF)
            </span>
          </div>
        </div>
        <ChevronDown
          className={`h-5 w-5 text-gray-400 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Accordion body */}
      {isOpen && (
        <div className="border-t border-gray-100 px-5 pb-5">
          {/* PJ / PF tab switcher */}
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

          <DocumentList providerType={providerType} entityType={activeEntity} />
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
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">{t('docList.title')}</h1>
          <p className="mt-1 text-sm text-gray-500">{t('docList.subtitle')}</p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 mb-6 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-green-200" />
            Obligatorio — sempre requerit
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-amber-200" />
            Condicional — depèn del cas
          </span>
        </div>

        {/* Accordions */}
        <div className="space-y-3">
          {PROVIDER_TYPES.map((pt) => (
            <ProviderAccordion key={pt.value} providerType={pt.value} label={pt.label} />
          ))}
        </div>
      </main>
    </div>
  )
}
