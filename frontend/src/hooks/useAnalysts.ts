import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAnalysts, createAnalyst, changePassword } from '../lib/api'
import type { CreateAnalystRequest, ChangePasswordRequest } from '../lib/types'

export function useAnalysts() {
  return useQuery({
    queryKey: ['analysts'],
    queryFn: fetchAnalysts,
    staleTime: 1000 * 60, // 1 minute
  })
}

export function useCreateAnalyst() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateAnalystRequest) => createAnalyst(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysts'] })
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => changePassword(data),
  })
}
