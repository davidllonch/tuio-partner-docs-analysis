import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchDeclarationTemplateInfo,
  fetchAllDeclarationTemplates,
  uploadDeclarationTemplate,
} from '../lib/api'

export function useDeclarationTemplateStatus(providerType: string) {
  return useQuery({
    queryKey: ['declaration-template', providerType],
    queryFn: () => fetchDeclarationTemplateInfo(providerType),
    retry: false,
    staleTime: 30_000,
  })
}

export function useAllDeclarationTemplates() {
  return useQuery({
    queryKey: ['declaration-templates-all'],
    queryFn: fetchAllDeclarationTemplates,
    staleTime: 30_000,
  })
}

export function useUploadDeclarationTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ providerType, file }: { providerType: string; file: File }) =>
      uploadDeclarationTemplate(providerType, file),
    onSuccess: (_data, { providerType }) => {
      queryClient.invalidateQueries({ queryKey: ['declaration-template', providerType] })
      queryClient.invalidateQueries({ queryKey: ['declaration-templates-all'] })
    },
  })
}
