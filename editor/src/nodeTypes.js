// ============================================================================
// graphon / Dify DSL node type catalogue.
// ============================================================================
// This is the single source of truth for the visual editor. Each entry drives:
//   - the palette (left sidebar) of draggable node types
//   - the default `data` object created when a node is dropped
//   - the per-field editors rendered in the Inspector panel
//
// The field descriptors use a small set of types:
//   { kind: 'string' | 'text' | 'bool' | 'select' | 'list' | 'kvlist' | 'variables' | 'edges' }
//
// These map directly onto the Dify DSL node shapes that graphon.dsl.loads()
// accepts (validated with `graphon.dsl.inspect`). See the reference graphs in
// /dsl/graph_http.yml and /dsl/graph_slim.yml.
// ============================================================================

export const NODE_TYPES = {
  start: {
    label: 'Start',
    color: '#2ea043',
    icon: '▶',
    description: 'Graph entry point. Declares the input variables.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Start' },
      { key: 'variables', label: 'Input variables', kind: 'variables', default: [] },
    ],
  },

  end: {
    label: 'End',
    color: '#6e7681',
    icon: '■',
    description: 'Graph terminator with typed outputs.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'End' },
      { key: 'outputs', label: 'Outputs (name -> selector)', kind: 'kvlist', default: [] },
    ],
  },

  answer: {
    label: 'Answer',
    color: '#0969da',
    icon: '✎',
    description: 'Emits a templated response string (streams to client).',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Answer' },
      { key: 'answer', label: 'Answer template', kind: 'text',
        default: '{{#start.title#}}', hint: 'Dify template syntax: {{#nodeId.var#}}' },
    ],
  },

  llm: {
    label: 'LLM (Slim)',
    color: '#a371f7',
    icon: '🤖',
    description: 'Native graphon LLM node. Requires Slim runtime + plugin.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'LLM' },
      { key: 'model.provider', label: 'Provider', kind: 'string', default: 'openai' },
      { key: 'model.name', label: 'Model', kind: 'string', default: 'gpt-4o-mini' },
      { key: 'model.mode', label: 'Mode', kind: 'select', default: 'chat',
        options: ['chat', 'completion'] },
      { key: 'model.completion_params.temperature', label: 'Temperature', kind: 'string', default: '0.2' },
      { key: 'model.completion_params.max_tokens', label: 'Max tokens', kind: 'string', default: '2400' },
      { key: 'prompt_template', label: 'Prompt (role/text per line)', kind: 'promptlist', default: [
        { role: 'system', text: 'You are a helpful assistant.' },
        { role: 'user', text: '{{#start.query#}}' },
      ] },
      { key: 'context.enabled', label: 'Context enabled', kind: 'bool', default: false },
      { key: 'vision.enabled', label: 'Vision enabled', kind: 'bool', default: false },
    ],
  },

  'http-request': {
    label: 'HTTP Request',
    color: '#fb8f44',
    icon: '🌐',
    description: 'POST/GET to any HTTP endpoint. Zero external binaries.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'HTTP Request' },
      { key: 'method', label: 'Method', kind: 'select', default: 'post',
        options: ['get', 'post', 'put', 'patch', 'delete'] },
      { key: 'url', label: 'URL', kind: 'string', default: '{{#start.req_url#}}' },
      { key: 'headers', label: 'Headers (JSON/template)', kind: 'text', default: '{{#start.req_headers#}}' },
      { key: 'body_type', label: 'Body type', kind: 'select', default: 'json',
        options: ['none', 'json', 'raw', 'form', 'x-www-form-urlencoded'] },
      { key: 'json_body', label: 'JSON body (template)', kind: 'text', default: '{{#start.req_body#}}' },
      { key: 'timeout', label: 'Timeout (s)', kind: 'string', default: '60' },
    ],
  },

  code: {
    label: 'Code',
    color: '#d29922',
    icon: '{ }',
    description: 'Sandboxed Python. Define main(...) with typed inputs/outputs.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Code' },
      { key: 'code_language', label: 'Language', kind: 'select', default: 'python3',
        options: ['python3'] },
      { key: 'variables', label: 'Inputs (name -> selector)', kind: 'kvlist', default: [] },
      { key: 'outputs', label: 'Outputs (names)', kind: 'list', default: ['result'] },
      { key: 'code', label: 'Python code', kind: 'text', default:
        'def main(arg) -> dict:\n    return {"result": arg}' },
    ],
  },

  'if-else': {
    label: 'If/Else',
    color: '#f85149',
    icon: '◇',
    description: 'Branch on conditions. Each case -> a named output edge.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'If/Else' },
      { key: 'cases', label: 'Cases (name | conditions JSON)', kind: 'caselist', default: [
        { case_id: 'true', name: 'IF', logical_operator: 'and', conditions: [] },
      ] },
    ],
  },

  'template-transform': {
    label: 'Template Transform',
    color: '#1f6feb',
    icon: '⚙',
    description: 'Render a Jinja2 template against input variables.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Template Transform' },
      { key: 'variables', label: 'Variables (name -> selector)', kind: 'kvlist', default: [] },
      { key: 'template', label: 'Jinja2 template', kind: 'text', default: 'Hello {{ name }}' },
    ],
  },

  'variable-aggregator': {
    label: 'Variable Aggregator',
    color: '#8957e5',
    icon: '∑',
    description: 'Merge variables from multiple upstream branches.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Variable Aggregator' },
      { key: 'variables', label: 'Groups (name -> [selectors])', kind: 'grouplist', default: [] },
    ],
  },

  assigner: {
    label: 'Assigner',
    color: '#bf8b70',
    icon: '←',
    description: 'Write a value to a variable in the pool (v1/v2 auto).',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Assigner' },
      { key: 'items', label: 'Assignments (var -> value/template)', kind: 'kvlist', default: [] },
    ],
  },

  'list-operator': {
    label: 'List Operator',
    color: '#218bff',
    icon: '☰',
    description: 'Filter/sort/slice/aggregate a list variable.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'List Operator' },
      { key: 'variable', label: 'Input list selector', kind: 'string', default: '' },
      { key: 'operator', label: 'Operator', kind: 'select', default: 'filter',
        options: ['filter', 'sort', 'slice', 'aggregate'] },
    ],
  },

  'question-classifier': {
    label: 'Question Classifier',
    color: '#7d8590',
    icon: '?',
    description: 'Classify input into one of N classes (Slim-backed).',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Question Classifier' },
      { key: 'model.provider', label: 'Provider', kind: 'string', default: 'openai' },
      { key: 'model.name', label: 'Model', kind: 'string', default: 'gpt-4o-mini' },
      { key: 'classes', label: 'Classes (name | instruction)', kind: 'kvlist', default: [] },
    ],
  },

  'parameter-extractor': {
    label: 'Parameter Extractor',
    color: '#56d364',
    icon: '⊕',
    description: 'Extract structured parameters (Slim-backed).',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Parameter Extractor' },
      { key: 'model.provider', label: 'Provider', kind: 'string', default: 'openai' },
      { key: 'model.name', label: 'Model', kind: 'string', default: 'gpt-4o-mini' },
      { key: 'parameters', label: 'Parameters (name | type | desc)', kind: 'paramlist', default: [] },
    ],
  },

  tool: {
    label: 'Tool',
    color: '#e3b341',
    icon: '🔧',
    description: 'Invoke a Slim plugin tool.',
    fields: [
      { key: 'title', label: 'Title', kind: 'string', default: 'Tool' },
      { key: 'provider_name', label: 'Provider name', kind: 'string', default: '' },
      { key: 'tool_name', label: 'Tool name', kind: 'string', default: '' },
      { key: 'tool_parameters', label: 'Tool parameters (name -> value)', kind: 'kvlist', default: [] },
    ],
  },
}

// Ordered groups for the palette UI.
export const PALETTE_GROUPS = [
  { name: 'Lifecycle', types: ['start', 'end', 'answer'] },
  { name: 'Logic', types: ['code', 'if-else', 'template-transform', 'variable-aggregator', 'assigner', 'list-operator'] },
  { name: 'LLM & Tools', types: ['llm', 'question-classifier', 'parameter-extractor', 'tool', 'http-request'] },
]

// Build a default data object for a freshly-dropped node.
export function defaultDataFor(type) {
  const spec = NODE_TYPES[type]
  if (!spec) throw new Error(`Unknown node type: ${type}`)
  const data = { type, title: spec.label }
  for (const f of spec.fields) {
    const value = (f.kind === 'list' || f.kind === 'kvlist' || f.kind === 'variables' ||
      f.kind === 'grouplist' || f.kind === 'caselist' || f.kind === 'paramlist' ||
      f.kind === 'promptlist')
      ? (f.default ? structuredClone(f.default) : [])
      : (f.default ?? '')
    if (f.key.includes('.')) {
      setNested(data, f.key, value)
      continue
    }
    if (f.kind === 'list' || f.kind === 'kvlist' || f.kind === 'variables' ||
        f.kind === 'grouplist' || f.kind === 'caselist' || f.kind === 'paramlist' ||
        f.kind === 'promptlist') {
      data[f.key] = value
    } else {
      data[f.key] = value
    }
  }
  return data
}

function setNested(target, dotted, value) {
  const parts = dotted.split('.')
  let cursor = target
  for (const part of parts.slice(0, -1)) {
    cursor[part] = cursor[part] && typeof cursor[part] === 'object' ? cursor[part] : {}
    cursor = cursor[part]
  }
  cursor[parts.at(-1)] = value
}

export function makeId(type) {
  return `${type}_${Math.random().toString(36).slice(2, 8)}`
}
