import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchSubmissions,
  fetchSubmission,
  reanalyseSubmission,
  fetchModels,
} from '../lib/api'
import type { PaginatedSubmissions, SubmissionDetail, ReanalyseRequest, ReanalyseResponse, ModelOption } from '../lib/types'

export function useSubmissions(page: number = 1, size: number = 20) {
  return useQuery<PaginatedSubmissions>({
    queryKey: ['submissions', page, size],
    queryFn: () => fetchSubmissions(page, size),
    staleTime: 1000 * 30, // refetch after 30 seconds
    placeholderData: (previousData) => previousData,
  })
}

export function useSubmission(id: string) {
  return useQuery<SubmissionDetail>({
    queryKey: ['submissions', id],
    queryFn: () => fetchSubmission(id),
    // For submissions that are still processing, poll every 10 seconds
    // so the analyst sees the result appear automatically
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      return data.status === 'pending' || data.status === 'analysing' ? 10_000 : false
    },
    staleTime: 1000 * 10,
  })
}

export function useModels() {
  return useQuery<{ models: ModelOption[] }>({
    queryKey: ['models'],
    queryFn: fetchModels,
    staleTime: 1000 * 60 * 5, // 5 minutes — model list rarely changes
  })
}

export function useReanalyse(submissionId: string) {
  const queryClient = useQueryClient()

  return useMutation<ReanalyseResponse, Error, ReanalyseRequest>({
    mutationFn: (data: ReanalyseRequest) => reanalyseSubmission(submissionId, data),
    onSuccess: () => {
      // Invalidate and refetch the submission so the UI shows the new AI report
      queryClient.invalidateQueries({ queryKey: ['submissions', submissionId] })
      // Also invalidate the list so the status badge updates on the dashboard
      queryClient.invalidateQueries({ queryKey: ['submissions'] })
    },
  })
}
