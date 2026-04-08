import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { login, fetchCurrentAnalyst } from '../lib/api'
import { setToken, clearToken, isLoggedIn } from '../lib/auth'
import type { LoginRequest, Analyst } from '../lib/types'

export function useCurrentAnalyst() {
  return useQuery<Analyst>({
    queryKey: ['analyst', 'me'],
    queryFn: fetchCurrentAnalyst,
    // Only fetch if there's a token stored — avoids an unnecessary 401
    enabled: isLoggedIn(),
    staleTime: 1000 * 60 * 5, // consider fresh for 5 minutes
    retry: false,
  })
}

export function useLogin() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: LoginRequest) => login(data),
    onSuccess: (response) => {
      setToken(response.access_token)
      // Pre-populate the analyst cache so the dashboard can show the name immediately
      queryClient.setQueryData(['analyst', 'me'], response.analyst)
      navigate('/dashboard')
    },
  })
}

export function useLogout() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  return () => {
    clearToken()
    queryClient.clear()
    navigate('/login')
  }
}
