import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AlertCircle, Building2, User, MapPin, Globe } from 'lucide-react'
import { useInvitationByToken } from '../hooks/useInvitations'
import { StructuredDocumentUploader, type StructuredSubmitPayload } from '../components/submit/StructuredDocumentUploader'
import { PartnerInfoStep } from '../components/submit/PartnerInfoStep'
import { getRequiredSlots } from '../lib/documentRequirements'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'
import { createSubmission } from '../lib/api'
import { PROVIDER_TYPE_LABELS, ENTITY_TYPE_LABELS } from '../lib/types'
import type { PartnerInfo } from '../lib/types'

export function InvitePage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { data: invitation, isLoading, isError, error } = useInvitationByToken(token!)
  const [partnerInfo, setPartnerInfo] = useState<PartnerInfo | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Determine error type from status code
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const errorStatus = (error as any)?.response?.status
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const errorDetail = (error as any)?.response?.data?.detail

  const handleStructuredSubmit = async (payload: StructuredSubmitPayload) => {
    if (!invitation) return
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const formData = new FormData()
      formData.append('invitation_token', token!)
      formData.append('provider_name', invitation.provider_name)
      formData.append('provider_type', invitation.provider_type)
      formData.append('entity_type', invitation.entity_type)
      formData.append('country', invitation.country)

      payload.files.forEach(({ file, label }) => {
        formData.append('files', file)
        formData.append('labels', label)
      })

      if (payload.notApplicableSlots.length > 0) {
        formData.append('not_applicable_slots', JSON.stringify(payload.notApplicableSlots))
      }

      if (partnerInfo) {
        formData.append('partner_info', JSON.stringify(partnerInfo))
      }

      await createSubmission(formData)
      navigate('/thank-you')
    } catch {
      setSubmitError(t('invite.submitError'))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderError = () => {
    let message = t('invite.invalidLink')
    if (errorStatus === 410) {
      if (errorDetail === 'already_used') {
        message = t('invite.alreadyUsed')
      } else {
        message = t('invite.expired')
      }
    }
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-10 max-w-md w-full">
          <AlertCircle className="h-12 w-12 text-amber-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">{t('invite.errorTitle')}</h2>
          <p className="text-sm text-gray-500">{message}</p>
        </div>
      </div>
    )
  }

  // Step indicator
  const StepIndicator = () => (
    <div className="flex items-center gap-2 px-8 pt-6 pb-4 border-b border-gray-100">
      <div className={`flex items-center gap-1.5 text-xs font-medium ${partnerInfo === null ? 'text-primary-600' : 'text-gray-400'}`}>
        <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${partnerInfo === null ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-500'}`}>1</span>
        {t('invite.step1')}
      </div>
      <div className="flex-1 h-px bg-gray-200" />
      <div className={`flex items-center gap-1.5 text-xs font-medium ${partnerInfo !== null ? 'text-primary-600' : 'text-gray-400'}`}>
        <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${partnerInfo !== null ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-500'}`}>2</span>
        {t('invite.step2')}
      </div>
    </div>
  )

  return (
    <div className="relative min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-3">
          <img src="/logo-tuio.png" alt="Tuio" className="h-8" />
          <LanguageSwitcher />
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="w-full max-w-2xl">
          {isLoading && (
            <div className="flex items-center justify-center py-24">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {isError && renderError()}

          {invitation && invitation.status === 'pending' && (
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              {/* Card header */}
              <div className="px-8 pt-8 pb-6 border-b border-gray-100">
                <h1 className="text-xl font-bold text-gray-900">
                  {t('submit.title')}
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                  {t('invite.context')}
                </p>
              </div>

              {/* Step indicator */}
              <StepIndicator />

              {/* Company info card (read-only) */}
              <div className="px-8 pt-5">
                <div className="rounded-xl bg-gray-50 border border-gray-200 p-5">
                  <h2 className="text-sm font-semibold text-gray-700 mb-3">
                    {t('invite.companyInfo')}
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <Building2 className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      <span className="font-medium">{invitation.provider_name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <Globe className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      <span>{PROVIDER_TYPE_LABELS[invitation.provider_type]}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <User className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      <span>{ENTITY_TYPE_LABELS[invitation.entity_type]}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <MapPin className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      <span>{invitation.country}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error banner */}
              {submitError && (
                <div className="px-8 pt-4">
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700">{submitError}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 1: Partner info form */}
              {partnerInfo === null && (
                <PartnerInfoStep
                  entityType={invitation.entity_type}
                  providerType={invitation.provider_type}
                  onContinue={setPartnerInfo}
                />
              )}

              {/* Step 2: Document uploader */}
              {partnerInfo !== null && (
                <div className="px-8 py-7">
                  <StructuredDocumentUploader
                    slots={getRequiredSlots(invitation.provider_type, invitation.entity_type)}
                    providerType={invitation.provider_type}
                    entityType={invitation.entity_type}
                    partnerInfo={partnerInfo}
                    onSubmit={handleStructuredSubmit}
                    isSubmitting={isSubmitting}
                  />
                </div>
              )}
            </div>
          )}

          {/* Footer */}
          <p className="text-center text-xs text-gray-400 mt-5">
            {t('invite.privacyNote')}
          </p>
        </div>
      </main>

      {/* Full-screen loading overlay */}
      {isSubmitting && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/90 backdrop-blur-sm"
          role="status"
          aria-live="polite"
        >
          <LoadingSpinner size="lg" />
          <p className="mt-5 text-base font-semibold text-gray-800">
            {t('submit.submitting')}
          </p>
        </div>
      )}
    </div>
  )
}
