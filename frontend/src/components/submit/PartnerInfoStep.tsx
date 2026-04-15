import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { ArrowRight } from 'lucide-react'
import type { PartnerInfo, PartnerInfoPJ, PartnerInfoPF } from '../../lib/types'

// ── Zod schemas ────────────────────────────────────────────────────────────────

const pjSchema = z.object({
  razon_social: z.string().min(1).max(255),
  cif: z.string().min(1).max(20),
  domicilio_social: z.string().min(1).max(500),
  nombre_representante: z.string().min(1).max(255),
  nif_representante: z.string().min(1).max(20),
})

const pfSchema = z.object({
  nombre_apellidos: z.string().min(1).max(255),
  nif: z.string().min(1).max(20),
  domicilio: z.string().min(1).max(500),
})

type PJFormValues = z.infer<typeof pjSchema>
type PFFormValues = z.infer<typeof pfSchema>

// ── Shared field component ─────────────────────────────────────────────────────

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string
  label: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label} <span className="text-red-500">*</span>
      </label>
      {children}
      {error && (
        <p className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

const inputClass = (hasError: boolean) =>
  `w-full rounded-lg border px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400
   shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500
   focus:border-transparent ${hasError ? 'border-red-400 bg-red-50' : 'border-gray-300 bg-white'}`

// ── PJ form ────────────────────────────────────────────────────────────────────

function PJForm({ onSubmit }: { onSubmit: (data: PartnerInfoPJ) => void }) {
  const { t } = useTranslation()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PJFormValues>({ resolver: zodResolver(pjSchema) })

  const submit = (data: PJFormValues) => {
    onSubmit({ entity_type: 'PJ', ...data })
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
      <Field id="razon_social" label={t('partnerInfo.razon_social')} error={errors.razon_social?.message}>
        <input
          id="razon_social"
          type="text"
          className={inputClass(!!errors.razon_social)}
          {...register('razon_social')}
        />
      </Field>

      <Field id="cif" label={t('partnerInfo.cif')} error={errors.cif?.message}>
        <input
          id="cif"
          type="text"
          className={inputClass(!!errors.cif)}
          {...register('cif')}
        />
      </Field>

      <Field id="domicilio_social" label={t('partnerInfo.domicilio_social')} error={errors.domicilio_social?.message}>
        <input
          id="domicilio_social"
          type="text"
          className={inputClass(!!errors.domicilio_social)}
          {...register('domicilio_social')}
        />
      </Field>

      <Field id="nombre_representante" label={t('partnerInfo.nombre_representante')} error={errors.nombre_representante?.message}>
        <input
          id="nombre_representante"
          type="text"
          className={inputClass(!!errors.nombre_representante)}
          {...register('nombre_representante')}
        />
      </Field>

      <Field id="nif_representante" label={t('partnerInfo.nif_representante')} error={errors.nif_representante?.message}>
        <input
          id="nif_representante"
          type="text"
          className={inputClass(!!errors.nif_representante)}
          {...register('nif_representante')}
        />
      </Field>

      <button
        type="submit"
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
      >
        {t('partnerInfo.continue')}
        <ArrowRight className="h-4 w-4" />
      </button>
    </form>
  )
}

// ── PF form ────────────────────────────────────────────────────────────────────

function PFForm({ onSubmit }: { onSubmit: (data: PartnerInfoPF) => void }) {
  const { t } = useTranslation()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PFFormValues>({ resolver: zodResolver(pfSchema) })

  const submit = (data: PFFormValues) => {
    onSubmit({ entity_type: 'PF', ...data })
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
      <Field id="nombre_apellidos" label={t('partnerInfo.nombre_apellidos')} error={errors.nombre_apellidos?.message}>
        <input
          id="nombre_apellidos"
          type="text"
          className={inputClass(!!errors.nombre_apellidos)}
          {...register('nombre_apellidos')}
        />
      </Field>

      <Field id="nif" label={t('partnerInfo.nif')} error={errors.nif?.message}>
        <input
          id="nif"
          type="text"
          className={inputClass(!!errors.nif)}
          {...register('nif')}
        />
      </Field>

      <Field id="domicilio" label={t('partnerInfo.domicilio')} error={errors.domicilio?.message}>
        <input
          id="domicilio"
          type="text"
          className={inputClass(!!errors.domicilio)}
          {...register('domicilio')}
        />
      </Field>

      <button
        type="submit"
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
      >
        {t('partnerInfo.continue')}
        <ArrowRight className="h-4 w-4" />
      </button>
    </form>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

interface PartnerInfoStepProps {
  entityType: 'PF' | 'PJ'
  onContinue: (info: PartnerInfo) => void
}

export function PartnerInfoStep({ entityType, onContinue }: PartnerInfoStepProps) {
  const { t } = useTranslation()

  return (
    <div className="px-8 py-7 space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">{t('partnerInfo.title')}</h2>
        <p className="text-sm text-gray-500 mt-1">{t('partnerInfo.subtitle')}</p>
      </div>

      {entityType === 'PJ' ? (
        <PJForm onSubmit={onContinue} />
      ) : (
        <PFForm onSubmit={onContinue} />
      )}
    </div>
  )
}
