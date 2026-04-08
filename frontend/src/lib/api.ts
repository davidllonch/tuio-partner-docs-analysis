import axios from 'axios'
import { getToken, clearToken } from './auth'
import type {
  PaginatedSubmissions,
  SubmissionDetail,
  LoginRequest,
  LoginResponse,
  ReanalyseRequest,
} from './types'

const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : ''

// The axios instance all requests go through.
// In development, Vite proxies /api/* to localhost:8000.
// In production, the reverse proxy handles it on the same domain.
export const apiClient = axios.create({
  baseURL,
  headers: {
    Accept: 'application/json',
  },
})

// Request interceptor: attach the JWT token if one exists in localStorage
apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: on 401 (unauthorized), clear the stored token and
// send the user back to the login page. This handles expired/invalid tokens
// automatically without needing to check manually in every component.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
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

export async function fetchCurrentAnalyst() {
  const response = await apiClient.get('/api/auth/me')
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

export async function createSubmission(formData: FormData): Promise<{ id: string }> {
  const response = await apiClient.post<{ id: string }>('/api/submissions', formData, {
    headers: {
      // Let axios set the correct multipart boundary automatically
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export async function reanalyseSubmission(
  id: string,
  data: ReanalyseRequest
): Promise<SubmissionDetail> {
  const response = await apiClient.post<SubmissionDetail>(
    `/api/submissions/${id}/reanalyse`,
    data
  )
  return response.data
}

// --- Documents ---

// Downloads a document programmatically using axios (with auth header)
// and triggers a browser download via a temporary anchor element.
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
