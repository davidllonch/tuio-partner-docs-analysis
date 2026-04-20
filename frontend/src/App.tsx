import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/ui/Toast'
import { ProtectedRoute } from './components/ui/ProtectedRoute'
import { ThankYouPage } from './pages/ThankYouPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { SubmissionDetailPage } from './pages/SubmissionDetailPage'
import { TeamPage } from './pages/TeamPage'
import { InvitationsPage } from './pages/InvitationsPage'
import { InvitePage } from './pages/InvitePage'
import { DeclarationTemplatesPage } from './pages/DeclarationTemplatesPage'
import { ContractTemplatesPage } from './pages/ContractTemplatesPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000 * 30,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Public — root landing */}
            <Route path="/" element={<LandingPage />} />

            {/* Public — partner-facing */}
            <Route path="/invite/:token" element={<InvitePage />} />
            <Route path="/thank-you" element={<ThankYouPage />} />

            {/* Public — analyst auth */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected — analyst-only */}
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
              <Route path="/team" element={<TeamPage />} />
              <Route path="/invitations" element={<InvitationsPage />} />
              <Route path="/declaration-templates" element={<DeclarationTemplatesPage />} />
              <Route path="/contract-templates" element={<ContractTemplatesPage />} />
            </Route>

            {/* Catch-all: redirect unknown URLs to login */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
