import { useState } from 'react'
import { FileText, FileImage, File, Download, Loader2 } from 'lucide-react'
import { downloadDocument } from '../../lib/api'
import type { Document } from '../../lib/types'

interface DocumentDownloadListProps {
  submissionId: string
  documents: Document[]
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileIcon(mimeType: string) {
  if (mimeType === 'application/pdf')
    return <FileText className="h-4 w-4 text-red-500 flex-shrink-0" />
  if (mimeType.startsWith('image/'))
    return <FileImage className="h-4 w-4 text-blue-500 flex-shrink-0" />
  return <File className="h-4 w-4 text-gray-400 flex-shrink-0" />
}

export function DocumentDownloadList({
  submissionId,
  documents,
}: DocumentDownloadListProps) {
  const [downloading, setDownloading] = useState<Record<string, boolean>>({})

  const handleDownload = async (doc: Document) => {
    if (downloading[doc.id]) return
    setDownloading((prev) => ({ ...prev, [doc.id]: true }))
    try {
      await downloadDocument(submissionId, doc.id, doc.original_filename)
    } finally {
      setDownloading((prev) => ({ ...prev, [doc.id]: false }))
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">Uploaded Documents</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {documents.length} {documents.length === 1 ? 'file' : 'files'} submitted
        </p>
      </div>

      {documents.length === 0 ? (
        <p className="px-5 py-6 text-sm text-gray-500 italic">No documents found.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-start gap-3 px-5 py-3.5">
              <span className="mt-0.5">{getFileIcon(doc.mime_type)}</span>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 leading-tight">
                  {doc.user_label}
                </p>
                <p className="text-xs text-gray-500 mt-0.5 truncate">
                  {doc.original_filename}
                </p>
                <p className="text-xs text-gray-400">{formatBytes(doc.size_bytes)}</p>
              </div>

              <button
                onClick={() => handleDownload(doc)}
                disabled={downloading[doc.id]}
                aria-label={`Download ${doc.original_filename}`}
                className="flex-shrink-0 inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {downloading[doc.id] ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
