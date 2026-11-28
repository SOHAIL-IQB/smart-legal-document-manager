import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useId, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'

import { listDocuments } from '@/api/documents'
import { useDebounced } from '@/lib/useDebounced'

type Props = { open: boolean; onOpenChange: (open: boolean) => void }

/** ⌘K: type part of a title, move with the arrows, Enter opens it. A combobox over a listbox. */
export function Palette({ open, onOpenChange }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="palette" aria-describedby={undefined}>
          <Dialog.Title className="palette__title">Jump to a document</Dialog.Title>
          {open && <PaletteSearch onDone={() => onOpenChange(false)} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function PaletteSearch({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate()
  const id = useId()
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  const query = useDebounced(text.trim(), 150)

  const results = useQuery({
    queryKey: ['palette', query],
    queryFn: ({ signal }) => listDocuments({ q: query, sort: 'updated_at', limit: 8, offset: 0 }, signal),
    enabled: query.length > 0,
    placeholderData: keepPreviousData,
  })
  const items = query ? (results.data?.items ?? []) : []
  const expanded = items.length > 0
  const optionId = (i: number) => `${id}-option-${i}`

  function open(index: number) {
    const item = items[index]
    if (!item) return
    onDone()
    navigate(`/documents/${item.id}`)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!expanded) return
    const moves: Record<string, number> = {
      ArrowDown: (active + 1) % items.length,
      ArrowUp: (active - 1 + items.length) % items.length,
      Home: 0,
      End: items.length - 1,
    }
    if (event.key in moves) {
      event.preventDefault()
      setActive(moves[event.key])
    } else if (event.key === 'Enter') {
      event.preventDefault()
      open(active)
    }
  }

  return (
    <>
      <label htmlFor={`${id}-input`} className="sr-only">
        Document title
      </label>
      <input
        id={`${id}-input`}
        className="palette__input"
        role="combobox"
        aria-expanded={expanded}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={expanded ? optionId(active) : undefined}
        placeholder="Type part of a title"
        autoComplete="off"
        spellCheck={false}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          setActive(0)
        }}
        onKeyDown={onKeyDown}
      />
      <ul id={`${id}-list`} role="listbox" aria-label="Documents" className="palette__list">
        {items.map((item, i) => (
          <li
            key={item.id}
            id={optionId(i)}
            role="option"
            aria-selected={i === active}
            className="palette__option"
            onMouseMove={() => setActive(i)}
            onClick={() => open(i)}
          >
            <span>
              <Highlight text={item.title} match={query} />
            </span>
          </li>
        ))}
      </ul>
      {query && results.isSuccess && items.length === 0 && (
        <p className="palette__empty">No document titles or text match “{query}”.</p>
      )}
      <p className="palette__hint" aria-hidden="true">
        ↑ ↓ to move · Enter to open · Esc to close
      </p>
    </>
  )
}

/** The matched letters are underlined: a mark by form, not colour. */
function Highlight({ text, match }: { text: string; match: string }) {
  const at = match ? text.toLowerCase().indexOf(match.toLowerCase()) : -1
  if (at === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, at)}
      <span className="palette__match">{text.slice(at, at + match.length)}</span>
      {text.slice(at + match.length)}
    </>
  )
}
