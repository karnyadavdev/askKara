export function avatarErrorMessage(error: unknown): string {
  const status =
    error && typeof error === 'object' && 'status' in error ? (error as { status?: number | string }).status : undefined
  const data =
    error && typeof error === 'object' && 'data' in error ? (error as { data?: { detail?: unknown } }).data : undefined
  const detail = data?.detail

  if (status === 415) return 'Use a JPG, PNG, or WebP image.'
  if (status === 413) return 'That image is over 2 MB.'
  if (status === 503) return 'Picture upload is not available right now.'
  if (status === 401) return 'Sign in again to change your picture.'
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string }
    if (first?.msg) return first.msg
  }
  return 'Could not upload that picture.'
}
