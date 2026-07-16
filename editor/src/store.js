// ============================================================================
// Editor state (Zustand). Holds the React Flow graph + selection + meta, and
// exposes the operations the toolbar + canvas + inspector call.
// ============================================================================

import { create } from 'zustand'
import {
  emptyFlow,
  newGraph,
  dslToFlow,
  flowToYaml,
} from './dslSerializer.js'
import { defaultDataFor, makeId } from './nodeTypes.js'

export const useStore = create((set, get) => ({
  flow: newGraph(),
  selectedId: null,
  dirty: false,
  currentFile: null,
  // server-side validation result from /dsl/validate
  validation: { status: 'idle', message: '', loadable: null },

  // ---- selection ----
  select: (id) => set({ selectedId: id }),

  // ---- graph mutations ----
  setFlow: (flow, opts = {}) =>
    set({ flow, dirty: !opts.silent, selectedId: null, currentFile: opts.file ?? null,
          validation: { status: 'idle', message: '', loadable: null } }),

  newDoc: () => set({ flow: newGraph(), dirty: false, selectedId: null, currentFile: null,
                      validation: { status: 'idle', message: '', loadable: null } }),

  clear: () => set({ flow: emptyFlow(), dirty: false, selectedId: null, currentFile: null }),

  addNode: (type, position) => {
    const id = makeId(type)
    const data = { ...defaultDataFor(type), __nodeType: type }
    const node = { id, type: 'dsl', position, data }
    set((s) => ({ flow: { ...s.flow, nodes: [...s.flow.nodes, node] }, dirty: true, selectedId: id }))
    return id
  },

  updateNodeData: (id, patch) =>
    set((s) => ({
      flow: {
        ...s.flow,
        nodes: s.flow.nodes.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, ...patch } } : n,
        ),
      },
      dirty: true,
    })),

  deleteNode: (id) =>
    set((s) => ({
      flow: {
        ...s.flow,
        nodes: s.flow.nodes.filter((n) => n.id !== id),
        edges: s.flow.edges.filter((e) => e.source !== id && e.target !== id),
      },
      dirty: true,
      selectedId: s.selectedId === id ? null : s.selectedId,
    })),

  // React Flow bulk callbacks
  onNodesChange: (changes) =>
    set((s) => ({ flow: { ...s.flow, nodes: applyChanges(s.flow.nodes, changes) } })),
  onEdgesChange: (changes) =>
    set((s) => ({ flow: { ...s.flow, edges: applyChanges(s.flow.edges, changes) } })),
  onConnect: (conn) =>
    set((s) => ({
      flow: {
        ...s.flow,
        edges: [
          ...s.flow.edges,
          {
            id: `e_${conn.source}_${conn.target}_${Math.random().toString(36).slice(2, 6)}`,
            source: conn.source,
            target: conn.target,
            sourceHandle: conn.sourceHandle || null,
            targetHandle: conn.targetHandle || null,
            animated: true,
          },
        ],
      },
      dirty: true,
    })),

  // ---- import / export ----
  importDsl: (dslText, file = null) => {
    const flow = dslToFlow(dslText)
    set({ flow, dirty: false, selectedId: null, currentFile: file,
          validation: { status: 'idle', message: '', loadable: null } })
    return flow
  },
  exportYaml: () => flowToYaml(get().flow),

  setMeta: (patch) => set((s) => ({ flow: { ...s.flow, meta: { ...s.flow.meta, ...patch } }, dirty: true })),
  setValidation: (v) => set({ validation: v }),
  markSaved: (file) => set({ dirty: false, currentFile: file }),
}))

// minimal React Flow change applier (position/select/remove) without the lib
function applyChanges(items, changes) {
  let out = items
  for (const c of changes) {
    if (c.type === 'remove') {
      out = out.filter((i) => i.id !== c.id)
    } else if (c.type === 'position' && c.position) {
      out = out.map((i) => (i.id === c.id ? { ...i, position: c.position, dragging: c.dragging } : i))
    } else if (c.type === 'select') {
      // handled via select(); no-op here to avoid clobbering store selection
    }
  }
  return out
}
