import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { NODE_TYPES } from './nodeTypes.js'

// The single React Flow node renderer. Styling is driven by the node's
// data.type (start/end/answer/llm/code/...) so every graphon node kind gets a
// distinct color + icon. Each node has a target handle (left) and source
// handle (right) for dragging edges.
function CanvasNodeInner({ data, selected, id }) {
  const type = data.__nodeType || data.type
  const spec = NODE_TYPES[type] || { label: type, color: '#6e7681', icon: '?' }
  const title = data.title || spec.label

  return (
    <div
      className="dsl-node"
      style={{
        borderColor: selected ? spec.color : 'var(--border)',
        boxShadow: selected ? `0 0 0 2px ${spec.color}55` : 'none',
      }}
      title={spec.description || ''}
    >
      <Handle type="target" position={Position.Left} className="dsl-handle" />
      <div className="dsl-node-head" style={{ background: spec.color }}>
        <span className="dsl-node-icon">{spec.icon}</span>
        <span className="dsl-node-type">{spec.label}</span>
      </div>
      <div className="dsl-node-body">
        <div className="dsl-node-title">{title}</div>
        <div className="dsl-node-id">{id}</div>
      </div>
      <Handle type="source" position={Position.Right} className="dsl-handle" />
    </div>
  )
}

export const CanvasNode = memo(CanvasNodeInner)
