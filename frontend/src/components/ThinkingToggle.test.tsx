import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { store } from '../app/store'
import { useAppSelector } from '../app/hooks'
import ThinkingToggle from '../components/ThinkingToggle'
import { toggleDeep, toggleThinking } from '../features/streamSlice'
import { renderWithStore } from '../test/renderWithStore'

function Probe() {
  const thinking = useAppSelector((state) => state.stream.thinking)
  return <span data-testid="thinking-flag">{thinking}</span>
}

describe('ThinkingToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    if (store.getState().stream.thinking === 'high') store.dispatch(toggleThinking())
    if (store.getState().stream.deep) store.dispatch(toggleDeep())
  })

  it('flips between low and highest', async () => {
    const user = userEvent.setup()
    renderWithStore(
      <>
        <ThinkingToggle />
        <Probe />
      </>,
    )

    expect(screen.getByTestId('thinking-flag')).toHaveTextContent('low')
    expect(screen.getByRole('button', { name: 'THINKING: LOW' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: 'THINKING: LOW' }))

    expect(screen.getByTestId('thinking-flag')).toHaveTextContent('high')
    expect(screen.getByRole('button', { name: 'THINKING: HIGHEST' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('is hidden while deep research is on', () => {
    renderWithStore(<ThinkingToggle />)

    act(() => {
      store.dispatch(toggleDeep())
    })

    expect(screen.queryByRole('button', { name: /THINKING/ })).toBeNull()
  })
})
