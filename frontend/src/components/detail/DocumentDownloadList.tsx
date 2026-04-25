import { useRef, useState } from 'react'
import { FileText, FileImage, File, Download, Loader2, Trash2, Plus, Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { downloadDocument, deleteDocument, addDocumentToSubmission } from '../../lib/api'
import type { Document } from '../../lib/types'

interface DocumentDownloadListProps {
  submissionId: string
  documents: Document[]
  onRefetch?: () => void
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
  onRefetch,
}: DocumentDownloadListProps) {
  const [downloading, setDownloading] = useState<Record<string, boolean>>({})
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [addLabel, setAddLabel] = useState('')
  const [addFile, setAddFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { t } = useTranslation()

  const handleDownload = async (doc: Document) => {
    if (downloading[doc.id]) return
    setDownloading((prev) => ({ ...prev, [doc.id]: true }))
    try {
      await downloadDocument(submissionId, doc.id, doc.original_filename)
    } finally {
      setDownloading((prev) => ({ ...prev, [doc.id]: false }))
    }
  }

  const handleDeleteConfirm = async (docId: string) => {
    setDeleting(docId)
    try {
      await deleteDocument(submissionId, docId)
      onRefetch?.()
    } catch {
      // ignore — user can retry
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
    }
  }

  const handleAddFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setAddFile(f)
    e.target.value = ''
  }

  const handleUpload = async () => {
    if (!addFile || !addLabel.trim()) return
    setIsUploading(true)
    try {
      await addDocumentToSubmission(submissionId, addFile, addLabel.trim())
      setAddFile(null)
      setAddLabel('')
      onRefetch?.()
    } catch {
      // ignore — user can retry
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">{t('detail.documents')}</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {documents.length} {documents.length === 1 ? 'file' : 'files'} submitted
        </p>
      </div>

      {documents.length === 0 ? (
        <p className="px-5 py-6 text-sm text-gray-500 italic">{t('detail.noDocuments')}</p>
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

              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => handleDownload(doc)}
                  disabled={downloading[doc.id]}
                  aria-label={`Download ${doc.original_filename}`}
                  className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300 focus:outline-none transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {downloading[doc.id] ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  {t('detail.downloadPdf')}
                </button>

                {confirmDelete === doc.id ? (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-red-600 font-medium">{t('detail.confirmDelete')}</span>
                    <button
                      onClick={() => handleDeleteConfirm(doc.id)}
                      disabled={deleting === doc.id}
                      className="inline-flex items-center rounded-md bg-red-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-60"
                    >
                      {deleting === doc.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : t('detail.confirmDeleteYes')}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="inline-flex items-center rounded-md border border-gray-200 px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
                    >
                      {t('detail.confirmDeleteNo')}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(doc.id)}
                    aria-label={`Delete ${doc.original_filename}`}
                    className="inline-flex items-center rounded-md border border-gray-200 bg-white p-1.5 text-gray-400 hover:text-red-600 hover:border-red-200 hover:bg-red-50 focus:outline-none transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add document section */}
      <div className="px-5 py-4 border-t border-gray-100 bg-gray-50 rounded-b-xl">
        <p className="text-xs font-semibold text-gray-700 mb-2.5 flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          {t('detail.addDocument')}
        </p>
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder={t('detail.addDocumentLabel')}
            value={addLabel}
            onChange={(e) => setAddLabel(e.target.value)}
            className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Upload className="h-3.5 w-3.5" />
              {addFile ? addFile.name : t('detail.selectFile')}
            </button>
            <button
              type="button"
              onClick={handleUpload}
              disabled={!addFile || !addLabel.trim() || isUploading}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {isUploading ? t('detail.uploading') : t('detail.uploadDocument')}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.docx"
            className="hidden"
            onChange={handleAddFile}
          />
        </div>
      </div>
    </div>
  )
}
