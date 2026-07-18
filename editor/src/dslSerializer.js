// ============================================================================
// DSL <-> React Flow conversion.
// ============================================================================
// graphon's DSL shape (validated against graphon.dsl.inspect):
//   kind: graph
//   dependencies: [{ type, value: {...} }]
//   graph:
//     nodes: [{ id, data: { type, title, ...fields } }]
//     edges: [{ source, target }]
//
// React Flow's shape:
//   nodes: [{ id, type, position, data }]
//   edges: [{ id, source, target, sourceHandle, targetHandle }]
//
// This module converts between the two losslessly for all the fields the
// editor understands, and preserves unknown fields on import (round-trip safe).
// ============================================================================

import yaml from 'js-yaml'

// ---------------------------------------------------------------------------
// DSL -> React Flow
// ---------------------------------------------------------------------------
export function dslToFlow(dslText) {
  const doc = typeof dslText === 'string' ? yaml.load(dslText) : dslText
  if (!doc || doc.kind !== 'graph' || !doc.graph) {
    throw new Error('Not a graphon graph DSL (expected kind: graph with a graph: block).')
  }

  const rawNodes = doc.graph.nodes || []
  const rawEdges = doc.graph.edges || []

  // Lay out nodes in a simple left-to-right cascade if no positions are stored.
  const colCounts = {}
  const nodes = rawNodes.map((n, i) => {
    const pos = n.__pos || {}
    let x = pos.x
    let y = pos.y
    if (x == null || y == null) {
      const col = i % 4
      const row = Math.floor(i / 4)
      colCounts[col] = (colCounts[col] || 0) + 1
      x = 80 + col * 320
      y = 80 + row * 220 + (colCounts[col] - 1) * 20
    }
    return {
      id: n.id,
      type: 'dsl', // single React Flow renderer; the node's data.type drives styling
      position: { x, y },
      data: { ...n.data, __nodeType: n.data?.type || 'unknown' },
      _dslRaw: n,
    }
  })

  const edges = rawEdges.map((e, i) => ({
    id: e.id || `e_${e.source}_${e.target}_${i}`,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle || null,
    targetHandle: e.targetHandle || null,
    animated: true,
    data: e.data || {},
    _dslRaw: e,
  }))

  return {
    nodes,
    edges,
    meta: {
      kind: doc.kind,
      dependencies: doc.dependencies || [],
      raw: doc, // keep full doc so unknown top-level keys survive export
    },
  }
}

// ---------------------------------------------------------------------------
// React Flow -> DSL
// ---------------------------------------------------------------------------
export function flowToDsl({ nodes, edges, meta }) {
  const cleanNodes = nodes.map((n) => {
    const data = { ...n.data }
    delete data.__nodeType // internal UI-only flag
    const node = { ...(n._dslRaw || {}), id: n.id, data }
    // persist positions so re-import keeps the layout
    node.__pos = { x: Math.round(n.position.x), y: Math.round(n.position.y) }
    return node
  })

  const cleanEdges = edges.map((e) => {
    const out = { ...(e._dslRaw || {}), source: e.source, target: e.target }
    delete out.id
    if (e.sourceHandle) out.sourceHandle = e.sourceHandle
    if (e.targetHandle) out.targetHandle = e.targetHandle
    if (e.data && Object.keys(e.data).length) out.data = e.data
    return out
  })

  const raw = meta?.raw && typeof meta.raw === 'object' ? structuredClone(meta.raw) : {}
  const doc = {
    ...raw,
    kind: meta?.kind || raw.kind || 'graph',
    dependencies: meta?.dependencies || raw.dependencies || [],
    graph: { ...(raw.graph || {}), nodes: cleanNodes, edges: cleanEdges },
  }
  return doc
}

export function flowToYaml(flow) {
  const doc = flowToDsl(flow)
  return yaml.dump(doc, {
    indent: 2,
    lineWidth: 100,
    noRefs: true,
    sortKeys: false,
  })
}

// ---------------------------------------------------------------------------
// Empty graph + minimal graph helpers
// ---------------------------------------------------------------------------
export function emptyFlow() {
  return {
    nodes: [],
    edges: [],
    meta: { kind: 'graph', dependencies: [], raw: null },
  }
}

export function newGraph() {
  const start = {
    id: 'start',
    type: 'dsl',
    position: { x: 120, y: 200 },
    data: { __nodeType: 'start', type: 'start', title: 'Start', variables: [] },
  }
  const answer = {
    id: 'answer',
    type: 'dsl',
    position: { x: 540, y: 200 },
    data: { __nodeType: 'answer', type: 'answer', title: 'Answer', answer: '{{#start.title#}}' },
  }
  return {
    nodes: [start, answer],
    edges: [{ id: 'e_start_answer', source: 'start', target: 'answer', animated: true }],
    meta: { kind: 'graph', dependencies: [], raw: null },
  }
}
