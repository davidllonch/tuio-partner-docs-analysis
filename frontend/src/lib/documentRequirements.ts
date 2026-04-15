export interface DocumentSlot {
  id: string
  label: string           // Spanish label shown to the partner
  note?: string           // Explanatory note for conditional slots
  isConditional: boolean  // true → partner can mark "No me aplica"
  hasDeclarationTemplate: boolean  // true → show download button
}

// Base document slots for Persona Jurídica (legal entity)
const PJ_BASE_SLOTS: DocumentSlot[] = [
  { id: 'escrituras_constitucion', label: 'Escrituras de constitución', isConditional: false, hasDeclarationTemplate: false },
  { id: 'escrituras_apoderamiento', label: 'Escrituras de apoderamiento de representantes legales', isConditional: false, hasDeclarationTemplate: false },
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
  { id: 'poliza_rc', label: 'Póliza de RC profesional en vigor + justificante de pago', isConditional: false, hasDeclarationTemplate: false },
  { id: 'cert_formacion', label: 'Certificado de formación del responsable de la distribución', isConditional: false, hasDeclarationTemplate: false },
  { id: 'declaraciones', label: 'Declaraciones firmadas del proveedor', isConditional: false, hasDeclarationTemplate: true },
]

// Additional slot for colaborador externo and generador de leads
const DECLARATIONS_SLOT: DocumentSlot[] = [
  { id: 'declaraciones', label: 'Declaraciones firmadas', isConditional: false, hasDeclarationTemplate: true },
]

/**
 * Returns the ordered list of required document slots for a given partner
 * type and entity type combination.
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
