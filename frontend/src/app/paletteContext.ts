import { createContext, useContext } from 'react'

/** Opens the ⌘K palette from anywhere in the signed-in app. */
export const PaletteContext = createContext<() => void>(() => {})

export const useOpenPalette = () => useContext(PaletteContext)
