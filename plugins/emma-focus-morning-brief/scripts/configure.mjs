#!/usr/bin/env node

import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { chmodSync, mkdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

function argument(name, fallback = '') { const index = process.argv.indexOf(`--${name}`); return index >= 0 ? process.argv[index + 1] : fallback }
function keychainService(baseUrl) { return `emma-focus-morning-brief-${createHash('sha256').update(baseUrl).digest('hex').slice(0, 16)}` }
async function hiddenPrompt(label) {
  if (!process.stdin.isTTY) throw new Error('PIN entry requires an interactive terminal')
  process.stdout.write(label); process.stdin.setRawMode(true); process.stdin.resume(); process.stdin.setEncoding('utf8')
  return new Promise((resolve, reject) => { let value = ''; const onData = (character) => {
    if (character === '\u0003') { process.stdin.setRawMode(false); process.stdin.pause(); reject(new Error('Cancelled')); return }
    if (character === '\r' || character === '\n') { process.stdin.off('data', onData); process.stdin.setRawMode(false); process.stdin.pause(); process.stdout.write('\n'); resolve(value); return }
    if (character === '\u007f') { value = value.slice(0, -1); return }; value += character
  }; process.stdin.on('data', onData) })
}

const baseUrl = argument('base-url').replace(/\/+$/, '')
const expiresDays = Number(argument('expires-days', '90'))
if (!baseUrl) throw new Error('Usage: node configure.mjs --base-url https://HOST/api/poc [--expires-days 90]')
if (new URL(baseUrl).protocol !== 'https:') throw new Error('Emma Focus morning-brief endpoint must use HTTPS')
if (process.platform !== 'darwin') throw new Error('Automatic secret storage currently requires macOS Keychain')
const pin = await hiddenPrompt('Parent PIN (hidden): ')
const response = await fetch(`${baseUrl}/focus-brief/tokens`, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ pin, label: 'Codex morning brief', expires_days: expiresDays }) })
const text = await response.text(); let body
try { body = text ? JSON.parse(text) : {} } catch { body = { detail: text } }
if (!response.ok || !body.token) throw new Error(typeof body.detail === 'string' ? body.detail : `Emma Focus authorization failed (${response.status})`)
execFileSync('security', ['add-generic-password', '-U', '-a', 'codex', '-s', keychainService(baseUrl), '-w', body.token], { stdio: ['ignore', 'ignore', 'inherit'] })
const configPath = process.env.EMMA_FOCUS_BRIEF_CONFIG || join(homedir(), '.config', 'emma-focus-morning-brief', 'config.json')
mkdirSync(dirname(configPath), { recursive: true, mode: 0o700 }); writeFileSync(configPath, `${JSON.stringify({ baseUrl }, null, 2)}\n`, { mode: 0o600 }); chmodSync(configPath, 0o600)
process.stdout.write(`Emma Focus read-only morning brief configured; expires ${body.expires_at}.\n`)
