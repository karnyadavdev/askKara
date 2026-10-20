import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { store } from '../app/store'
import { useAppSelector } from '../app/hooks'
import DeepToggle from '../components/DeepToggle'
import { goHome, toggleDeep } from '../features/streamSlice'
import { renderWithStore } from '../test/renderWithStore'

function Probe() {
  const deep = useAppSelector((state) => state.stream.deep)
  return <span data-testid="deep-flag">{deep ? 'on' : 'off'}</span>
}

describe('DeepToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    if (store.getState().stream.deep) store.dispatch(toggleDeep())
  })

  it('flips deep mode in the store', async () => {
    const user = userEvent.setup()
    renderWithStore(
      <>
        <DeepToggle />
        <Probe />
      </>,
    )

    expect(screen.getByTestId('deep-flag')).toHaveTextContent('off')
    await user.click(screen.getByRole('button', { name: 'DEEP RESEARCH' }))
    expect(screen.getByTestId('deep-flag')).toHaveTextContent('on')
    expect(screen.getByRole('button', { name: 'DEEP RESEARCH' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('exposes pressed state for screen readers', async () => {
    const user = userEvent.setup()
    renderWithStore(<DeepToggle />)

    const button = screen.getByRole('button', { name: /DEEP/ })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    await user.click(button)
    expect(button).toHaveAttribute('aria-pressed', 'true')
  })

  it('clears deep mode when going home', async () => {
    const user = userEvent.setup()
    renderWithStore(
      <>
        <DeepToggle />
        <Probe />
      </>,
    )

    await user.click(screen.getByRole('button', { name: 'DEEP RESEARCH' }))
    expect(screen.getByTestId('deep-flag')).toHaveTextContent('on')
    act(() => {
      store.dispatch(goHome())
    })
    expect(screen.getByTestId('deep-flag')).toHaveTextContent('off')
  })
})
