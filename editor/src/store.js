// ============================================================================
// Editor state (Zustand). Holds the React Flow graph + selection + meta, and
// exposes the operations the toolbar + canvas + inspector call.
// ============================================================================

import { create } from 'zustand'
import { applyEdgeChanges, applyNodeChanges } from 'reactflow'
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
  currentRevision: null,
  // server-side validation result from /dsl/validate
  validation: { status: 'idle', message: '', loadable: null },

  // ---- selection ----
  select: (id) => set({ selectedId: id }),

  // ---- graph mutations ----
  setFlow: (flow, opts = {}) =>
    set({ flow, dirty: !opts.silent, selectedId: null, currentFile: opts.file ?? null,
          currentRevision: opts.revision ?? null,
          validation: { status: 'idle', message: '', loadable: null } }),

  newDoc: () => set({ flow: newGraph(), dirty: false, selectedId: null, currentFile: null,
                      currentRevision: null,
                      validation: { status: 'idle', message: '', loadable: null } }),

  clear: () => set({ flow: emptyFlow(), dirty: false, selectedId: null, currentFile: null,
                     currentRevision: null }),

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
    set((s) => ({
      flow: { ...s.flow, nodes: applyNodeChanges(changes, s.flow.nodes) },
      // Dimension/selection updates are React Flow bookkeeping. Only user
      // mutations should mark the graph as changed.
      dirty: s.dirty || changes.some((c) => c.type === 'position' || c.type === 'remove'),
    })),
  onEdgesChange: (changes) =>
    set((s) => ({
      flow: { ...s.flow, edges: applyEdgeChanges(changes, s.flow.edges) },
      dirty: s.dirty || changes.some((c) => c.type !== 'select'),
    })),
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
  importDsl: (dslText, file = null, revision = null) => {
    const flow = dslToFlow(dslText)
    set({ flow, dirty: false, selectedId: null, currentFile: file, currentRevision: revision,
          validation: { status: 'idle', message: '', loadable: null } })
    return flow
  },
  exportYaml: () => flowToYaml(get().flow),

  setMeta: (patch) => set((s) => ({ flow: { ...s.flow, meta: { ...s.flow.meta, ...patch } }, dirty: true })),
  setValidation: (v) => set({ validation: v }),
  markSaved: (file, revision) => set({ dirty: false, currentFile: file,
                                       currentRevision: revision ?? null }),
}))
