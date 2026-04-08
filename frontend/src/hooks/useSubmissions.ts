import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchSubmissions,
  fetchSubmission,
  reanalyseSubmission,
} from '../lib/api'
import type { PaginatedSubmissions, SubmissionDetail, ReanalyseRequest } from '../lib/types'

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

export function useReanalyse(submissionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ReanalyseRequest) => reanalyseSubmission(submissionId, data),
    onSuccess: (updatedSubmission) => {
      // Update the cached detail immediately so the UI reflects the new analysis
      queryClient.setQueryData<SubmissionDetail>(
        ['submissions', submissionId],
        updatedSubmission
      )
      // Also invalidate the list so the status badge updates on the dashboard
      queryClient.invalidateQueries({ queryKey: ['submissions'] })
    },
  })
}
