export type ProviderType =
  | 'correduria_seguros'
  | 'agencia_seguros'
  | 'colaborador_externo'
  | 'generador_leads'

export type EntityType = 'PF' | 'PJ'

export type SubmissionStatus = 'pending' | 'analysing' | 'complete' | 'error'

export type InvitationStatus = 'pending' | 'submitted' | 'expired'

export interface SubmissionListItem {
  id: string
  created_at: string
  provider_name: string
  provider_type: ProviderType
  entity_type: EntityType
  country: string
  status: SubmissionStatus
  email_sent_at: string | null
}

export interface Document {
  id: string
  original_filename: string
  user_label: string
  mime_type: string
  size_bytes: number
  uploaded_at: string
}

export interface Analysis {
  id: string
  provider_type: ProviderType
  ai_model_used: string | null
  triggered_by: 'partner' | 'analyst'
  created_at: string
}

export interface ReanalyseResponse {
  status: string
  analysis_id: string
}

export interface SubmissionDetail extends SubmissionListItem {
  ai_response: string | null
  error_message: string | null
  partner_info: string | null
  contract_data: string | null
  documents: Document[]
  analyses: Analysis[]
}

export interface PaginatedSubmissions {
  items: SubmissionListItem[]
  total: number
  page: number
  size: number
}

export interface Analyst {
  id: string
  email: string
  full_name: string | null
  is_admin: boolean
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  analyst: Analyst
}

export interface ReanalyseRequest {
  provider_type: ProviderType
  model?: string
}

export interface ModelOption {
  id: string
  display_name: string
}

export interface AnalystListItem {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface CreateAnalystRequest {
  email: string
  full_name: string
  password: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

// Human-readable labels for provider types
export const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  correduria_seguros: 'Correduría de Seguros',
  agencia_seguros: 'Agencia de Seguros',
  colaborador_externo: 'Colaborador Externo',
  generador_leads: 'Generador de Leads',
}

// Human-readable labels for entity types
export const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  PJ: 'Legal Entity (Persona Jurídica)',
  PF: 'Physical Person (Persona Física)',
}

// ── Invitation types ──────────────────────────────────────────────────────────

export interface InvitationAnalyst {
  id: string
  full_name: string | null
}

export interface InvitationListItem {
  id: string
  token: string
  provider_name: string
  provider_type: ProviderType
  entity_type: EntityType
  country: string
  status: InvitationStatus
  created_at: string
  expires_at: string
  submission_id: string | null
  created_by_analyst: InvitationAnalyst | null
}

export interface InvitationCreateResponse extends InvitationListItem {
  invitation_url: string
}

export interface InvitationPublic {
  provider_name: string
  provider_type: ProviderType
  entity_type: EntityType
  country: string
  status: InvitationStatus
}

export interface CreateInvitationRequest {
  provider_name: string
  provider_type: ProviderType
  entity_type: EntityType
  country: string
}

export interface PaginatedInvitations {
  items: InvitationListItem[]
  total: number
  page: number
  size: number
}

// ── Partner info types (for declaration personalisation) ──────────────────────

export interface PartnerInfoPJ {
  entity_type: 'PJ'
  razon_social: string
  cif: string
  domicilio_social: string
  nombre_representante: string
  nif_representante: string
  poder: string
  email: string
  direccion_notificaciones: string
  contacto_notificaciones: string
  clave_dgs?: string
}

export interface PartnerInfoPF {
  entity_type: 'PF'
  nombre_apellidos: string
  nif: string
  domicilio: string
  email: string
  direccion_notificaciones: string
  contacto_notificaciones: string
  clave_dgs?: string
}

export type PartnerInfo = PartnerInfoPJ | PartnerInfoPF

// ── Declaration template types ────────────────────────────────────────────────

export interface DeclarationTemplateInfo {
  provider_type: string
  entity_type: string
  provider_type_label: string
  entity_type_label: string
  original_filename: string
  uploaded_at: string
  uploaded_by_name: string | null
}

export interface AllDeclarationTemplatesResponse {
  templates: DeclarationTemplateInfo[]
}

// ── Contract template types ───────────────────────────────────────────────────

export interface ContractTemplateInfo {
  provider_type: string
  entity_type: string
  provider_type_label: string
  entity_type_label: string
  original_filename: string
  uploaded_at: string
  uploaded_by_name: string | null
}

export interface AllContractTemplatesResponse {
  templates: ContractTemplateInfo[]
}
