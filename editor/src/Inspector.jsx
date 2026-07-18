import { useStore } from './store.js'
import { NODE_TYPES } from './nodeTypes.js'

// ============================================================================
// Inspector: renders the editable fields for the currently-selected node.
// Each field kind gets its own input control. Nested dotted keys
// (e.g. "model.provider") are read/written through a small helper.
// ============================================================================

function getPath(obj, dotted) {
  return dotted.split('.').reduce((o, k) => (o == null ? o : o[k]), obj)
}
function setPath(obj, dotted, value) {
  const parts = dotted.split('.')
  const clone = Array.isArray(obj) ? [...obj] : { ...obj }
  let cur = clone
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i]
    cur[k] = Array.isArray(cur[k]) ? [...cur[k]] : { ...cur[k] }
    cur = cur[k]
  }
  cur[parts[parts.length - 1]] = value
  return clone
}

export default function Inspector({ open = false, onClose }) {
  const flow = useStore((s) => s.flow)
  const selectedId = useStore((s) => s.selectedId)
  const updateNodeData = useStore((s) => s.updateNodeData)
  const deleteNode = useStore((s) => s.deleteNode)

  const node = flow.nodes.find((n) => n.id === selectedId)

  if (!node) {
    return (
      <aside id="node-inspector" className={`inspector ${open ? 'open' : ''}`}>
        <div className="insp-head">
          <h3>Inspector</h3>
          <button type="button" className="inspector-close" onClick={onClose}>Close</button>
        </div>
        <div className="empty">Select a node to edit its fields.</div>
      </aside>
    )
  }

  const type = node.data.__nodeType || node.data.type
  const spec = NODE_TYPES[type]
  const data = node.data

  const setField = (field, value) => {
    // top-level key vs dotted nested key
    const patch = field.key.includes('.')
      ? setPath(data, field.key, value)
      : { [field.key]: value }
    updateNodeData(node.id, patch)
  }

  return (
    <aside id="node-inspector" className={`inspector ${open ? 'open' : ''}`}>
      <div className="insp-head">
        <h3>{spec?.label || type}</h3>
        <div className="insp-meta">
          <span className="node-id-badge">{node.id}</span>
          <button type="button" className="inspector-close" onClick={onClose}>Close</button>
        </div>
      </div>
      <p className="insp-desc">{spec?.description}</p>

      {spec?.fields.map((f) => (
        <FieldEditor key={f.key} field={f} value={getFieldValue(data, f)} onChange={(v) => setField(f, v)} />
      ))}

      <div className="insp-actions">
        <button className="danger" onClick={() => deleteNode(node.id)}>Delete node</button>
      </div>
    </aside>
  )
}

function getFieldValue(data, field) {
  if (field.key.includes('.')) return getPath(data, field.key) ?? field.default
  return data[field.key] ?? field.default
}

// ---------------------------------------------------------------------------
// Field editors by kind
// ---------------------------------------------------------------------------
function FieldEditor({ field, value, onChange }) {
  return (
    <div className="field">
      <label>
        {field.label}
        {field.hint && <span className="hint">{field.hint}</span>}
      </label>
      <FieldControl field={field} value={value} onChange={onChange} />
    </div>
  )
}

function FieldControl({ field, value, onChange }) {
  switch (field.kind) {
    case 'bool':
      return <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
    case 'select':
      return (
        <select value={value || ''} onChange={(e) => onChange(e.target.value)}>
          {field.options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      )
    case 'text':
      return <textarea value={value ?? ''} onChange={(e) => onChange(e.target.value)} rows={8} spellCheck={false} />
    case 'list':
      return <ListEditor value={value || []} onChange={onChange} />
    case 'kvlist':
    case 'variables':
    case 'grouplist':
    case 'caselist':
    case 'paramlist':
    case 'promptlist':
      return <CompoundEditor kind={field.kind} value={value || []} onChange={onChange} />
    case 'string':
    default:
      return <input value={value ?? ''} onChange={(e) => onChange(e.target.value)} spellCheck={false} />
  }
}

// Simple string list editor (e.g. code node output names).
function ListEditor({ value, onChange }) {
  const update = (i, v) => onChange(value.map((x, idx) => (idx === i ? v : x)))
  const add = () => onChange([...value, ''])
  const remove = (i) => onChange(value.filter((_, idx) => idx !== i))
  return (
    <div className="list-ed">
      {value.map((v, i) => (
        <div className="list-row" key={i}>
          <input value={v} onChange={(e) => update(i, e.target.value)} />
          <button className="mini danger" onClick={() => remove(i)}>×</button>
        </div>
      ))}
      <button className="mini" onClick={add}>+ add</button>
    </div>
  )
}

// Compound editors: each renders a small table with the right columns per kind.
function CompoundEditor({ kind, value, onChange }) {
  const cols = COMPOUND_COLS[kind] || []
  const update = (i, key, v) => onChange(value.map((row, idx) => (idx === i ? { ...row, [key]: v } : row)))
  const add = () => onChange([...value, cols.reduce((o, c) => ({ ...o, [c.key]: c.default ?? '' }), {})])
  const remove = (i) => onChange(value.filter((_, idx) => idx !== i))

  return (
    <div className="compound-ed">
      {value.map((row, i) => (
        <div className="compound-row" key={i}>
          {cols.map((c) => (
            <input
              key={c.key}
              placeholder={c.label}
              value={row[c.key] ?? ''}
              onChange={(e) => update(i, c.key, e.target.value)}
              title={c.label}
            />
          ))}
          <button className="mini danger" onClick={() => remove(i)}>×</button>
        </div>
      ))}
      <button className="mini" onClick={add}>+ add row</button>
    </div>
  )
}

const COMPOUND_COLS = {
  // start node variables: name + type + required
  variables: [
    { key: 'variable', label: 'name', default: '' },
    { key: 'type', label: 'type', default: 'text' },
    { key: 'label', label: 'label', default: '' },
    { key: 'required', label: 'required', default: false },
  ],
  // generic name -> selector (end outputs, code/template inputs, http headers)
  kvlist: [
    { key: 'variable', label: 'name', default: '' },
    { key: 'value_selector', label: 'selector', default: '' },
  ],
  grouplist: [
    { key: 'variable', label: 'name', default: '' },
    { key: 'value_selector', label: 'selector', default: '' },
  ],
  caselist: [
    { key: 'case_id', label: 'id', default: 'case_1' },
    { key: 'name', label: 'name', default: 'IF' },
    { key: 'logical_operator', label: 'op', default: 'and' },
  ],
  paramlist: [
    { key: 'name', label: 'name', default: '' },
    { key: 'type', label: 'type', default: 'string' },
    { key: 'description', label: 'desc', default: '' },
  ],
  promptlist: [
    { key: 'role', label: 'role', default: 'user' },
    { key: 'text', label: 'text', default: '' },
  ],
}
