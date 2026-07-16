import Canvas from './Canvas.jsx'
import Inspector from './Inspector.jsx'
import Palette from './Palette.jsx'
import Toolbar from './Toolbar.jsx'

export default function App() {
  return (
    <div className="app">
      <Toolbar />
      <div className="workspace">
        <Palette />
        <Canvas />
        <Inspector />
      </div>
    </div>
  )
}
