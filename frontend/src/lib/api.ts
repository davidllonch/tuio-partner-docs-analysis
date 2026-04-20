import axios from 'axios'
import { getToken, clearToken } from './auth'
import type {
  PaginatedSubmissions,
  SubmissionDetail,
  LoginRequest,
  LoginResponse,
  ReanalyseRequest,
  ReanalyseResponse,
  ModelOption,
  AnalystListItem,
  CreateAnalystRequest,
  ChangePasswordRequest,
  Analyst,
  CreateInvitationRequest,
  InvitationCreateResponse,
  PaginatedInvitations,
  InvitationPublic,
  PartnerInfo,
  AllDeclarationTemplatesResponse,
  AllContractTemplatesResponse,
} from './types'

const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : ''

export const apiClient = axios.create({
  baseURL,
  headers: {
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginEndpoint = error.config?.url?.includes('/api/auth/login')
    if (error.response?.status === 401 && !isLoginEndpoint) {
      clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// --- Auth ---

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/auth/login', data)
  return response.data
}

export async function fetchCurrentAnalyst(): Promise<Analyst> {
  const response = await apiClient.get<Analyst>('/api/auth/me')
  return response.data
}

// --- Submissions ---

export async function fetchSubmissions(
  page: number = 1,
  size: number = 20
): Promise<PaginatedSubmissions> {
  const response = await apiClient.get<PaginatedSubmissions>('/api/submissions', {
    params: { page, size },
  })
  return response.data
}

export async function fetchSubmission(id: string): Promise<SubmissionDetail> {
  const response = await apiClient.get<SubmissionDetail>(`/api/submissions/${id}`)
  return response.data
}

export async function createSubmission(formData: FormData): Promise<{ status: string }> {
  const response = await apiClient.post<{ status: string }>('/api/submissions', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export async function reanalyseSubmission(
  id: string,
  data: ReanalyseRequest
): Promise<ReanalyseResponse> {
  const response = await apiClient.post<ReanalyseResponse>(
    `/api/submissions/${id}/reanalyse`,
    data
  )
  return response.data
}

export async function downloadReportPdf(submissionId: string, filename: string): Promise<void> {
  const response = await apiClient.get(
    `/api/submissions/${submissionId}/report.pdf`,
    { responseType: 'blob' }
  )
  const blob = new Blob([response.data], { type: 'application/pdf' })
  const url = window.URL.createObjectURL(blob)
  const anchor = window.document.createElement('a')
  anchor.href = url
  anchor.download = filename
  window.document.body.appendChild(anchor)
  anchor.click()
  window.document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
}

// --- Analysts ---

export async function fetchAnalysts(): Promise<AnalystListItem[]> {
  const response = await apiClient.get<AnalystListItem[]>('/api/analysts')
  return response.data
}

export async function createAnalyst(data: CreateAnalystRequest): Promise<Analyst> {
  const response = await apiClient.post<Analyst>('/api/analysts', data)
  return response.data
}

export async function changePassword(data: ChangePasswordRequest): Promise<void> {
  await apiClient.post('/api/auth/change-password', data)
}

// --- Models ---

export async function fetchModels(): Promise<{ models: ModelOption[] }> {
  const response = await apiClient.get<{ models: ModelOption[] }>('/api/models')
  return response.data
}

// --- Documents ---

export async function downloadDocument(
  submissionId: string,
  documentId: string,
  filename: string
): Promise<void> {
  const response = await apiClient.get(
    `/api/submissions/${submissionId}/documents/${documentId}`,
    { responseType: 'blob' }
  )

  const blob = new Blob([response.data], {
    type: response.headers['content-type'] || 'application/octet-stream',
  })

  const url = window.URL.createObjectURL(blob)
  const anchor = window.document.createElement('a')
  anchor.href = url
  anchor.download = filename
  window.document.body.appendChild(anchor)
  anchor.click()
  window.document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
}

// --- Invitations ---

export async function createInvitation(
  data: CreateInvitationRequest
): Promise<InvitationCreateResponse> {
  const response = await apiClient.post<InvitationCreateResponse>('/api/invitations', data)
  return response.data
}

export async function fetchInvitations(params?: {
  status_filter?: string
  page?: number
  size?: number
}): Promise<PaginatedInvitations> {
  const response = await apiClient.get<PaginatedInvitations>('/api/invitations', {
    params,
  })
  return response.data
}

export async function fetchInvitationByToken(token: string): Promise<InvitationPublic> {
  const response = await apiClient.get<InvitationPublic>(`/api/invitations/${token}`)
  return response.data
}

export async function cancelInvitation(id: string): Promise<void> {
  await apiClient.delete(`/api/invitations/${id}`)
}

// --- Declaration Templates ---

export async function fetchDeclarationTemplateInfo(
  providerType: string,
  entityType: string
): Promise<{ provider_type: string; entity_type: string; original_filename: string; uploaded_at: string } | null> {
  try {
    const response = await apiClient.get(
      `/api/declaration-templates/${providerType}/${entityType}`
    )
    return response.data
  } catch {
    return null
  }
}

export async function fetchAllDeclarationTemplates(): Promise<AllDeclarationTemplatesResponse> {
  const response = await apiClient.get<AllDeclarationTemplatesResponse>('/api/declaration-templates')
  return response.data
}

export async function uploadDeclarationTemplate(
  providerType: string,
  entityType: string,
  file: File
): Promise<AllDeclarationTemplatesResponse['templates'][number]> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.put(
    `/api/declaration-templates/${providerType}/${entityType}`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

export async function generateDeclarationPdf(
  providerType: string,
  entityType: string,
  partnerInfo: PartnerInfo
): Promise<Blob> {
  const response = await apiClient.post(
    `/api/declaration-templates/${providerType}/${entityType}/generate`,
    { partner_info: partnerInfo },
    { responseType: 'blob' }
  )
  return new Blob([response.data], { type: 'application/pdf' })
}

// --- Contract Templates ---

export async function fetchContractTemplateInfo(
  providerType: string,
  entityType: string
): Promise<{ provider_type: string; entity_type: string; original_filename: string; uploaded_at: string } | null> {
  try {
    const response = await apiClient.get(
      `/api/contract-templates/${providerType}/${entityType}`
    )
    return response.data
  } catch {
    return null
  }
}

export async function fetchAllContractTemplates(): Promise<AllContractTemplatesResponse> {
  const response = await apiClient.get<AllContractTemplatesResponse>('/api/contract-templates')
  return response.data
}

export async function uploadContractTemplate(
  providerType: string,
  entityType: string,
  file: File
): Promise<AllContractTemplatesResponse['templates'][number]> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.put(
    `/api/contract-templates/${providerType}/${entityType}`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

export async function generateContractPdf(
  providerType: string,
  entityType: string,
  partnerInfo: PartnerInfo
): Promise<Blob> {
  const response = await apiClient.post(
    `/api/contract-templates/${providerType}/${entityType}/generate`,
    { partner_info: partnerInfo },
    { responseType: 'blob' }
  )
  return new Blob([response.data], { type: 'application/pdf' })
}

export async function generateContractPdfFull(
  providerType: string,
  entityType: string,
  partnerInfo: PartnerInfo,
  contractData: object
): Promise<Blob> {
  const token = getToken()
  const response = await apiClient.post(
    `/api/contract-templates/${providerType}/${entityType}/generate-full`,
    { partner_info: partnerInfo, contract_data: contractData },
    {
      responseType: 'blob',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }
  )
  return new Blob([response.data], { type: 'application/pdf' })
}

export async function updateContractData(
  submissionId: string,
  contractData: object
): Promise<void> {
  const token = getToken()
  await apiClient.patch(
    `/api/submissions/${submissionId}/contract-data`,
    { contract_data: JSON.stringify(contractData) },
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }
  )
}
