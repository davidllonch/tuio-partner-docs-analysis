import { useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LoadingSpinner } from '../ui/LoadingSpinner'
import { AlertCircle, Download } from 'lucide-react'
import type { SubmissionStatus } from '../../lib/types'

interface AIReportPanelProps {
  status: SubmissionStatus
  aiResponse: string | null
  errorMessage: string | null
  providerName?: string
}

// Custom Tailwind styles for each Markdown element.
// This gives the AI report clean, readable formatting without
// needing an extra CSS plugin.
const md = {
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-lg font-bold text-gray-900 mt-6 mb-3 pb-2 border-b border-gray-200 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-base font-semibold text-gray-800 mt-5 mb-2">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-sm font-semibold text-gray-700 mt-4 mb-1">{children}</h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="text-sm text-gray-700 mb-3 leading-relaxed">{children}</p>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-gray-600">{children}</em>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc list-outside ml-5 mb-3 space-y-1 text-sm text-gray-700">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal list-outside ml-5 mb-3 space-y-1 text-sm text-gray-700">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-sm text-gray-700 leading-relaxed">{children}</li>
  ),
  hr: () => <hr className="border-gray-200 my-5" />,
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-4 border-indigo-200 pl-4 italic text-gray-600 mb-3 text-sm">
      {children}
    </blockquote>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="bg-gray-100 rounded px-1 py-0.5 text-xs font-mono text-gray-800">
      {children}
    </code>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto mb-4 rounded-lg border border-gray-200">
      <table className="min-w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="border-b border-gray-200 px-4 py-2 text-left font-semibold text-gray-700 text-xs uppercase tracking-wide">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border-b border-gray-100 px-4 py-2 text-gray-700 text-sm">{children}</td>
  ),
  tr: ({ children }: { children?: React.ReactNode }) => (
    <tr className="hover:bg-gray-50 transition-colors">{children}</tr>
  ),
}

// Styles injected into the print window so the PDF looks clean and professional.
const PRINT_STYLES = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.6;
    color: #111827;
    max-width: 780px;
    margin: 32px auto;
    padding: 0 24px;
  }
  h1 { font-size: 18px; font-weight: 700; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin: 24px 0 12px; }
  h2 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; color: #1f2937; }
  h3 { font-size: 13px; font-weight: 600; margin: 16px 0 6px; color: #374151; }
  p  { margin-bottom: 10px; }
  ul, ol { margin: 0 0 10px 20px; }
  li { margin-bottom: 4px; }
  hr { border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }
  blockquote { border-left: 3px solid #c7d2fe; padding-left: 12px; color: #6b7280; margin-bottom: 10px; font-style: italic; }
  code { background: #f3f4f6; border-radius: 3px; padding: 1px 5px; font-family: monospace; font-size: 11px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th, td { border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left; }
  th { background: #f9fafb; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  strong { font-weight: 600; }
`

export function AIReportPanel({ status, aiResponse, errorMessage, providerName }: AIReportPanelProps) {
  const reportRef = useRef<HTMLDivElement>(null)

  const handleDownloadPDF = () => {
    if (!reportRef.current) return

    const title = providerName ? `Informe KYC — ${providerName}` : 'Informe KYC/KYB'
    const printWindow = window.open('', '_blank')
    if (!printWindow) return

    printWindow.document.write(`
      <!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="UTF-8" />
        <title>${title}</title>
        <style>${PRINT_STYLES}</style>
      </head>
      <body>${reportRef.current.innerHTML}</body>
      </html>
    `)
    printWindow.document.close()

    // Small delay to ensure styles are applied before the print dialog opens
    setTimeout(() => {
      printWindow.print()
      printWindow.close()
    }, 250)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">KYC/KYB Analysis Report</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            AI-generated compliance report based on the submitted documents
          </p>
        </div>

        {status === 'complete' && aiResponse && (
          <button
            onClick={handleDownloadPDF}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download PDF
          </button>
        )}
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
          <div className="min-w-0" ref={reportRef}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={md}
            >
              {aiResponse}
            </ReactMarkdown>
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
