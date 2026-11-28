import { useCallback, useEffect, useState } from 'react'
import { Outlet } from 'react-router'

import { AppHeader } from './AppHeader'
import { Palette } from './Palette'
import { PaletteContext } from './paletteContext'
import './app.css'

/** Every signed-in screen: the header band, the page, and ⌘K anywhere. */
export function AppLayout() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const openPalette = useCallback(() => setPaletteOpen(true), [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <PaletteContext.Provider value={openPalette}>
      <div className="app">
        <AppHeader />
        <Outlet />
      </div>
      <Palette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </PaletteContext.Provider>
  )
}
