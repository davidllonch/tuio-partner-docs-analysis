import { useState, useEffect } from 'react'
import { X, Loader2, Eye, EyeOff, CheckCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useChangePassword } from '../../hooks/useAnalysts'
import axios from 'axios'

interface ChangePasswordModalProps {
  onClose: () => void
}

export function ChangePasswordModal({ onClose }: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const { t } = useTranslation()

  const mutation = useChangePassword()

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !mutation.isPending) onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose, mutation.isPending])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (newPassword.length < 8) {
      setValidationError(t('changePassword.errorShort'))
      return
    }
    if (newPassword !== confirmPassword) {
      setValidationError(t('changePassword.errorMismatch'))
      return
    }

    mutation.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setSuccess(true)
          setTimeout(onClose, 1800)
        },
        onError: (error) => {
          if (axios.isAxiosError(error) && error.response?.status === 400) {
            setValidationError(t('changePassword.errorWrong'))
          } else {
            setValidationError(t('changePassword.errorGeneric'))
          }
        },
      }
    )
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={(e) => { if (e.target === e.currentTarget && !mutation.isPending) onClose() }}
    >
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-xl border border-gray-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{t('changePassword.title')}</h2>
          <button
            onClick={() => { if (!mutation.isPending) onClose() }}
            disabled={mutation.isPending}
            className="text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-30"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {success ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <CheckCircle className="h-10 w-10 text-green-500" />
              <p className="text-sm font-medium text-gray-800">{t('changePassword.success')}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Current password */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('changePassword.current')}
                </label>
                <div className="relative">
                  <input
                    type={showCurrent ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    autoFocus
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrent((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* New password */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('changePassword.new')}
                </label>
                <div className="relative">
                  <input
                    type={showNew ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    placeholder="Minimum 8 characters"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder-gray-400"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Confirm new password */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('changePassword.confirm')}
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              {validationError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {validationError}
                </p>
              )}

              <button
                type="submit"
                disabled={mutation.isPending}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {mutation.isPending ? t('changePassword.submitting') : t('changePassword.submit')}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
