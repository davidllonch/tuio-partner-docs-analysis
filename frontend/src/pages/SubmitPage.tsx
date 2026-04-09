import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ProviderInfoForm, type ProviderInfoFormValues } from '../components/submit/ProviderInfoForm'
import { DocumentUploader, type FileEntry } from '../components/submit/DocumentUploader'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { createSubmission } from '../lib/api'
import { AlertCircle } from 'lucide-react'

type Step = 1 | 2

export function SubmitPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>(1)
  const [providerInfo, setProviderInfo] = useState<ProviderInfoFormValues | null>(null)
  const [files, setFiles] = useState<FileEntry[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const handleInfoSubmit = (values: ProviderInfoFormValues) => {
    setProviderInfo(values)
    setStep(2)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSubmit = async () => {
    if (!providerInfo) return
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const formData = new FormData()
      formData.append('provider_name', providerInfo.provider_name)
      formData.append('provider_type', providerInfo.provider_type)
      formData.append('entity_type', providerInfo.entity_type)
      formData.append('country', providerInfo.country)

      files.forEach((entry) => {
        formData.append('files', entry.file)
        formData.append('labels', entry.label)
      })

      await createSubmission(formData)
      navigate('/thank-you')
    } catch {
      setSubmitError(
        'Something went wrong. Please try again or contact support at legal@tuio.com.'
      )
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">T</span>
          </div>
          <span className="text-sm font-semibold text-gray-700">Tuio</span>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="w-full max-w-2xl">
          {/* Card */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Card header */}
            <div className="px-8 pt-8 pb-6 border-b border-gray-100">
              <h1 className="text-xl font-bold text-gray-900">
                Partner Documentation Submission
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Please provide the required information and documents for KYC/KYB compliance review.
              </p>

              {/* Step indicator */}
              <div className="flex items-center gap-4 mt-5">
                {/* Step 1 */}
                <div className="flex items-center gap-2">
                  <div
                    className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                      step >= 1
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {step > 1 ? (
                      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      '1'
                    )}
                  </div>
                  <span
                    className={`text-sm font-medium ${
                      step === 1 ? 'text-indigo-600' : 'text-gray-500'
                    }`}
                  >
                    Provider Information
                  </span>
                </div>

                <div className="flex-1 h-px bg-gray-200" />

                {/* Step 2 */}
                <div className="flex items-center gap-2">
                  <div
                    className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                      step >= 2
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    2
                  </div>
                  <span
                    className={`text-sm font-medium ${
                      step === 2 ? 'text-indigo-600' : 'text-gray-500'
                    }`}
                  >
                    Documentation
                  </span>
                </div>
              </div>

              {/* Step label */}
              <p className="mt-3 text-xs text-gray-400">
                Step {step} of 2
              </p>
            </div>

            {/* Card body */}
            <div className="px-8 py-7">
              {/* Submission error */}
              {submitError && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-700">{submitError}</p>
                  </div>
                </div>
              )}

              {step === 1 && (
                <ProviderInfoForm
                  defaultValues={providerInfo ?? undefined}
                  onSubmit={handleInfoSubmit}
                />
              )}

              {step === 2 && (
                <DocumentUploader
                  files={files}
                  onChange={setFiles}
                  onBack={() => setStep(1)}
                  onSubmit={handleSubmit}
                  isSubmitting={isSubmitting}
                />
              )}
            </div>
          </div>

          {/* Footer note */}
          <p className="text-center text-xs text-gray-400 mt-5">
            Your information is handled in accordance with applicable data protection regulations.
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
            Sending your documentation…
          </p>
        </div>
      )}
    </div>
  )
}
