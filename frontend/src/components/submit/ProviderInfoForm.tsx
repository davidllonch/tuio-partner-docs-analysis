import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { ProviderType, EntityType } from '../../lib/types'

const schema = z.object({
  provider_name: z.string().min(1, 'Provider name is required').max(255),
  provider_type: z.enum(
    ['correduria_seguros', 'agencia_seguros', 'colaborador_externo', 'generador_leads'],
    { required_error: 'Please select a provider type' }
  ),
  entity_type: z.enum(['PJ', 'PF'], { required_error: 'Please select an entity type' }),
  country: z.string().min(1, 'Country is required').max(100),
})

export type ProviderInfoFormValues = z.infer<typeof schema>

interface ProviderInfoFormProps {
  defaultValues?: Partial<ProviderInfoFormValues>
  onSubmit: (values: ProviderInfoFormValues) => void
}

const PROVIDER_TYPE_OPTIONS: { value: ProviderType; label: string }[] = [
  { value: 'correduria_seguros', label: 'Correduría de Seguros' },
  { value: 'agencia_seguros', label: 'Agencia de Seguros' },
  { value: 'colaborador_externo', label: 'Colaborador Externo' },
  { value: 'generador_leads', label: 'Generador de Leads' },
]

const ENTITY_TYPE_OPTIONS: { value: EntityType; label: string; description: string }[] =
  [
    {
      value: 'PJ',
      label: 'Legal Entity',
      description: 'Persona Jurídica — a company or organisation',
    },
    {
      value: 'PF',
      label: 'Physical Person',
      description: 'Persona Física — an individual',
    },
  ]

export function ProviderInfoForm({ defaultValues, onSubmit }: ProviderInfoFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<ProviderInfoFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      entity_type: 'PJ',
      ...defaultValues,
    },
  })

  const entityType = watch('entity_type')

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      {/* Provider Name */}
      <div>
        <label
          htmlFor="provider_name"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Provider Name <span className="text-red-500">*</span>
        </label>
        <input
          id="provider_name"
          type="text"
          autoComplete="organization"
          placeholder="Company or individual name"
          className={`
            w-full rounded-lg border px-3 py-2.5 text-sm text-gray-900
            placeholder-gray-400 shadow-sm transition-colors
            focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
            ${errors.provider_name ? 'border-red-400 bg-red-50' : 'border-gray-300 bg-white'}
          `}
          {...register('provider_name')}
        />
        {errors.provider_name && (
          <p className="mt-1 text-xs text-red-600" role="alert">
            {errors.provider_name.message}
          </p>
        )}
      </div>

      {/* Provider Type */}
      <div>
        <label
          htmlFor="provider_type"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Provider Type <span className="text-red-500">*</span>
        </label>
        <select
          id="provider_type"
          className={`
            w-full rounded-lg border px-3 py-2.5 text-sm text-gray-900
            shadow-sm transition-colors bg-white
            focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
            ${errors.provider_type ? 'border-red-400 bg-red-50' : 'border-gray-300'}
          `}
          {...register('provider_type')}
        >
          <option value="">Select a provider type…</option>
          {PROVIDER_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {errors.provider_type && (
          <p className="mt-1 text-xs text-red-600" role="alert">
            {errors.provider_type.message}
          </p>
        )}
      </div>

      {/* Entity Type */}
      <div>
        <span className="block text-sm font-medium text-gray-700 mb-2">
          Entity Type <span className="text-red-500">*</span>
        </span>
        <div className="grid grid-cols-2 gap-3">
          {ENTITY_TYPE_OPTIONS.map((opt) => {
            const isSelected = entityType === opt.value
            return (
              <label
                key={opt.value}
                className={`
                  relative flex cursor-pointer rounded-lg border p-4 transition-colors
                  ${
                    isSelected
                      ? 'border-indigo-600 bg-indigo-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }
                `}
              >
                <input
                  type="radio"
                  value={opt.value}
                  className="sr-only"
                  {...register('entity_type')}
                />
                <div>
                  <p
                    className={`text-sm font-medium ${
                      isSelected ? 'text-indigo-900' : 'text-gray-900'
                    }`}
                  >
                    {opt.label}
                  </p>
                  <p
                    className={`text-xs mt-0.5 ${
                      isSelected ? 'text-indigo-600' : 'text-gray-500'
                    }`}
                  >
                    {opt.description}
                  </p>
                </div>
                {isSelected && (
                  <span className="absolute top-2 right-2 h-5 w-5 rounded-full bg-indigo-600 flex items-center justify-center">
                    <svg
                      className="h-3 w-3 text-white"
                      fill="currentColor"
                      viewBox="0 0 12 12"
                    >
                      <path d="M3.707 5.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4a1 1 0 00-1.414-1.414L5 6.586 3.707 5.293z" />
                    </svg>
                  </span>
                )}
              </label>
            )
          })}
        </div>
        {errors.entity_type && (
          <p className="mt-1 text-xs text-red-600" role="alert">
            {errors.entity_type.message}
          </p>
        )}
      </div>

      {/* Country */}
      <div>
        <label
          htmlFor="country"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Country of Domicile <span className="text-red-500">*</span>
        </label>
        <input
          id="country"
          type="text"
          autoComplete="country-name"
          placeholder="Country of domicile"
          className={`
            w-full rounded-lg border px-3 py-2.5 text-sm text-gray-900
            placeholder-gray-400 shadow-sm transition-colors
            focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
            ${errors.country ? 'border-red-400 bg-red-50' : 'border-gray-300 bg-white'}
          `}
          {...register('country')}
        />
        {errors.country && (
          <p className="mt-1 text-xs text-red-600" role="alert">
            {errors.country.message}
          </p>
        )}
      </div>

      <button
        type="submit"
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors"
      >
        Next
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>
    </form>
  )
}
