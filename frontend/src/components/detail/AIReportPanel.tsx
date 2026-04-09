import { useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LoadingSpinner } from '../ui/LoadingSpinner'
import { AlertCircle, Download, Loader2 } from 'lucide-react'
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


export function AIReportPanel({ status, aiResponse, errorMessage, providerName }: AIReportPanelProps) {
  const reportRef = useRef<HTMLDivElement>(null)
  const [isGenerating, setIsGenerating] = useState(false)

  const handleDownloadPDF = async () => {
    if (!reportRef.current || isGenerating) return
    setIsGenerating(true)

    try {
      // Lazy-load the libraries only when needed (keeps initial bundle small)
      const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
        import('jspdf'),
        import('html2canvas'),
      ])

      // Render the report div to a canvas at 2× resolution for crisp text
      const canvas = await html2canvas(reportRef.current, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
      })

      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })

      const pageW = pdf.internal.pageSize.getWidth()
      const pageH = pdf.internal.pageSize.getHeight()
      const margin = 12 // mm
      const printW = pageW - margin * 2
      const printH = (canvas.height * printW) / canvas.width

      // Paginate: if the content is taller than one page, split across pages
      let yOffset = 0
      while (yOffset < printH) {
        if (yOffset > 0) pdf.addPage()
        pdf.addImage(imgData, 'PNG', margin, margin - yOffset, printW, printH)
        yOffset += pageH - margin * 2
      }

      const safeName = (providerName ?? '').replace(/[^\w\s\-]/g, '').trim()
      const filename = safeName ? `Informe_KYC_${safeName}.pdf` : 'Informe_KYC.pdf'
      pdf.save(filename)
    } finally {
      setIsGenerating(false)
    }
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
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isGenerating
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Generant…</>
              : <><Download className="h-3.5 w-3.5" />Download PDF</>
            }
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
