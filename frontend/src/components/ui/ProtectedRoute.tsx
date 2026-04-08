import { Navigate, Outlet } from 'react-router-dom'
import { isLoggedIn } from '../../lib/auth'

/**
 * Wraps any route that requires the analyst to be logged in.
 * If no token is found in localStorage, redirects to /login.
 * The `replace` prop means the login page won't appear in the browser history
 * — so pressing "back" after logging in won't send the user back to /login.
 */
export function ProtectedRoute() {
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
