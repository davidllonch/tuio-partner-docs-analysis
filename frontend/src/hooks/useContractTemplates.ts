import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchContractTemplateInfo,
  fetchAllContractTemplates,
  uploadContractTemplate,
} from '../lib/api'

export function useContractTemplateStatus(providerType: string, entityType: string) {
  return useQuery({
    queryKey: ['contract-template', providerType, entityType],
    queryFn: () => fetchContractTemplateInfo(providerType, entityType),
    retry: false,
    staleTime: 30_000,
  })
}

export function useAllContractTemplates() {
  return useQuery({
    queryKey: ['contract-templates-all'],
    queryFn: fetchAllContractTemplates,
    staleTime: 30_000,
  })
}

export function useUploadContractTemplate() {
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
    }) => uploadContractTemplate(providerType, entityType, file),
    onSuccess: (_data, { providerType, entityType }) => {
      queryClient.invalidateQueries({
        queryKey: ['contract-template', providerType, entityType],
      })
      queryClient.invalidateQueries({ queryKey: ['contract-templates-all'] })
    },
  })
}
