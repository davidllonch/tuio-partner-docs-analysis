import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useTranslation } from 'react-i18next'
import {
  Upload,
  FileText,
  FileImage,
  File,
  X,
  AlertCircle,
} from 'lucide-react'

export interface FileEntry {
  id: string
  file: File
  label: string
}

interface DocumentUploaderProps {
  files: FileEntry[]
  onChange: (files: FileEntry[]) => void
  onBack?: () => void
  onSubmit: () => void
  isSubmitting: boolean
  hideBackButton?: boolean
}

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024 // 20 MB
const MAX_TOTAL_SIZE_BYTES = 100 * 1024 * 1024 // 100 MB

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileIcon(mimeType: string) {
  if (mimeType === 'application/pdf')
    return <FileText className="h-5 w-5 text-red-500" />
  if (mimeType.startsWith('image/'))
    return <FileImage className="h-5 w-5 text-blue-500" />
  return <File className="h-5 w-5 text-gray-500" />
}

export function DocumentUploader({
  files,
  onChange,
  onBack,
  onSubmit,
  isSubmitting,
  hideBackButton = false,
}: DocumentUploaderProps) {
  const [rejectionMessages, setRejectionMessages] = useState<string[]>([])
  const { t } = useTranslation()

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setRejectionMessages([])
      const newEntries: FileEntry[] = acceptedFiles.map((file) => ({
        id: crypto.randomUUID(),
        file,
        label: '',
      }))
      onChange([...files, ...newEntries])
    },
    [files, onChange]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE_BYTES,
    onDropRejected: (rejectedFiles) => {
      const messages = rejectedFiles.flatMap((r) =>
        r.errors.map((e) => {
          if (e.code === 'file-too-large') {
            return `"${r.file.name}" exceeds the 20 MB limit.`
          }
          if (e.code === 'file-invalid-type') {
            return `"${r.file.name}" is not an accepted file type (PDF, JPEG, PNG, DOCX).`
          }
          return `"${r.file.name}": ${e.message}`
        })
      )
      setRejectionMessages(messages)
    },
  })

  const removeFile = (id: string) => {
    onChange(files.filter((f) => f.id !== id))
  }

  const updateLabel = (id: string, label: string) => {
    onChange(files.map((f) => (f.id === id ? { ...f, label } : f)))
  }

  const totalBytes = files.reduce((sum, f) => sum + f.file.size, 0)
  const totalExceeded = totalBytes > MAX_TOTAL_SIZE_BYTES
  const hasEmptyLabel = files.some((f) => f.label.trim() === '')
  const canSubmit = files.length > 0 && !hasEmptyLabel && !totalExceeded && !isSubmitting

  return (
    <div className="space-y-5">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`
          relative rounded-xl border-2 border-dashed p-8 text-center cursor-pointer
          transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500
          ${
            isDragActive
              ? 'border-primary-400 bg-primary-50'
              : 'border-gray-300 bg-gray-50 hover:border-primary-400 hover:bg-primary-50'
          }
        `}
        tabIndex={0}
        role="button"
        aria-label="File upload area — click or drag files here"
      >
        <input {...getInputProps()} />
        <Upload
          className={`mx-auto h-10 w-10 mb-3 ${
            isDragActive ? 'text-primary-500' : 'text-gray-400'
          }`}
        />
        <p className="text-sm font-medium text-gray-700">
          {isDragActive ? 'Drop files here' : t('submit.dragDrop')}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          {t('submit.fileTypes')}
        </p>
      </div>

      {/* Rejection errors */}
      {rejectionMessages.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
            <ul className="space-y-0.5">
              {rejectionMessages.map((msg, i) => (
                <li key={i} className="text-xs text-red-700">
                  {msg}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-3">
          {files.map((entry) => (
            <li
              key={entry.id}
              className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-3"
            >
              <span className="mt-0.5 flex-shrink-0">
                {getFileIcon(entry.file.type)}
              </span>

              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {entry.file.name}
                  </p>
                  <span className="text-xs text-gray-500 whitespace-nowrap flex-shrink-0">
                    {formatBytes(entry.file.size)}
                  </span>
                </div>

                <div>
                  <input
                    type="text"
                    value={entry.label}
                    onChange={(e) => updateLabel(entry.id, e.target.value)}
                    placeholder='Document label (e.g. "Certificate of incorporation")'
                    aria-label={`Label for ${entry.file.name}`}
                    className={`
                      w-full rounded-md border px-2.5 py-1.5 text-sm
                      placeholder-gray-400 transition-colors
                      focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                      ${
                        entry.label.trim() === ''
                          ? 'border-amber-300 bg-amber-50'
                          : 'border-gray-300 bg-white'
                      }
                    `}
                  />
                  {entry.label.trim() === '' && (
                    <p className="mt-0.5 text-xs text-amber-600">
                      Please describe this document
                    </p>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => removeFile(entry.id)}
                aria-label={`Remove ${entry.file.name}`}
                className="flex-shrink-0 mt-0.5 p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Size counter */}
      {files.length > 0 && (
        <p
          className={`text-xs ${
            totalExceeded ? 'text-red-600 font-medium' : 'text-gray-500'
          }`}
        >
          {files.length} {files.length === 1 ? 'file' : 'files'} ·{' '}
          {formatBytes(totalBytes)} / {formatBytes(MAX_TOTAL_SIZE_BYTES)} total max
          {totalExceeded && ' — Total size exceeds the 100 MB limit'}
        </p>
      )}

      {/* Navigation buttons */}
      <div className="flex gap-3 pt-2">
        {!hideBackButton && (
          <button
            type="button"
            onClick={onBack}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
                clipRule="evenodd"
              />
            </svg>
            Back
          </button>
        )}

        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? t('submit.submitting') : t('submit.submit')}
        </button>
      </div>
    </div>
  )
}
