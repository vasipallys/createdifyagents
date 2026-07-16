import { PALETTE_GROUPS, NODE_TYPES } from './nodeTypes.js'

// Left sidebar: lists all 14 graphon node types grouped by category.
// Each item is draggable onto the canvas (HTML5 drag-drop -> Canvas.onDrop).
export default function Palette() {
  const onDragStart = (e, type) => {
    e.dataTransfer.setData('application/reactflow', type)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="palette">
      <h3>Nodes</h3>
      {PALETTE_GROUPS.map((group) => (
        <div className="palette-group" key={group.name}>
          <div className="palette-group-name">{group.name}</div>
          {group.types.map((type) => {
            const spec = NODE_TYPES[type]
            if (!spec) return null
            return (
              <div
                key={type}
                className="palette-item"
                draggable
                onDragStart={(e) => onDragStart(e, type)}
                title={spec.description}
                style={{ borderLeftColor: spec.color }}
              >
                <span className="palette-icon" style={{ color: spec.color }}>{spec.icon}</span>
                <span>{spec.label}</span>
              </div>
            )
          })}
        </div>
      ))}
    </aside>
  )
}
