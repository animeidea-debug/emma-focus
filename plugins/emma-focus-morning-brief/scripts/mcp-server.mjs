#!/usr/bin/env node

import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import readline from 'node:readline'

function readConfig() {
  const configPath = process.env.EMMA_FOCUS_BRIEF_CONFIG || join(homedir(), '.config', 'emma-focus-morning-brief', 'config.json')
  let file = {}
  try { file = JSON.parse(readFileSync(configPath, 'utf8')) } catch (error) { if (error?.code !== 'ENOENT') throw error }
  const baseUrl = String(process.env.EMMA_FOCUS_BRIEF_BASE_URL || file.baseUrl || '').replace(/\/+$/, '')
  if (baseUrl) {
    const parsed = new URL(baseUrl)
    const localHttp = parsed.protocol === 'http:' && ['127.0.0.1', 'localhost', '::1'].includes(parsed.hostname)
    if (parsed.protocol !== 'https:' && !localHttp) throw new Error('Emma Focus morning-brief endpoint must use HTTPS')
  }
  return { baseUrl }
}

function keychainService(baseUrl) {
  return `emma-focus-morning-brief-${createHash('sha256').update(baseUrl).digest('hex').slice(0, 16)}`
}

function readToken(baseUrl) {
  if (process.env.EMMA_FOCUS_BRIEF_TOKEN) return process.env.EMMA_FOCUS_BRIEF_TOKEN
  if (process.platform !== 'darwin') throw new Error('EMMA_FOCUS_BRIEF_TOKEN is required outside macOS')
  try {
    return execFileSync('security', ['find-generic-password', '-a', 'codex', '-s', keychainService(baseUrl), '-w'], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
  } catch { throw new Error('Emma Focus morning-brief authorization is missing; ask a parent to run configure.mjs') }
}

async function apiRequest(path) {
  const { baseUrl } = readConfig()
  if (!baseUrl) throw new Error('Emma Focus morning-brief endpoint is not configured')
  const response = await fetch(`${baseUrl}${path}`, { headers: { Authorization: `Bearer ${readToken(baseUrl)}`, Accept: 'application/json' } })
  const text = await response.text()
  let body
  try { body = text ? JSON.parse(text) : {} } catch { body = { detail: text } }
  if (!response.ok) throw new Error(`Emma Focus read failed: ${typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`}`)
  return body
}

const tools = [
  { name: 'check_connection', description: 'Check the configured read-only Emma Focus morning-brief connection and authorization.', inputSchema: { type: 'object', additionalProperties: false, properties: {} } },
  { name: 'get_focus_brief', description: 'Read reviewed focus facts, wallet changes, balances, and a seven-day trend. This tool cannot modify Emma Focus.', inputSchema: { type: 'object', additionalProperties: false, properties: { reference_date: { type: 'string', description: 'Asia/Shanghai reference date in YYYY-MM-DD; defaults to today.' }, trend_days: { type: 'integer', minimum: 1, maximum: 14, default: 7 } } } },
]

async function callTool(name, args = {}) {
  if (name === 'check_connection') return apiRequest('/focus-brief/health')
  if (name === 'get_focus_brief') {
    const query = new URLSearchParams()
    if (args.reference_date) query.set('reference_date', String(args.reference_date))
    query.set('trend_days', String(args.trend_days ?? 7))
    return apiRequest(`/focus-brief?${query}`)
  }
  throw new Error(`Unknown tool: ${name}`)
}

function reply(message) { process.stdout.write(`${JSON.stringify(message)}\n`) }
const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
for await (const line of input) {
  if (!line.trim()) continue
  let request
  try {
    request = JSON.parse(line)
    if (request.method === 'notifications/initialized') continue
    if (request.method === 'initialize') { reply({ jsonrpc: '2.0', id: request.id, result: { protocolVersion: request.params?.protocolVersion || '2025-03-26', capabilities: { tools: {} }, serverInfo: { name: 'emma-focus-morning-brief', version: '0.1.0' } } }); continue }
    if (request.method === 'tools/list') { reply({ jsonrpc: '2.0', id: request.id, result: { tools } }); continue }
    if (request.method === 'tools/call') {
      try { const result = await callTool(request.params?.name, request.params?.arguments); reply({ jsonrpc: '2.0', id: request.id, result: { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] } }) }
      catch (error) { reply({ jsonrpc: '2.0', id: request.id, result: { isError: true, content: [{ type: 'text', text: error instanceof Error ? error.message : String(error) }] } }) }
      continue
    }
    reply({ jsonrpc: '2.0', id: request.id, error: { code: -32601, message: 'Method not found' } })
  } catch (error) { reply({ jsonrpc: '2.0', id: request?.id ?? null, error: { code: -32603, message: error instanceof Error ? error.message : String(error) } }) }
}
