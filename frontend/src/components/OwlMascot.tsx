import { useEffect, useRef, useState } from 'react'
import './owl.css'

export type OwlMood = 'idle' | 'thinking' | 'happy' | 'greeting'

interface OwlMascotProps {
  mood?: OwlMood
  size?: number
  className?: string
}

export default function OwlMascot({ mood = 'idle', size = 160, className = '' }: OwlMascotProps) {
  const [blinking, setBlinking] = useState(false)
  const moodRef = useRef<OwlMood>(mood)

  useEffect(() => {
    moodRef.current = mood
  }, [mood])

  useEffect(() => {
    let timer: number | undefined
    let settled = false
    const schedule = () => {
      const thinking = moodRef.current === 'thinking'
      const base = thinking ? 1400 : 2800
      const jitter = Math.random() * (thinking ? 800 : 2400)
      timer = window.setTimeout(() => {
        if (settled) return
        setBlinking(true)
        window.setTimeout(() => setBlinking(false), 300)
        if (Math.random() < 0.28) {
          window.setTimeout(() => {
            if (settled) return
            setBlinking(true)
            window.setTimeout(() => setBlinking(false), 300)
          }, 420)
        }
        schedule()
      }, base + jitter)
    }
    schedule()
    return () => {
      settled = true
      window.clearTimeout(timer)
    }
  }, [])

  const eyeArcs = mood === 'happy'
  const pupilsOpen = mood === 'greeting'
  const cls = ['owl', `owl--${mood}`, blinking ? 'owl--blinking' : '', className]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={cls} style={{ width: size, height: (size * 220) / 240 }}>
      <svg viewBox="0 0 240 220" width="100%" height="100%" aria-hidden="true">
        <defs>
          <radialGradient id="owl-glow-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffd27a" stopOpacity="0.85" />
            <stop offset="60%" stopColor="#ffb454" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#ffb454" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="owl-body-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8a5a33" />
            <stop offset="100%" stopColor="#69421f" />
          </linearGradient>
          <linearGradient id="owl-wing-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7a4d28" />
            <stop offset="100%" stopColor="#5d3a1a" />
          </linearGradient>
        </defs>

        <ellipse className="owl-glow" cx="120" cy="108" rx="100" ry="96" fill="url(#owl-glow-grad)" />

        <g className="owl-sway">
          <g className="owl-wings">
            <ellipse className="owl-wing owl-wing--l" cx="58" cy="158" rx="21" ry="38" fill="url(#owl-wing-grad)" transform="rotate(14 58 158)" />
            <ellipse className="owl-wing owl-wing--r" cx="182" cy="158" rx="21" ry="38" fill="url(#owl-wing-grad)" transform="rotate(-14 182 158)" />
          </g>

          <g className="owl-tufts">
            <path className="owl-tuft owl-tuft--l" d="M80 34 L58 6 L94 24 Z" fill="url(#owl-body-grad)" strokeLinejoin="round" />
            <path className="owl-tuft owl-tuft--r" d="M160 34 L182 6 L146 24 Z" fill="url(#owl-body-grad)" strokeLinejoin="round" />
          </g>

          <ellipse cx="120" cy="98" rx="80" ry="76" fill="url(#owl-body-grad)" />
          <ellipse cx="120" cy="112" rx="60" ry="56" fill="#f7e9d0" />

          <g className="owl-eyes">
            <g className="owl-eye">
              <ellipse className="owl-eyeball" cx="92" cy="98" rx="23" ry="26" fill="#ffffff" />
              {eyeArcs ? (
                <path className="owl-eye-arc" d="M80 100 Q92 88 104 100" stroke="#3a2a1a" strokeWidth="4.5" fill="none" strokeLinecap="round" />
              ) : (
                <g className="owl-pupil-wrap">
                  <circle
                    className="owl-pupil"
                    cx="92"
                    cy="98"
                    r={pupilsOpen ? 13 : 11}
                    fill="#3a2a1a"
                  />
                  <circle className="owl-glint" cx="87" cy="92" r="3.6" fill="#fff" />
                </g>
              )}
              <ellipse className="owl-eyelid" cx="92" cy="98" rx="23" ry="26" fill="#f7e9d0" />
            </g>
            <g className="owl-eye">
              <ellipse className="owl-eyeball" cx="148" cy="98" rx="23" ry="26" fill="#ffffff" />
              {eyeArcs ? (
                <path className="owl-eye-arc" d="M136 100 Q148 88 160 100" stroke="#3a2a1a" strokeWidth="4.5" fill="none" strokeLinecap="round" />
              ) : (
                <g className="owl-pupil-wrap">
                  <circle
                    className="owl-pupil"
                    cx="148"
                    cy="98"
                    r={pupilsOpen ? 13 : 11}
                    fill="#3a2a1a"
                  />
                  <circle className="owl-glint" cx="143" cy="92" r="3.6" fill="#fff" />
                </g>
              )}
              <ellipse className="owl-eyelid" cx="148" cy="98" rx="23" ry="26" fill="#f7e9d0" />
            </g>
          </g>

          <g className="owl-brows">
            <path className="owl-brow owl-brow--l" d="M78 64 Q92 56 106 62" stroke="#69421f" strokeWidth="3.5" fill="none" strokeLinecap="round" />
            <path className="owl-brow owl-brow--r" d="M134 62 Q148 56 162 64" stroke="#69421f" strokeWidth="3.5" fill="none" strokeLinecap="round" />
          </g>

          <g className="owl-blush">
            <ellipse cx="66" cy="122" rx="9" ry="6" fill="#f4a7b0" opacity="0.65" />
            <ellipse cx="174" cy="122" rx="9" ry="6" fill="#f4a7b0" opacity="0.65" />
          </g>

          <g className="owl-flibs">
            <g className="owl-flib owl-flib--l">
              <ellipse cx="84" cy="130" rx="4" ry="5.5" fill="#d9b98a" />
              <ellipse cx="91" cy="133" rx="4" ry="5.5" fill="#d9b98a" />
              <ellipse cx="98" cy="130" rx="4" ry="5.5" fill="#d9b98a" />
            </g>
            <g className="owl-flib owl-flib--r">
              <ellipse cx="142" cy="130" rx="4" ry="5.5" fill="#d9b98a" />
              <ellipse cx="149" cy="133" rx="4" ry="5.5" fill="#d9b98a" />
              <ellipse cx="156" cy="130" rx="4" ry="5.5" fill="#d9b98a" />
            </g>
          </g>

          <g className="owl-sparks">
            <path className="owl-spark owl-spark--l" d="M58 118 L60 124 L66 126 L60 128 L58 134 L56 128 L50 126 L56 124 Z" fill="#ffd27a" />
            <path className="owl-spark owl-spark--r" d="M182 118 L184 124 L190 126 L184 128 L182 134 L180 128 L174 126 L180 124 Z" fill="#ffd27a" />
          </g>

          <path
            className="owl-beak"
            d="M120 134 C113 134 111 142 113 148 C115 154 125 154 127 148 C129 142 127 134 120 134 Z"
            fill="#f0a040"
          />

          <ellipse cx="120" cy="172" rx="46" ry="38" fill="#fdf3e0" />
          <g className="owl-feet">
            <ellipse cx="102" cy="212" rx="14" ry="6" fill="#e08a2e" />
            <ellipse cx="138" cy="212" rx="14" ry="6" fill="#e08a2e" />
          </g>
        </g>
      </svg>
    </div>
  )
}
