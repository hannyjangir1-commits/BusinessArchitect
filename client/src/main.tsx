import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/index.css'
import App from './App'
import { DialogFocusManager } from './components/DialogFocusManager'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DialogFocusManager />
    <App />
  </StrictMode>,
)
