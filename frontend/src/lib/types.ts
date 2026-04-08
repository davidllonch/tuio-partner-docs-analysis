export type ProviderType =
  | 'correduria_seguros'
  | 'agencia_seguros'
  | 'colaborador_externo'
  | 'generador_leads'

export type EntityType = 'PF' | 'PJ'

export type SubmissionStatus = 'pending' | 'analysing' | 'complete' | 'error'

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
  ai_model_used: string
  triggered_by: 'partner' | 'analyst'
  created_at: string
}

export interface SubmissionDetail extends SubmissionListItem {
  ai_response: string | null
  error_message: string | null
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
  full_name: string
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
