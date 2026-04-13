import * as ToastPrimitive from '@radix-ui/react-toast'
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

type ToastVariant = 'success' | 'error' | 'info'

interface ToastMessage {
  id: string
  title: string
  description?: string
  variant: ToastVariant
}

interface ToastContextValue {
  toast: (opts: { title: string; description?: string; variant?: ToastVariant }) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const VARIANT_STYLES: Record<ToastVariant, { container: string; icon: ReactNode }> = {
  success: {
    container: 'border-green-200 bg-white',
    icon: <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />,
  },
  error: {
    container: 'border-red-200 bg-white',
    icon: <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />,
  },
  info: {
    container: 'border-gray-200 bg-white',
    icon: <Info className="h-5 w-5 text-primary-600 flex-shrink-0" />,
  },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const toast = useCallback(
    ({
      title,
      description,
      variant = 'info',
    }: {
      title: string
      description?: string
      variant?: ToastVariant
    }) => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev, { id, title, description, variant }])
    },
    []
  )

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}

        {toasts.map((t) => {
          const styles = VARIANT_STYLES[t.variant]
          return (
            <ToastPrimitive.Root
              key={t.id}
              open
              onOpenChange={(open) => {
                if (!open) dismiss(t.id)
              }}
              duration={5000}
              className={`
                flex items-start gap-3 p-4 rounded-lg shadow-lg border
                data-[state=open]:animate-in data-[state=closed]:animate-out
                data-[swipe=end]:animate-out data-[state=closed]:fade-out-80
                data-[state=closed]:slide-out-to-right-full
                data-[state=open]:slide-in-from-top-full
                ${styles.container}
              `}
            >
              {styles.icon}
              <div className="flex-1 min-w-0">
                <ToastPrimitive.Title className="text-sm font-semibold text-gray-900">
                  {t.title}
                </ToastPrimitive.Title>
                {t.description && (
                  <ToastPrimitive.Description className="mt-1 text-sm text-gray-600">
                    {t.description}
                  </ToastPrimitive.Description>
                )}
              </div>
              <ToastPrimitive.Close
                aria-label="Dismiss notification"
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="h-4 w-4" />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          )
        })}

        <ToastPrimitive.Viewport className="fixed top-4 right-4 flex flex-col gap-2 w-96 max-w-[100vw] z-50" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used inside <ToastProvider>')
  }
  return ctx
}
