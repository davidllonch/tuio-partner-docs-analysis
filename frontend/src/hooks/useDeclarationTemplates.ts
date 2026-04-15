import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchDeclarationTemplateInfo,
  fetchAllDeclarationTemplates,
  uploadDeclarationTemplate,
} from '../lib/api'

export function useDeclarationTemplateStatus(providerType: string, entityType: string) {
  return useQuery({
    queryKey: ['declaration-template', providerType, entityType],
    queryFn: () => fetchDeclarationTemplateInfo(providerType, entityType),
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
    mutationFn: ({
      providerType,
      entityType,
      file,
    }: {
      providerType: string
      entityType: string
      file: File
    }) => uploadDeclarationTemplate(providerType, entityType, file),
    onSuccess: (_data, { providerType, entityType }) => {
      queryClient.invalidateQueries({
        queryKey: ['declaration-template', providerType, entityType],
      })
      queryClient.invalidateQueries({ queryKey: ['declaration-templates-all'] })
    },
  })
}
