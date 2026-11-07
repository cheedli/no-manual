// No Manual — Desktop half: interactive 3D step viewer for solver plans.
// Source of desktop/plugin.js (built by scripts/build_desktop.sh; three.js is bundled in).
// Rules followed: no JSX, only @hermes/plugin-sdk / react imports at runtime, theme colours only,
// canvas tracks its container with ResizeObserver, everything disposed on unmount.
import * as sdk from '@hermes/plugin-sdk'
import { useEffect, useMemo, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import {
  AmbientLight, BoxGeometry, CircleGeometry, Color, DirectionalLight, EdgesGeometry, Group, LineBasicMaterial,
  LineSegments, Mesh, MeshBasicMaterial, MeshStandardMaterial, PerspectiveCamera, Scene, Vector3, WebGLRenderer
} from 'three'

const OUR_TOOLS = ['nm_render_steps', 'nm_get_step']
const ANIM_MS = 700

function parseResult(result) {
  if (!result) return {}
  if (typeof result === 'string') {
    try { return JSON.parse(result) } catch { return {} }
  }
  return result
}

function cssVar(el, name, fallbackVar) {
  const v = getComputedStyle(el).getPropertyValue(name).trim()
  if (v) return v
  return fallbackVar ? getComputedStyle(el).getPropertyValue(fallbackVar).trim() : ''
}

async function loadScene(ctx, file, scenePath) {
  if (file && /scene\.json$/.test(file.name || file.path || '')) {
    try {
      const url = await file.resolveUrl()
      const res = await fetch(url)
      if (res.ok) return await res.json()
    } catch { /* fall through to the backend route */ }
  }
  return ctx.rest('/scene?path=' + encodeURIComponent(scenePath))
}

function Viewer3D({ scene, stepIdx, explode, fitTick }) {
  const host = useRef(null)
  const state = useRef(null)

  // one-time three.js setup per scene
  useEffect(() => {
    const el = host.current
    if (!el || !scene) return undefined
    const renderer = new WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    renderer.setClearColor(0x000000, 0) // keep the app's own background
    el.appendChild(renderer.domElement)

    const s3 = new Scene()
    s3.add(new AmbientLight(0xffffff, 1.7))
    const sun = new DirectionalLight(0xffffff, 1.5)
    sun.position.set(1, 2, 3)
    s3.add(sun)
    const camera = new PerspectiveCamera(35, 1, 1, 100000)
    const model = new Group()
    s3.add(model)

    const { w, h, d } = scene.outer_dims
    const center = new Vector3(w / 2, h / 2, d / 2)
    const lineColor = new Color(cssVar(el, '--ui-text-secondary') || 'currentColor')
    const panelColor = new Color(cssVar(el, '--ui-stroke-secondary', '--ui-text-quaternary') || 'gray')
    // new parts: a light tint of the theme accent (the blueprint look of the step cards)
    const accent = new Color(cssVar(el, '--ui-accent') || 'currentColor').lerp(new Color(1, 1, 1), 0.5)
    // soft ground shadow under the footprint (No Manual drawing style)
    const shadowMat = new MeshBasicMaterial({ color: lineColor.clone(), transparent: true, opacity: 0.12, depthWrite: false })
    const shadow = new Mesh(new CircleGeometry(1, 48), shadowMat)
    shadow.rotation.x = -Math.PI / 2
    shadow.scale.set(w * 0.75, d * 0.95, 1)
    shadow.position.set(w / 2, -1, d / 2)
    model.add(shadow)
    const meshes = {}
    for (const p of scene.parts) {
      const geo = new BoxGeometry(p.size[0], p.size[1], p.size[2])
      const mat = new MeshStandardMaterial({ color: panelColor.clone(), roughness: 1, metalness: 0, transparent: true, opacity: 0.96 })
      const mesh = new Mesh(geo, mat)
      const edges = new LineSegments(new EdgesGeometry(geo), new LineBasicMaterial({ color: lineColor }))
      mesh.add(edges)
      mesh.visible = false
      model.add(mesh)
      meshes[p.id] = { mesh, size: p.size, mat, edges }
    }
    const view = { yaw: -0.6, pitch: 0.45, dist: Math.max(w, h, d) * 2.6 }
    const placeCamera = () => {
      camera.position.set(
        center.x + view.dist * Math.cos(view.pitch) * Math.sin(view.yaw),
        center.y + view.dist * Math.sin(view.pitch),
        center.z + view.dist * Math.cos(view.pitch) * Math.cos(view.yaw))
      camera.lookAt(center)
    }
    const resize = () => {
      const r = el.getBoundingClientRect()
      const cw = Math.max(1, Math.floor(r.width))
      const ch = Math.max(1, Math.floor(r.height))
      renderer.setSize(cw, ch, false)
      renderer.domElement.style.width = cw + 'px'
      renderer.domElement.style.height = ch + 'px'
      camera.aspect = cw / ch
      camera.updateProjectionMatrix()
      draw()
    }
    const draw = () => { placeCamera(); renderer.render(s3, camera) }
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    // tiny orbit: drag rotates, wheel zooms
    let drag = null
    const onDown = e => { drag = { x: e.clientX, y: e.clientY }; renderer.domElement.setPointerCapture?.(e.pointerId) }
    const onMove = e => {
      if (!drag) return
      view.yaw -= (e.clientX - drag.x) * 0.008
      view.pitch = Math.max(-1.2, Math.min(1.4, view.pitch + (e.clientY - drag.y) * 0.008))
      drag = { x: e.clientX, y: e.clientY }
      draw()
    }
    const onUp = () => { drag = null }
    const onWheel = e => { e.preventDefault(); view.dist = Math.max(200, view.dist * (1 + Math.sign(e.deltaY) * 0.1)); draw() }
    const c = renderer.domElement
    c.addEventListener('pointerdown', onDown)
    c.addEventListener('pointermove', onMove)
    c.addEventListener('pointerup', onUp)
    c.addEventListener('pointerleave', onUp)
    c.addEventListener('wheel', onWheel, { passive: false })

    let raf = 0
    state.current = { meshes, draw, view, accent, panelColor, raf: () => raf, setRaf: v => { raf = v }, center, w, h, d }
    resize()
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      c.removeEventListener('pointerdown', onDown)
      c.removeEventListener('pointermove', onMove)
      c.removeEventListener('pointerup', onUp)
      c.removeEventListener('pointerleave', onUp)
      c.removeEventListener('wheel', onWheel)
      shadow.geometry.dispose(); shadowMat.dispose()
      for (const m of Object.values(meshes)) {
        m.mesh.geometry.dispose(); m.mat.dispose(); m.edges.geometry.dispose(); m.edges.material.dispose()
      }
      renderer.dispose()
      c.remove()
      state.current = null
    }
  }, [scene])

  // show one step: placed parts at rest, new parts fly in from their exploded offset
  useEffect(() => {
    const st = state.current
    if (!st || !scene) return undefined
    const step = scene.steps[stepIdx]
    if (!step) return undefined
    const placed = new Map(step.placed.map(p => [p.id, p.pos]))
    const added = new Set(step.added)
    const spread = explode ? 0.35 : 0
    const target = {}
    for (const [id, m] of Object.entries(st.meshes)) {
      const pos = placed.get(id)
      m.mesh.visible = !!pos
      if (!pos) continue
      m.mat.color.copy(added.has(id) ? st.accent : st.panelColor)
      const cx = pos[0] + m.size[0] / 2
      const cy = pos[1] + m.size[1] / 2
      const cz = pos[2] + m.size[2] / 2
      const t = new Vector3(cx + (cx - st.center.x) * spread, cy + (cy - st.center.y) * spread, cz + (cz - st.center.z) * spread)
      target[id] = t
      const from = step.explode_from?.[id]
      if (added.has(id) && from) m.mesh.position.set(t.x + from[0], t.y + from[1], t.z + from[2])
      else m.mesh.position.copy(t)
    }
    const start = performance.now()
    cancelAnimationFrame(st.raf())
    const tick = now => {
      const k = Math.min(1, (now - start) / ANIM_MS)
      const ease = 1 - Math.pow(1 - k, 3)
      for (const id of added) {
        const m = st.meshes[id]
        if (m && target[id]) m.mesh.position.lerp(target[id], ease)
      }
      st.draw()
      if (k < 1) st.setRaf(requestAnimationFrame(tick))
    }
    st.setRaf(requestAnimationFrame(tick))
    return () => cancelAnimationFrame(st.raf())
  }, [scene, stepIdx, explode])

  // Fit: reset the orbit
  useEffect(() => {
    const st = state.current
    if (!st || !fitTick) return
    st.view.yaw = -0.6; st.view.pitch = 0.45; st.view.dist = Math.max(st.w, st.h, st.d) * 2.6
    st.draw()
  }, [fitTick])

  return jsx('div', { ref: host, style: { width: '100%', height: '100%', minHeight: '320px', cursor: 'grab', touchAction: 'none' } })
}

function Btn({ onClick, children, disabled, pressed }) {
  const B = sdk.Button
  if (B) return jsx(B, { size: 'sm', variant: pressed ? 'secondary' : 'ghost', onClick, disabled, children })
  return jsx('button', { type: 'button', onClick, disabled, style: { fontSize: '12px', padding: '2px 8px', borderRadius: '4px', background: 'transparent', color: 'var(--ui-text-secondary)', border: '1px solid var(--ui-stroke-secondary)' }, children })
}

function StepViewer(props) {
  const { file, result, fallback, ctx } = props
  const res = useMemo(() => parseResult(result), [result])
  const isScene = /scene\.json$/.test(file?.name || file?.path || '')
  const scenePath = isScene ? file.path : res.scene_path
  const [scene, setScene] = useState(null)
  const [failed, setFailed] = useState(false)
  const [idx, setIdx] = useState(0)
  const [explode, setExplode] = useState(false)
  const [fitTick, setFitTick] = useState(0)

  useEffect(() => {
    if (!scenePath) return undefined
    let live = true
    loadScene(ctx, file, scenePath).then(s => {
      if (!live) return
      if (!s || s.version !== 1 || !Array.isArray(s.steps) || !s.steps.length) { setFailed(true); return }
      setScene(s)
      const want = Number(res.index) || s.steps.length
      setIdx(Math.max(0, Math.min(s.steps.length - 1, want - 1)))
    }, () => live && setFailed(true))
    return () => { live = false }
  }, [scenePath])

  if (!scenePath || failed) return fallback ?? null
  if (!scene) return jsx('div', { style: { padding: '12px', fontSize: '12px', color: 'var(--ui-text-tertiary)' }, children: 'Loading 3D steps…' })
  const step = scene.steps[idx]
  const hw = (step.hardware || []).map(h => `×${h.count} ${String(h.kind).replace(/_/g, ' ')}`).join('  ·  ')
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '8px', padding: '8px', borderRadius: '8px',
      border: '1px solid var(--ui-stroke-secondary)', height: '460px', boxSizing: 'border-box' },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', minWidth: 0 },
        children: [
          jsx('span', { style: { fontWeight: 600, whiteSpace: 'nowrap', color: 'var(--ui-text-secondary)' }, children: `Step ${idx + 1} of ${scene.steps.length}` }),
          jsx('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--ui-text-secondary)' }, children: step.title }),
          step.confidence < 0.75 && jsx('span', { style: { fontSize: '11px', padding: '0 4px', borderRadius: '4px', whiteSpace: 'nowrap', color: 'var(--ui-accent)', border: '1px solid var(--ui-accent)' }, children: 'check this step' })
        ]
      }),
      jsx('div', { style: { flex: 1, minHeight: 0 }, children: jsx(Viewer3D, { scene, stepIdx: idx, explode, fitTick }) }),
      hw && jsx('div', { style: { fontSize: '12px', color: 'var(--ui-text-tertiary)' }, children: hw }),
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: '4px' },
        children: [
          jsx(Btn, { onClick: () => setIdx(i => Math.max(0, i - 1)), disabled: idx === 0, children: '◀ Prev' }),
          jsx(Btn, { onClick: () => setIdx(i => Math.min(scene.steps.length - 1, i + 1)), disabled: idx === scene.steps.length - 1, children: 'Next ▶' }),
          jsx(Btn, { onClick: () => setExplode(v => !v), pressed: explode, children: explode ? 'Collapse' : 'Explode' }),
          jsx(Btn, { onClick: () => setFitTick(t => t + 1), children: 'Fit' }),
          jsx('span', { style: { marginLeft: 'auto', fontSize: '11px', color: 'var(--ui-text-quaternary)' }, children: 'drag to rotate · scroll to zoom' })
        ]
      })
    ]
  })
}

export default {
  id: 'no-manual',
  name: 'No Manual',
  register(ctx) {
    // Older Desktops don't export the area: nothing to do there (PNG steps still work everywhere).
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA !== 'string') return
    ctx.register({
      id: 'step-viewer',
      area: sdk.TOOL_MEDIA_RENDERER_AREA,
      data: { tools: OUR_TOOLS, render: props => jsx(StepViewer, { ...props, ctx }) }
    })
  }
}
