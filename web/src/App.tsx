import { useEffect, useRef, useState } from 'react'
import './App.css'
import {
  A2UIClient,
  A2UIRenderer,
  themeStyleSheet,
  type TimelineItem,
} from '@googlemaps/a2ui/lit'

/** 첫 화면에서 보여줄 추천 질문 */
const SUGGESTIONS = [
  { emoji: '🍣', text: '강남역 근처 스시 맛집 보여줘' },
  { emoji: '🥐', text: '홍대에서 분위기 좋은 브런치 카페 추천해줘' },
  { emoji: '🍷', text: '이태원 와인바 알려줘' },
  { emoji: '🚶', text: '서울역에서 광화문까지 가는 길 알려줘' },
]

/**
 * 맛집 파인더 — Maps Agentic UI Toolkit(A2UI) 한국어 데모.
 * A2A 프로토콜로 Python 에이전트와 통신하고, 응답의 A2UI 서피스를
 * <a2ui-surface> 웹 컴포넌트로 렌더링하는 채팅 UI.
 */
function App() {
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [input, setInput] = useState('')
  const [isRequesting, setIsRequesting] = useState(false)

  // A2UIClient: A2A 에이전트와의 통신 담당 (SERVER_URL은 index.html에서 주입)
  const clientRef = useRef(new A2UIClient((window as any).SERVER_URL))
  // A2UIRenderer: A2UI 서피스 상태 관리 및 메시지 처리
  const rendererRef = useRef(new A2UIRenderer())

  const messagesEndRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [timeline, isRequesting])

  // A2UI 위젯 테마 스타일시트 적용
  useEffect(() => {
    if (!document.adoptedStyleSheets.includes(themeStyleSheet)) {
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, themeStyleSheet]
    }
  }, [])

  /** 사용자 메시지를 에이전트에 보내고 응답 타임라인을 갱신한다 */
  const send = async (text: string) => {
    const messageText = text.trim()
    if (!messageText || isRequesting) return

    setInput('')
    setIsRequesting(true)

    rendererRef.current.addUserMessage(messageText)
    setTimeline([...rendererRef.current.timeline])

    try {
      const response = await clientRef.current.send(messageText)
      rendererRef.current.processResponse(response)
      setTimeline([...rendererRef.current.timeline])
    } catch (error) {
      console.error('Failed to send message:', error)
      rendererRef.current.processResponse([
        {
          type: 'text',
          text: `⚠️ 에이전트 연결에 실패했어요. 에이전트 서버(포트 10002)가 실행 중인지 확인해 주세요. (${
            error instanceof Error ? error.message : '알 수 없는 오류'
          })`,
        },
      ])
      setTimeline([...rendererRef.current.timeline])
    } finally {
      setIsRequesting(false)
    }
  }

  const isEmpty = timeline.length === 0

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-mark">맛</span>
          <div className="brand-text">
            <strong>맛집 파인더</strong>
            <span>Maps Agentic UI 데모</span>
          </div>
        </div>
        <a
          className="header-link"
          href="https://github.com/googlemaps-samples/a2ui"
          target="_blank"
          rel="noreferrer"
        >
          A2UI Toolkit ↗
        </a>
      </header>

      <main className="chat">
        <maui-providers>
          {isEmpty && (
            <section className="hero">
              <h1>
                오늘은 <em>어디서</em> 먹을까요?
              </h1>
              <p>
                맛집·카페·바를 찾아드리고, 지도와 길찾기까지 한 번에 보여드려요.
              </p>
              <div className="chips">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.text}
                    className="chip"
                    onClick={() => send(s.text)}
                    disabled={isRequesting}
                  >
                    <span className="chip-emoji">{s.emoji}</span>
                    {s.text}
                  </button>
                ))}
              </div>
            </section>
          )}

          {timeline.map((item, idx) => {
            if (item.type === 'user') {
              return (
                <div key={idx} className="msg msg-user">
                  {item.text}
                </div>
              )
            }
            if (item.type === 'action') {
              return (
                <div key={idx} className="msg msg-action">
                  <strong>액션: {item.action}</strong>
                  <pre>{item.text}</pre>
                </div>
              )
            }
            if (item.type === 'text') {
              return (
                <div key={idx} className="msg msg-bot">
                  {item.text}
                </div>
              )
            }
            if (item.type === 'surface') {
              // 에이전트가 생성한 A2UI 서피스(장소 카드, 지도, 경로 등) 렌더링
              const surface = rendererRef.current.getSurface(item.surfaceId)
              if (!surface) return null
              return (
                <div key={item.surfaceId} className="msg msg-surface">
                  {/* @ts-ignore — Lit 웹 컴포넌트에 객체 프로퍼티 직접 전달 */}
                  <a2ui-surface surface={surface}></a2ui-surface>
                </div>
              )
            }
            return null
          })}

          {isRequesting && (
            <div className="thinking">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
              맛집을 찾고 있어요…
            </div>
          )}
          <div ref={messagesEndRef} />
        </maui-providers>
      </main>

      <footer className="composer">
        <div className="composer-inner">
          <textarea
            className="composer-input"
            rows={1}
            placeholder="예) 성수동 파스타 맛집 추천해줘"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send(input)
              }
            }}
            disabled={isRequesting}
          />
          <button
            className="composer-send"
            onClick={() => send(input)}
            disabled={isRequesting || !input.trim()}
            aria-label="보내기"
          >
            {isRequesting ? '…' : '↑'}
          </button>
        </div>
        <p className="composer-note">
          장소 정보는 Google Maps Platform에서 실시간으로 가져옵니다.
        </p>
      </footer>
    </div>
  )
}

export default App
