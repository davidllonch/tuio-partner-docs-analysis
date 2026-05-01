import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronDown, KeyRound, LogOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useCurrentAnalyst, useLogout } from '../../hooks/useAuth'
import { LanguageSwitcher } from '../ui/LanguageSwitcher'
import { ChangePasswordModal } from '../ui/ChangePasswordModal'

export function AnalystHeader() {
  const { t } = useTranslation()
  const location = useLocation()
  const { data: analyst } = useCurrentAnalyst()
  const logout = useLogout()
  const [openMenu, setOpenMenu] = useState<string | null>(null)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const navRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside the nav
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (navRef.current && !navRef.current.contains(event.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isPartnersActive =
    location.pathname === '/dashboard' ||
    location.pathname === '/invitations' ||
    location.pathname === '/documentation-list' ||
    location.pathname.startsWith('/submissions/')
  const isTemplatesActive =
    location.pathname === '/declaration-templates' ||
    location.pathname === '/contract-templates'
  const isTeamActive = location.pathname === '/team'

  const toggleMenu = (menu: string) => {
    setOpenMenu((prev) => (prev === menu ? null : menu))
  }

  const dropdownItemClass =
    'block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors'
  const activeButtonClass =
    'px-3 py-1.5 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg flex items-center gap-1'
  const inactiveButtonClass =
    'px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors flex items-center gap-1'

  return (
    <>
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-6">
              <Link to="/dashboard">
                <img src="/logo-tuio.png" alt="Tuio" className="h-8" />
              </Link>

              <nav className="hidden sm:flex items-center gap-1" ref={navRef}>
                {/* Partners dropdown */}
                <div className="relative">
                  <button
                    className={isPartnersActive ? activeButtonClass : inactiveButtonClass}
                    onClick={() => toggleMenu('partners')}
                    aria-expanded={openMenu === 'partners'}
                    aria-haspopup="true"
                  >
                    {t('nav.partners')}
                    <ChevronDown
                      className={`h-3.5 w-3.5 transition-transform ${
                        openMenu === 'partners' ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {openMenu === 'partners' && (
                    <div className="absolute top-full left-0 mt-1 w-48 rounded-lg bg-white border border-gray-200 shadow-lg z-50 py-1">
                      <Link
                        to="/dashboard"
                        className={dropdownItemClass}
                        onClick={() => setOpenMenu(null)}
                      >
                        {t('nav.submissions')}
                      </Link>
                      <Link
                        to="/invitations"
                        className={dropdownItemClass}
                        onClick={() => setOpenMenu(null)}
                      >
                        {t('nav.invitations')}
                      </Link>
                      <Link
                        to="/documentation-list"
                        className={dropdownItemClass}
                        onClick={() => setOpenMenu(null)}
                      >
                        {t('nav.documentationList')}
                      </Link>
                    </div>
                  )}
                </div>

                {/* Templates dropdown */}
                <div className="relative">
                  <button
                    className={isTemplatesActive ? activeButtonClass : inactiveButtonClass}
                    onClick={() => toggleMenu('templates')}
                    aria-expanded={openMenu === 'templates'}
                    aria-haspopup="true"
                  >
                    {t('nav.templates')}
                    <ChevronDown
                      className={`h-3.5 w-3.5 transition-transform ${
                        openMenu === 'templates' ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {openMenu === 'templates' && (
                    <div className="absolute top-full left-0 mt-1 w-56 rounded-lg bg-white border border-gray-200 shadow-lg z-50 py-1">
                      <Link
                        to="/declaration-templates"
                        className={dropdownItemClass}
                        onClick={() => setOpenMenu(null)}
                      >
                        {t('nav.declarationTemplates')}
                      </Link>
                      <Link
                        to="/contract-templates"
                        className={dropdownItemClass}
                        onClick={() => setOpenMenu(null)}
                      >
                        {t('nav.contractTemplates')}
                      </Link>
                    </div>
                  )}
                </div>

                {/* Equipo — direct link, no dropdown */}
                <Link
                  to="/team"
                  className={isTeamActive ? activeButtonClass : inactiveButtonClass}
                >
                  {t('nav.team')}
                </Link>
              </nav>
            </div>

            <div className="flex items-center gap-3">
              <LanguageSwitcher />
              {analyst && (
                <span className="hidden sm:block text-sm text-gray-600">
                  {analyst.full_name}
                </span>
              )}
              <button
                onClick={() => setShowPasswordModal(true)}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                aria-label={t('auth.changePassword')}
              >
                <KeyRound className="h-4 w-4" />
                <span className="hidden sm:inline">{t('auth.changePassword')}</span>
              </button>
              <button
                onClick={logout}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                aria-label={t('auth.logout')}
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">{t('auth.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {showPasswordModal && (
        <ChangePasswordModal onClose={() => setShowPasswordModal(false)} />
      )}
    </>
  )
}
