export type Theme = 'light' | 'dark'

export function applyTheme(theme: Theme) {
  if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light')
  else document.documentElement.removeAttribute('data-theme')
}

export function initTheme() {
  const stored = localStorage.getItem('kara_theme')
  if (stored === 'light' || stored === 'dark') {
    applyTheme(stored)
    return
  }

  const query = window.matchMedia('(prefers-color-scheme: light)')
  applyTheme(query.matches ? 'light' : 'dark')
  query.addEventListener('change', (event) => {
    if (localStorage.getItem('kara_theme')) return
    applyTheme(event.matches ? 'light' : 'dark')
  })
}
