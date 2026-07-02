import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Maps Agentic UI Toolkit 사용량 어트리뷰션 ID를 전역으로 노출
// (툴킷 기본 ID + Google Maps Platform agent-skills 어트리뷰션)
;(window as any).A2UI_ATTRIBUTION_ID = 'gmp_web_maui_v0.1.7_exp,gmp_git_agentskills_v1'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
