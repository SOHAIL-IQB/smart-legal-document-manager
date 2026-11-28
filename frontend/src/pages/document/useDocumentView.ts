import { useSearchParams } from 'react-router'

export type Tab = 'read' | 'compare' | 'activity'
const TABS: Tab[] = ['read', 'compare', 'activity']

const number = (value: string | null) => {
  const n = Number.parseInt(value ?? '', 10)
  return Number.isFinite(n) && n > 0 ? n : undefined
}

/** The workspace's state lives in the address: the tab, the version read, the pair compared. */
export function useDocumentView() {
  const [params, setParams] = useSearchParams()
  const tab = TABS.includes(params.get('tab') as Tab) ? (params.get('tab') as Tab) : 'read'
  const view = {
    tab,
    version: number(params.get('v')),
    from: number(params.get('from')),
    to: number(params.get('to')),
    everyLine: params.get('all') === '1',
  }

  function go(next: Partial<typeof view>) {
    const merged = { ...view, ...next }
    const out = new URLSearchParams()
    if (merged.tab !== 'read') out.set('tab', merged.tab)
    if (merged.tab === 'read' && merged.version) out.set('v', String(merged.version))
    if (merged.tab === 'compare') {
      if (merged.from) out.set('from', String(merged.from))
      if (merged.to) out.set('to', String(merged.to))
      if (merged.everyLine) out.set('all', '1')
    }
    setParams(out)
  }

  return { view, go }
}

export type DocumentView = ReturnType<typeof useDocumentView>['view']
export type GoTo = ReturnType<typeof useDocumentView>['go']
