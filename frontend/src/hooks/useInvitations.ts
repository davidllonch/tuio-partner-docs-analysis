import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchInvitations,
  createInvitation,
  cancelInvitation,
  fetchInvitationByToken,
} from '../lib/api'
import type { CreateInvitationRequest } from '../lib/types'

export function useInvitations(params?: {
  status_filter?: string
  page?: number
  size?: number
}) {
  return useQuery({
    queryKey: ['invitations', params],
    queryFn: () => fetchInvitations(params),
  })
}

export function useCreateInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateInvitationRequest) => createInvitation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
    },
  })
}

export function useCancelInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cancelInvitation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
    },
  })
}

export function useInvitationByToken(token: string) {
  return useQuery({
    queryKey: ['invitation-token', token],
    queryFn: () => fetchInvitationByToken(token),
    retry: false, // Don't retry 404/410 errors
  })
}
