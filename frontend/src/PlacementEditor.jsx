import { useCallback, useRef } from 'react'

const DISPLAY_MAX_PX = 340

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

export function defaultPlacement(position) {
  return { position, x: 0.5, y: 0.5, scale: 1, angle: 0 }
}

export default function PlacementEditor({ printArea, design, placement, onChange }) {
  const dragRef = useRef(null)

  const boxScale = Math.min(DISPLAY_MAX_PX / printArea.width_px, DISPLAY_MAX_PX / printArea.height_px)
  const boxWidth = printArea.width_px * boxScale
  const boxHeight = printArea.height_px * boxScale

  const baseFit = Math.min(printArea.width_px / design.width, printArea.height_px / design.height)
  const effectiveScale = baseFit * placement.scale
  const imgWidth = design.width * effectiveScale * boxScale
  const imgHeight = design.height * effectiveScale * boxScale

  const handlePointerDown = useCallback(
    (e) => {
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      dragRef.current = { startX: e.clientX, startY: e.clientY, startPlacementX: placement.x, startPlacementY: placement.y }
    },
    [placement.x, placement.y],
  )

  const handlePointerMove = useCallback(
    (e) => {
      if (!dragRef.current) return
      const dx = e.clientX - dragRef.current.startX
      const dy = e.clientY - dragRef.current.startY
      onChange({
        ...placement,
        x: clamp(dragRef.current.startPlacementX + dx / boxWidth, -0.5, 1.5),
        y: clamp(dragRef.current.startPlacementY + dy / boxHeight, -0.5, 1.5),
      })
    },
    [boxWidth, boxHeight, placement, onChange],
  )

  const handlePointerUp = useCallback((e) => {
    dragRef.current = null
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      // pointer capture already released
    }
  }, [])

  return (
    <div className="placement-editor">
      <div className="placement-box" style={{ width: boxWidth, height: boxHeight }}>
        <img
          src={design.url}
          alt={design.original_filename}
          draggable={false}
          className="placement-image"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          style={{
            width: imgWidth,
            height: imgHeight,
            left: placement.x * boxWidth,
            top: placement.y * boxHeight,
            transform: `translate(-50%, -50%) rotate(${placement.angle}deg)`,
          }}
        />
      </div>
      <div className="placement-controls">
        <label>
          Scale
          <input
            type="range"
            min="0.1"
            max="3"
            step="0.01"
            value={placement.scale}
            onChange={(e) => onChange({ ...placement, scale: parseFloat(e.target.value) })}
          />
        </label>
        <label>
          Rotate
          <input
            type="range"
            min="-180"
            max="180"
            step="1"
            value={placement.angle}
            onChange={(e) => onChange({ ...placement, angle: parseFloat(e.target.value) })}
          />
        </label>
        <button type="button" className="back" onClick={() => onChange(defaultPlacement(placement.position))}>
          Reset
        </button>
      </div>
      <p className="muted">
        Drag the artwork to reposition it. Print area: {printArea.width_px}×{printArea.height_px}px ({printArea.position}).
      </p>
    </div>
  )
}
