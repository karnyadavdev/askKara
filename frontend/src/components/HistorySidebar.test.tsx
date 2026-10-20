import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import HistorySidebar from '../components/HistorySidebar'

const base = {
  open: true,
  onClose: () => {},
}

describe('HistorySidebar', () => {
  it('lists chats and opens one on click', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(
      <HistorySidebar {...base} items={[{ id: 'conv-1', title: 'First chat' }]} onOpen={onOpen} onNew={() => {}} />,
    )

    await user.click(screen.getByText('First chat'))
    expect(onOpen).toHaveBeenCalledWith('conv-1')
  })

  it('shows the empty state', () => {
    render(<HistorySidebar {...base} items={[]} onOpen={() => {}} onNew={() => {}} />)
    expect(screen.getByText('Nothing yet.')).toBeInTheDocument()
  })

  it('starts a new chat on NEW CHAT click', async () => {
    const user = userEvent.setup()
    const onNew = vi.fn()
    render(<HistorySidebar {...base} items={[]} onOpen={() => {}} onNew={onNew} />)

    await user.click(screen.getByText('NEW CHAT'))
    expect(onNew).toHaveBeenCalled()
  })
})
