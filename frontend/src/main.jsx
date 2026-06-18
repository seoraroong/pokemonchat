import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// PWA 설치 모드 감지 → html에 pwa-mode 클래스 추가
if (
  window.matchMedia('(display-mode: standalone)').matches ||
  window.matchMedia('(display-mode: fullscreen)').matches ||
  window.navigator.standalone === true
) {
  document.documentElement.classList.add('pwa-mode');
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
