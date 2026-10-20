import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import App from './App.tsx'
import { store } from './app/store'
import './styles.css'

const theme = localStorage.getItem('kara_theme')
if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>,
)
