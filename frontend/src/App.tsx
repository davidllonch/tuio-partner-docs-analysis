import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/ui/Toast'
import { ProtectedRoute } from './components/ui/ProtectedRoute'
import { SubmitPage } from './pages/SubmitPage'
import { ThankYouPage } from './pages/ThankYouPage'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { SubmissionDetailPage } from './pages/SubmissionDetailPage'
import { TeamPage } from './pages/TeamPage'

// QueryClient is the "state manager" for all API data fetching.
// It automatically handles caching, refetching, and loading states.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000 * 30, // consider data fresh for 30 seconds by default
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Public — partner-facing */}
            <Route path="/" element={<SubmitPage />} />
            <Route path="/thank-you" element={<ThankYouPage />} />

            {/* Public — analyst auth */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected — analyst-only */}
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
              <Route path="/team" element={<TeamPage />} />
            </Route>

            {/* Catch-all: redirect unknown URLs to the partner form */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
