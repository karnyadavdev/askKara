import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProfileModal from '../components/ProfileModal'
import { avatarErrorMessage } from '../features/avatarErrors'
import { renderWithStore } from '../test/renderWithStore'

class StubRequest {
  url: string
  method: string
  headers: Headers
  body: BodyInit | null

  constructor(input: RequestInfo | URL, init: RequestInit = {}) {
    const raw = typeof input === 'string' ? input : String(input)
    this.url = /^https?:\/\//.test(raw) ? raw : `http://localhost${raw}`
    this.method = (init.method ?? 'GET').toUpperCase()
    this.headers = new Headers(init.headers)
    this.body = init.body ?? null
  }
}

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('Request', StubRequest)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function lastRequest(): StubRequest {
  return fetchMock.mock.calls.at(-1)?.[0] as StubRequest
}

function renderModal() {
  return renderWithStore(
    <ProfileModal email="karan@example.com" name="Karan" avatarUrl={null} onClose={() => {}} onSignOut={() => {}} />,
  )
}

describe('ProfileModal', () => {
  it('prefills the name and opens the editor on click', async () => {
    const user = userEvent.setup()
    renderModal()

    expect(screen.getByText('Karan')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Edit name' }))

    expect(screen.getByPlaceholderText('Your name')).toHaveValue('Karan')
    expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy()
  })

  it('saves the name with a PATCH to /api/auth/me', async () => {
    const user = userEvent.setup()
    fetchMock.mockResolvedValue(
      jsonResponse({ id: 1, email: 'karan@example.com', name: 'Karan Yadav', avatar_url: null }),
    )

    renderModal()

    await user.click(screen.getByRole('button', { name: 'Edit name' }))
    await user.clear(screen.getByPlaceholderText('Your name'))
    await user.type(screen.getByPlaceholderText('Your name'), 'Karan Yadav')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('Name saved.')
    const request = lastRequest()
    expect(request.url).toBe('http://localhost/api/auth/me')
    expect(request.method).toBe('PATCH')
    expect(request.body).toBe(JSON.stringify({ name: 'Karan Yadav' }))
  })

  it('shows an error when the name cannot be saved', async () => {
    const user = userEvent.setup()
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'boom' }, 500))

    renderModal()

    await user.click(screen.getByRole('button', { name: 'Edit name' }))
    await user.clear(screen.getByPlaceholderText('Your name'))
    await user.type(screen.getByPlaceholderText('Your name'), 'Karan Yadav')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('Could not save that name.')
  })

  it('uploads a picked picture as multipart form data', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ id: 1, email: 'karan@example.com', name: 'Karan', avatar_url: '/api/avatars/1' }),
    )

    renderModal()

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['png-bytes'], 'me.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [file] } })

    await screen.findByText('Picture updated.')
    const request = lastRequest()
    expect(request.url).toBe('http://localhost/api/auth/avatar')
    expect(request.method).toBe('POST')
    expect(request.body).toBeInstanceOf(FormData)
    expect((request.body as FormData).get('file')).toBe(file)
  })

  it('surfaces the server message when the picture is rejected', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Image is over 2 MB' }, 413))

    renderModal()

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'big.jpg', { type: 'image/jpeg' })] } })

    await screen.findByText('That image is over 2 MB.')
  })
})

describe('avatarErrorMessage', () => {
  it('maps the unsupported format', () => {
    expect(avatarErrorMessage({ status: 415 })).toBe('Use a JPG, PNG, or WebP image.')
  })

  it('maps the size limit', () => {
    expect(avatarErrorMessage({ status: 413 })).toBe('That image is over 2 MB.')
  })

  it('maps the unconfigured store', () => {
    expect(avatarErrorMessage({ status: 503 })).toBe('Picture upload is not available right now.')
  })

  it('maps an expired session', () => {
    expect(avatarErrorMessage({ status: 401 })).toBe('Sign in again to change your picture.')
  })

  it('uses a string detail from the server', () => {
    expect(avatarErrorMessage({ status: 400, data: { detail: 'That file is not a readable image' } })).toBe(
      'That file is not a readable image',
    )
  })

  it('uses the first validation message', () => {
    expect(avatarErrorMessage({ status: 422, data: { detail: [{ msg: 'Invalid file' }] } })).toBe('Invalid file')
  })

  it('falls back to the generic message', () => {
    expect(avatarErrorMessage(new Error('network'))).toBe('Could not upload that picture.')
  })
})
