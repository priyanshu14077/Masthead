import { useEffect, useRef } from "react"

/**
 * The hero's misty ribbon: a few thousand points laid along two slow sine waves, brightest at the
 * ribbon's centre line. Draws one still frame under reduced motion and pauses while off screen.
 */
export function ParticleWave({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext("2d")
    if (!canvas || !ctx) return
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    let w = 0, h = 0, frame = 0, visible = true, t = 12
    // Fixed jitter per point, so the texture shimmers without flicker.
    const jitter = Array.from({ length: 9001 }, (_, i) => {
      const s = Math.sin(i * 12.9898) * 43758.5453
      return s - Math.floor(s)
    })
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = canvas.clientWidth
      h = canvas.clientHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    const draw = () => {
      ctx.clearRect(0, 0, w, h)
      const cols = Math.max(110, Math.floor(w / 4))
      const rows = 64
      let k = 0
      for (let i = 0; i < cols; i++) {
        const x = (i / (cols - 1)) * w
        const u = x / w
        const centre = h * 0.42 + Math.sin(u * 5.2 + t * 0.32) * h * 0.13 + Math.sin(u * 11 - t * 0.21) * h * 0.04
        const spread = h * (0.14 + 0.08 * Math.sin(u * 3.1 + t * 0.17))
        const fade = Math.sin(Math.PI * u) ** 0.8
        for (let j = 0; j < rows; j++) {
          const r = jitter[k++ % jitter.length]
          const offset = (j / (rows - 1) - 0.5) * 2
          const y = centre + offset * spread + Math.sin(i * 0.7 + j + t) * 1.6 + (r - 0.5) * 9
          const glow = Math.exp(-(offset * offset) * 1.9)
          const a = glow * fade * (0.22 + 0.62 * r)
          if (a < 0.03) continue
          ctx.fillStyle = `rgba(235,235,235,${a.toFixed(3)})`
          ctx.fillRect(x + (r - 0.5) * 4, y, 1.3, 1.3)
        }
      }
    }
    const loop = () => {
      if (visible) {
        t += 0.012
        draw()
      }
      frame = requestAnimationFrame(loop)
    }
    resize()
    draw()
    if (!still) frame = requestAnimationFrame(loop)
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting))
    io.observe(canvas)
    const ro = new ResizeObserver(() => { resize(); draw() })
    ro.observe(canvas)
    return () => { cancelAnimationFrame(frame); io.disconnect(); ro.disconnect() }
  }, [])
  return <canvas ref={ref} aria-hidden="true" className={className} />
}
