import { LoadingSpinner } from '../ui/LoadingSpinner'
import { AlertCircle } from 'lucide-react'
import type { SubmissionStatus } from '../../lib/types'

interface AIReportPanelProps {
  status: SubmissionStatus
  aiResponse: string | null
  errorMessage: string | null
}

export function AIReportPanel({ status, aiResponse, errorMessage }: AIReportPanelProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">KYC/KYB Analysis Report</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          AI-generated compliance report based on the submitted documents
        </p>
      </div>

      <div className="p-5">
        {(status === 'pending' || status === 'analysing') && (
          <div className="flex flex-col items-center justify-center py-12 gap-4 text-gray-500">
            <LoadingSpinner size="lg" />
            <p className="text-sm font-medium">Analysis in progress…</p>
            <p className="text-xs text-gray-400 text-center max-w-xs">
              The AI is reviewing the submitted documents. This page will update
              automatically when the report is ready.
            </p>
          </div>
        )}

        {status === 'error' && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-red-800">Analysis failed</p>
                {errorMessage && (
                  <p className="mt-1 text-sm text-red-700">{errorMessage}</p>
                )}
                <p className="mt-2 text-xs text-red-600">
                  You can retry using the Re-run Analysis panel on the right.
                </p>
              </div>
            </div>
          </div>
        )}

        {status === 'complete' && aiResponse && (
          <div
            className="
              whitespace-pre-wrap font-mono text-sm leading-relaxed text-gray-800
              bg-gray-50 rounded-lg border border-gray-200 p-4
              overflow-x-auto
            "
          >
            {aiResponse}
          </div>
        )}

        {status === 'complete' && !aiResponse && (
          <p className="text-sm text-gray-500 italic">
            The analysis completed but no report was generated.
          </p>
        )}
      </div>
    </div>
  )
}
