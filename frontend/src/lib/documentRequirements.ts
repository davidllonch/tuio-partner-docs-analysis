/**
 * Document requirements module.
 *
 * Dual purpose:
 *
 * 1. Partner-facing upload form (StructuredDocumentUploader / InvitePage):
 *    Uses the local `DocumentSlot` interface and `getRequiredSlots()` function.
 *    These include extra UX fields (note, sameAsConstitutionOption, etc.) that
 *    are only needed in the partner-facing form and are NOT sent to the backend.
 *
 * 2. Analyst-facing tools (DocumentationListPage / ValidateDocumentsPage):
 *    Uses `useDocumentRequirements()` hook which fetches from the backend API.
 *    The backend is the single source of truth for which documents are required.
 *    To change requirements, edit backend/app/routers/validate_documents.py.
 */

import { useQuery } from '@tanstack/react-query'
import { fetchDocumentRequirements } from './api'
import type { ProviderType, EntityType } from './types'

// ---------------------------------------------------------------------------
// Partner-facing DocumentSlot (used by StructuredDocumentUploader + InvitePage)
// Includes extra UX-only fields not present in the API response.
// ---------------------------------------------------------------------------

export interface DocumentSlot {
  id: string
  label: string
  note?: string
  isConditional: boolean
  hasDeclarationTemplate: boolean
  sameAsConstitutionOption?: boolean
}

// Base document slots for Persona Jurídica (legal entity)
const PJ_BASE_SLOTS: DocumentSlot[] = [
  { id: 'escrituras_constitucion', label: 'Escrituras de constitución', isConditional: false, hasDeclarationTemplate: false },
  { id: 'escrituras_apoderamiento', label: 'Escrituras de apoderamiento de representantes legales', isConditional: false, hasDeclarationTemplate: false, sameAsConstitutionOption: true },
  { id: 'dni_representante', label: 'DNI del representante legal', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_cuenta_gastos', label: 'Certificado de titularidad de cuenta bancaria (gastos generales)', isConditional: false, hasDeclarationTemplate: false },
  { id: 'titularidad_real', label: 'Acta de titularidad real (antigüedad menor de 12 meses) o último Modelo 200 presentado', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_ss_pj', label: 'Certificado de estar al corriente con la Seguridad Social', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_hacienda_pj', label: 'Certificado de estar al corriente con Hacienda', isConditional: false, hasDeclarationTemplate: false },
]

// Base document slots for Persona Física (individual)
const PF_BASE_SLOTS: DocumentSlot[] = [
  { id: 'doc_identidad', label: 'Documento de identidad', isConditional: false, hasDeclarationTemplate: false },
  { id: 'doc_alta_censal', label: 'Documento acreditativo de alta / situación censal / actividad económica', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_cuenta_bancaria', label: 'Certificado de titularidad de cuenta bancaria propia', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_hacienda_pf', label: 'Certificado de estar al corriente con Hacienda', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_ss_pf', label: 'Certificado de estar al corriente con la Seguridad Social', isConditional: false, hasDeclarationTemplate: false },
]

// Additional slots for insurance distributors (correduría + agencia)
const DISTRIBUTOR_EXTRA_SLOTS: DocumentSlot[] = [
  { id: 'resolucion_dgsfp', label: 'Resolución de la DGSFP de otorgamiento de clave', isConditional: false, hasDeclarationTemplate: false },
  {
    id: 'cert_cuenta_cobros',
    label: 'Certificado de titularidad de la cuenta dedicada a cobros de clientes',
    note: 'Solo requerido si la entidad cobra directamente de los clientes.',
    isConditional: true,
    hasDeclarationTemplate: false,
  },
  { id: 'poliza_rc', label: 'Póliza de RC profesional en vigor', isConditional: false, hasDeclarationTemplate: false },
  { id: 'justificante_pago_rc', label: 'Justificante de pago de la póliza RC', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_formacion', label: 'Certificado de formación del responsable de la distribución', isConditional: false, hasDeclarationTemplate: false },
  { id: 'declaraciones', label: 'Declaraciones firmadas del proveedor', isConditional: false, hasDeclarationTemplate: true },
]

// Additional slot for colaborador externo and generador de leads
const DECLARATIONS_SLOT: DocumentSlot[] = [
  { id: 'declaraciones', label: 'Declaraciones firmadas', isConditional: false, hasDeclarationTemplate: true },
]

/**
 * Returns the ordered list of required document slots for the partner-facing
 * upload form (StructuredDocumentUploader / InvitePage).
 *
 * For analyst-facing pages, use `useDocumentRequirements()` instead — it
 * fetches from the backend, which is the single source of truth.
 */
export function getRequiredSlots(providerType: string, entityType: string): DocumentSlot[] {
  const baseSlots = entityType === 'PJ' ? PJ_BASE_SLOTS : PF_BASE_SLOTS

  if (providerType === 'correduria_seguros' || providerType === 'agencia_seguros') {
    return [...baseSlots, ...DISTRIBUTOR_EXTRA_SLOTS]
  }

  if (providerType === 'colaborador_externo' || providerType === 'generador_leads') {
    return [...baseSlots, ...DECLARATIONS_SLOT]
  }

  return baseSlots
}

// ---------------------------------------------------------------------------
// Analyst-facing hook — fetches from backend API
// ---------------------------------------------------------------------------

/**
 * React Query hook that fetches the required document slots from the backend.
 * Used by DocumentationListPage and ValidateDocumentsPage.
 *
 * The backend (validate_documents.py) is the single source of truth.
 * To change which documents are required, edit that Python file.
 */
export function useDocumentRequirements(
  providerType: ProviderType | string,
  entityType: EntityType | string
) {
  return useQuery({
    queryKey: ['document-requirements', providerType, entityType],
    queryFn: () => fetchDocumentRequirements(providerType, entityType),
    staleTime: 1000 * 60 * 10, // cache 10 min — requirements rarely change
    enabled: Boolean(providerType) && Boolean(entityType),
  })
}
