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

const parsedUrl = new URL(baseUrl)
const isLanAddress = ['127.0.0.1', 'localhost', '::1'].includes(parsedUrl.hostname)
  || parsedUrl.hostname.startsWith('192.168.')
  || parsedUrl.hostname.startsWith('10.')
  || parsedUrl.hostname.match(/^172\.(1[6-9]|2\d|3[01])\./)
  || parsedUrl.hostname.endsWith('.local')

if (parsedUrl.protocol !== 'https:' && !isLanAddress) {
  throw new Error('Emma Focus morning-brief endpoint must use HTTPS (LAN addresses may use HTTP)')
}
if (process.platform !== 'darwin') throw new Error('Automatic secret storage currently requires macOS Keychain')

// Check if the endpoint is reachable and not being intercepted by a reverse proxy
console.log(`Checking endpoint: ${baseUrl}/focus-brief/health ...`)
const probeResponse = await fetch(`${baseUrl}/focus-brief/health`, {
  method: 'GET',
  redirect: 'manual',
  headers: { 'Accept': 'application/json' },
})
if (probeResponse.type === 'opaqueredirect' || (probeResponse.status >= 300 && probeResponse.status < 400)) {
  const location = probeResponse.headers.get('location') || 'unknown'
  console.error(`\n❌ Endpoint returned a redirect (HTTP ${probeResponse.status}) to: ${location}`)
  console.error('')
  if (location.includes('zconnect.cn')) {
    console.error('The ZConnect (极空间) remote access proxy is intercepting the request.')
    console.error('ZConnect requires a browser session cookie that CLI tools cannot provide.')
    console.error('')
    console.error('Fix: Use the LAN URL for token setup, for example:')
    console.error('  node configure.mjs --base-url http://192.168.6.108:8888/api/poc')
    console.error('')
    console.error('After obtaining the token on LAN, you can switch the base-url to the')
    console.error('ZConnect HTTPS URL for remote access; the Bearer token may still work')
    console.error('if ZConnect forwards Authorization headers.')
  } else {
    console.error('The endpoint redirected unexpectedly. Check the URL and try again.')
    console.error('If you are on the home network, try the LAN IP instead:')
    console.error('  node configure.mjs --base-url http://192.168.6.108:8888/api/poc')
  }
  process.exit(1)
}

const pin = await hiddenPrompt('Parent PIN (hidden): ')
const response = await fetch(`${baseUrl}/focus-brief/tokens`, {
  method: 'POST',
  redirect: 'manual',
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  body: JSON.stringify({ pin, label: 'Codex morning brief', expires_days: expiresDays })
})

// Handle redirect (ZConnect or other proxy intercepting POST)
if (response.type === 'opaqueredirect' || (response.status >= 300 && response.status < 400)) {
  const location = response.headers.get('location') || 'unknown'
  console.error(`\n❌ Token request redirected (HTTP ${response.status}) to: ${location}`)
  if (location.includes('zconnect.cn')) {
    console.error('ZConnect intercepted the POST. Run this command on your home LAN with the local URL:')
    console.error('  node configure.mjs --base-url http://192.168.6.108:8888/api/poc')
  }
  process.exit(1)
}

const text = await response.text(); let body
try { body = text ? JSON.parse(text) : {} } catch { body = { detail: text.slice(0, 500) } }
if (!response.ok || !body.token) {
  const detail = typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`
  throw new Error(`Emma Focus authorization failed: ${detail}`)
}
execFileSync('security', ['add-generic-password', '-U', '-a', 'codex', '-s', keychainService(baseUrl), '-w', body.token], { stdio: ['ignore', 'ignore', 'inherit'] })
const configPath = process.env.EMMA_FOCUS_BRIEF_CONFIG || join(homedir(), '.config', 'emma-focus-morning-brief', 'config.json')
mkdirSync(dirname(configPath), { recursive: true, mode: 0o700 }); writeFileSync(configPath, `${JSON.stringify({ baseUrl }, null, 2)}\n`, { mode: 0o600 }); chmodSync(configPath, 0o600)
process.stdout.write(`Emma Focus read-only morning brief configured; expires ${body.expires_at}.\n`)
