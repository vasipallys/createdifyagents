import { useEffect, useState } from 'react'
import Canvas from './Canvas.jsx'
import Inspector from './Inspector.jsx'
import Palette from './Palette.jsx'
import Toolbar from './Toolbar.jsx'
import { useStore } from './store.js'

export default function App() {
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const selectedId = useStore((state) => state.selectedId)

  useEffect(() => {
    if (selectedId) setInspectorOpen(true)
  }, [selectedId])

  return (
    <div className="app">
      <Toolbar />
      <div className="workspace">
        <Palette />
        <Canvas />
        <button
          type="button"
          className="inspector-toggle"
          aria-expanded={inspectorOpen}
          aria-controls="node-inspector"
          onClick={() => setInspectorOpen((open) => !open)}
        >
          {inspectorOpen ? 'Close inspector' : 'Open inspector'}
        </button>
        <Inspector open={inspectorOpen} onClose={() => setInspectorOpen(false)} />
      </div>
    </div>
  )
}
