import { Search } from 'lucide-react'
import { Link, NavLink } from 'react-router'

import { AccountMenu } from './AccountMenu'
import { useOpenPalette } from './paletteContext'

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

/** The sheet's top edge: wordmark, the main places, the palette and the account menu. */
export function AppHeader() {
  const openPalette = useOpenPalette()
  return (
    <header className="app-header">
      <Link to="/documents" className="app-header__wordmark" aria-label="Inkstep, your documents">
        <span className="app-header__mark" aria-hidden="true" />
        Inkstep
      </Link>
      <nav aria-label="Main" className="app-header__nav">
        <NavLink to="/documents" end className="tag">
          Documents
        </NavLink>
        <NavLink to="/notifications" className="tag">
          Notifications
        </NavLink>
      </nav>
      <div className="app-header__tools">
        <button
          type="button"
          className="tag"
          onClick={openPalette}
          aria-keyshortcuts="Meta+K Control+K"
        >
          <Search aria-hidden size={15} />
          Jump to…
          <kbd className="tag__key">{isMac ? '⌘K' : 'Ctrl K'}</kbd>
        </button>
        <AccountMenu />
      </div>
    </header>
  )
}
