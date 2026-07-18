import { describe, expect, it } from 'vitest'

import { dslToFlow, flowToDsl } from './dslSerializer.js'
import { defaultDataFor } from './nodeTypes.js'


describe('node defaults', () => {
  it('materializes dotted LLM defaults for new nodes', () => {
    const data = defaultDataFor('llm')

    expect(data.model).toEqual({
      provider: 'openai',
      name: 'gpt-4o-mini',
      mode: 'chat',
      completion_params: { temperature: '0.2', max_tokens: '2400' },
    })
    expect(data.context).toEqual({ enabled: false })
    expect(data.vision).toEqual({ enabled: false })
  })

  it('deep-clones compound defaults between nodes', () => {
    const first = defaultDataFor('llm')
    const second = defaultDataFor('llm')

    first.prompt_template[0].text = 'changed'
    expect(second.prompt_template[0].text).toBe('You are a helpful assistant.')
  })
})


describe('DSL round trips', () => {
  it('preserves unknown document, graph, node, and edge metadata', () => {
    const input = {
      kind: 'graph',
      version: '2026-07',
      x_extension: { owner: 'platform' },
      dependencies: [{ type: 'marketplace', value: { plugin: 'sample' } }],
      graph: {
        viewport: { x: 10, y: 20, zoom: 0.8 },
        nodes: [{
          id: 'start',
          custom_wrapper: 'keep-me',
          __pos: { x: 100, y: 200 },
          data: { type: 'start', title: 'Start', variables: [], vendor_data: { enabled: true } },
        }],
        edges: [{
          id: 'original-edge-id',
          source: 'start',
          target: 'start',
          sourceHandle: 'yes',
          vendor_edge: 42,
        }],
      },
    }

    const output = flowToDsl(dslToFlow(input))

    expect(output.version).toBe('2026-07')
    expect(output.x_extension).toEqual({ owner: 'platform' })
    expect(output.graph.viewport).toEqual({ x: 10, y: 20, zoom: 0.8 })
    expect(output.graph.nodes[0].custom_wrapper).toBe('keep-me')
    expect(output.graph.nodes[0].data.vendor_data).toEqual({ enabled: true })
    expect(output.graph.edges[0].vendor_edge).toBe(42)
    expect(output.graph.edges[0].sourceHandle).toBe('yes')
  })
})
