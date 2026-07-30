import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import readline from 'node:readline'
import test from 'node:test'

test('MCP exposes only the focus read tools and forwards the scoped token', async (context) => {
  const requests = []
  const server = createServer((request, response) => {
    requests.push({ url: request.url, authorization: request.headers.authorization })
    response.setHeader('Content-Type', 'application/json')
    response.end(JSON.stringify(request.url.endsWith('/focus-brief/health')
      ? { status: 'ok', scope: 'focus-brief:read' }
      : { authoritative: true, reference_date: '2026-07-30', yesterday: { data_state: 'missing' }, trend: [] }))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  context.after(() => server.close())
  const address = server.address()
  const child = spawn(process.execPath, [fileURLToPath(new URL('./mcp-server.mjs', import.meta.url))], {
    env: { ...process.env, EMMA_FOCUS_BRIEF_BASE_URL: `http://127.0.0.1:${address.port}`, EMMA_FOCUS_BRIEF_TOKEN: 'emma_focus_brief_test' },
    stdio: ['pipe', 'pipe', 'inherit'],
  })
  context.after(() => child.kill())
  const lines = readline.createInterface({ input: child.stdout }); const responses = []
  lines.on('line', (line) => responses.push(JSON.parse(line)))
  async function request(message) {
    child.stdin.write(`${JSON.stringify(message)}\n`)
    for (let attempt = 0; attempt < 100; attempt += 1) { const found = responses.find((response) => response.id === message.id); if (found) return found; await new Promise((resolve) => setTimeout(resolve, 10)) }
    throw new Error(`No MCP response for ${message.method}`)
  }
  const initialized = await request({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26' } })
  assert.equal(initialized.result.serverInfo.name, 'emma-focus-morning-brief')
  const listed = await request({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} })
  assert.deepEqual(listed.result.tools.map((tool) => tool.name), ['check_connection', 'get_focus_brief'])
  const called = await request({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'get_focus_brief', arguments: { reference_date: '2026-07-30', trend_days: 7 } } })
  assert.equal(called.result.isError, undefined)
  assert.match(called.result.content[0].text, /"authoritative": true/)
  assert.equal(requests[0].authorization, 'Bearer emma_focus_brief_test')
  assert.match(requests[0].url, /focus-brief\?reference_date=2026-07-30&trend_days=7/)
})
