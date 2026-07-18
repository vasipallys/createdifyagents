import { useRef, useState } from 'react'
import { useStore } from './store.js'
import { listDslFiles, getDslFile, saveDslFile, validateDsl } from './api.js'

// Top toolbar: New / Import / Export / Validate / Save + dirty + validation badge.
export default function Toolbar() {
  const fileInput = useRef(null)
  const [busy, setBusy] = useState(false)
  const [list, setList] = useState([])
  const [showList, setShowList] = useState(false)

  const newDoc = useStore((s) => s.newDoc)
  const importDsl = useStore((s) => s.importDsl)
  const exportYaml = useStore((s) => s.exportYaml)
  const dirty = useStore((s) => s.dirty)
  const currentFile = useStore((s) => s.currentFile)
  const currentRevision = useStore((s) => s.currentRevision)
  const markSaved = useStore((s) => s.markSaved)
  const setValidation = useStore((s) => s.setValidation)
  const validation = useStore((s) => s.validation)

  const onImportFile = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => {
      try { importDsl(String(reader.result), f.name) } catch (err) { alert(`Parse error: ${err.message}`) }
    }
    reader.readAsText(f)
    e.target.value = ''
  }

  const onExport = () => {
    const yaml = exportYaml()
    const blob = new Blob([yaml], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = currentFile || 'graph.yml'
    a.click()
    URL.revokeObjectURL(url)
  }

  const onValidate = async () => {
    setBusy(true)
    try {
      const res = await validateDsl(exportYaml())
      setValidation({
        status: res.loadable ? 'ok' : 'error',
        message: res.error || (res.loadable ? 'Graph is loadable by graphon.' : 'Not loadable.'),
        loadable: res.loadable,
        deps: res.dependencies,
      })
    } catch (e) {
      setValidation({ status: 'error', message: `request failed: ${e.message}`, loadable: false })
    } finally {
      setBusy(false)
    }
  }

  const onOpenList = async () => {
    try {
      const res = await listDslFiles()
      setList(res.files || [])
      setShowList(true)
    } catch (e) { alert(`list failed: ${e.message}`) }
  }

  const onOpenFile = async (name) => {
    setBusy(true)
    try {
      const res = await getDslFile(name)
      importDsl(res.dsl, name, res.revision)
      setShowList(false)
    } catch (e) { alert(`load failed: ${e.message}`) }
    finally { setBusy(false) }
  }

  const onSave = async () => {
    let name = currentFile
    if (!name) {
      name = prompt('Save as (filename in /dsl):', 'my_graph.yml')
      if (!name) return
    }
    setBusy(true)
    try {
      const dsl = exportYaml()
      let res
      try {
        res = await saveDslFile(name, dsl, currentRevision)
      } catch (error) {
        if (!/DSL write API key/i.test(error.message)) throw error
        const key = prompt('Enter the DSL write API key for this browser session:')
        if (!key) throw error
        sessionStorage.setItem('story-pointer-dsl-key', key)
        res = await saveDslFile(name, dsl, currentRevision)
      }
      markSaved(name, res.revision)
      setValidation({ status: 'idle', message: '', loadable: null })
    } catch (e) { alert(`save failed: ${e.message}`) }
    finally { setBusy(false) }
  }

  const vBadge = validation.status === 'ok'
    ? <span className="badge ok">✓ valid</span>
    : validation.status === 'error'
      ? <span className="badge err" title={validation.message}>✗ invalid</span>
      : null

  return (
    <header className="toolbar">
      <div className="tb-left">
        <strong>🎯 Story Pointer</strong>
        <span className="sep">/</span>
        <span>DSL Editor</span>
      </div>
      <div className="tb-right">
        <button onClick={newDoc} title="New graph">New</button>
        <button onClick={() => fileInput.current?.click()} title="Import .yml">Import</button>
        <input type="file" ref={fileInput} accept=".yml,.yaml" onChange={onImportFile} hidden />
        <button onClick={onExport} title="Download as .yml">Export</button>
        <button onClick={onOpenList} title="Open from server /dsl">Open…</button>
        <button onClick={onValidate} disabled={busy} title="Validate with graphon">Validate</button>
        <button onClick={onSave} disabled={busy} className="primary">Save</button>
        <span className={'dirty ' + (dirty ? 'on' : '')}>{dirty ? '● unsaved' : 'saved'}</span>
        {currentFile && <span className="file-name">{currentFile}</span>}
        {vBadge}
      </div>

      {showList && (
        <div className="modal" onClick={() => setShowList(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h4>Open DSL file</h4>
            <ul className="file-list">
              {(list || []).map((f) => (
                <li key={f} onClick={() => onOpenFile(f)}>{f}</li>
              ))}
              {list.length === 0 && <li className="muted">No files in /dsl</li>}
            </ul>
            <button onClick={() => setShowList(false)}>Close</button>
          </div>
        </div>
      )}

      {validation.status !== 'idle' && (
        <div className={'val-bar ' + validation.status}>{validation.message}</div>
      )}
    </header>
  )
}
