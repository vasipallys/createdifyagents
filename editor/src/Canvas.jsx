import { useCallback, useRef } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { CanvasNode } from './CanvasNode.jsx'
import { useStore } from './store.js'

const nodeTypes = { dsl: CanvasNode }

function CanvasInner() {
  const flow = useStore((s) => s.flow)
  const selectedId = useStore((s) => s.selectedId)
  const onNodesChange = useStore((s) => s.onNodesChange)
  const onEdgesChange = useStore((s) => s.onEdgesChange)
  const onConnectStore = useStore((s) => s.onConnect)
  const addNode = useStore((s) => s.addNode)
  const select = useStore((s) => s.select)
  const deleteNode = useStore((s) => s.deleteNode)

  const wrapperRef = useRef(null)
  const { screenToFlowPosition } = useReactFlow()

  // drag-drop from the palette
  const onDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      const type = e.dataTransfer.getData('application/reactflow')
      if (!type) return
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addNode(type, position)
    },
    [addNode, screenToFlowPosition],
  )

  const handleConnect = useCallback(
    (conn) => onConnectStore(conn),
    [onConnectStore],
  )

  return (
    <div className="canvas-wrap" ref={wrapperRef}>
      <ReactFlow
        nodes={flow.nodes.map((n) => ({ ...n, selected: n.id === selectedId }))}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={(_, n) => select(n.id)}
        onPaneClick={() => select(null)}
        onNodeDoubleClick={(_, n) => select(n.id)}
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        deleteKeyCode={null}
        onNodesDelete={(nodes) => nodes.forEach((node) => deleteNode(node.id))}
      >
        <Background color="#2d3b50" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const t = n.data?.__nodeType
            return NODE_COLOR[t] || '#6e7681'
          }}
          maskColor="rgba(0,0,0,0.5)"
        />
      </ReactFlow>
    </div>
  )
}

const NODE_COLOR = {
  start: '#2ea043', end: '#6e7681', answer: '#0969da', llm: '#a371f7',
  'http-request': '#fb8f44', code: '#d29922', 'if-else': '#f85149',
  'template-transform': '#1f6feb', 'variable-aggregator': '#8957e5',
  assigner: '#bf8b70', 'list-operator': '#218bff',
  'question-classifier': '#7d8590', 'parameter-extractor': '#56d364', tool: '#e3b341',
}

export default function Canvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  )
}
