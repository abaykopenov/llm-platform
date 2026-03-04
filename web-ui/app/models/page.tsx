'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || ''

interface OllamaModel {
  name: string
  size_gb: number
  family: string
  parameters: string
  quantization: string
}

interface LoadedModel {
  name: string
  size_gb: number
  vram_gb: number
}

interface LLMStatus {
  strategy: string
  default_model: string
  endpoints: Array<{ name: string; url: string; healthy: boolean }>
  models: OllamaModel[]
  loaded_models: LoadedModel[]
}

export default function ModelsPage() {
  const [status, setStatus] = useState<LLMStatus | null>(null)
  const [pullName, setPullName] = useState('')
  const [pulling, setPulling] = useState(false)
  const [pullProgress, setPullProgress] = useState('')

  const fetchData = async () => {
    try {
      const resp = await fetch(`${API}/api/llm/status`)
      setStatus(await resp.json())
    } catch (e) { console.error(e) }
  }

  useEffect(() => { fetchData() }, [])

  const pullModel = async () => {
    if (!pullName.trim() || pulling) return
    setPulling(true)
    setPullProgress('Начинаю загрузку...')

    try {
      const resp = await fetch(`${API}/api/models/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: pullName }),
      })

      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const text = decoder.decode(value, { stream: true })
          for (const line of text.split('\n')) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') {
                setPullProgress('✅ Модель загружена!')
                continue
              }
              try {
                const parsed = JSON.parse(data)
                if (parsed.status) {
                  let msg = parsed.status
                  if (parsed.completed && parsed.total) {
                    const pct = Math.round((parsed.completed / parsed.total) * 100)
                    const mb = Math.round(parsed.completed / 1024 / 1024)
                    const totalMb = Math.round(parsed.total / 1024 / 1024)
                    msg += ` — ${mb}/${totalMb} МБ (${pct}%)`
                  }
                  setPullProgress(msg)
                }
              } catch {}
            }
          }
        }
      }
    } catch (e: any) {
      setPullProgress('❌ Ошибка: ' + e.message)
    } finally {
      setPulling(false)
      fetchData()
    }
  }

  const deleteModel = async (name: string) => {
    if (!confirm(`Удалить модель ${name}?`)) return
    try {
      await fetch(`${API}/api/models/${name}`, { method: 'DELETE' })
      fetchData()
    } catch (e) { console.error(e) }
  }

  return (
    <div className="container">
      <div className="header"><h1>⚡ LLM Platform</h1></div>
      <div className="nav-tabs">
        <Link href="/" className="nav-tab">💬 Чат</Link>
        <Link href="/files" className="nav-tab">📁 Файлы</Link>
        <span className="nav-tab active">🤖 Модели</span>
        <Link href="/monitoring" className="nav-tab">📊 Мониторинг</Link>
      </div>

      {/* Pull Model */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">📥 Загрузить модель</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            className="chat-input"
            placeholder="Название модели, например: gemma3:4b, qwen2.5:7b, llama3.1:8b"
            value={pullName}
            onChange={e => setPullName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && pullModel()}
            style={{ minHeight: 42, maxHeight: 42 }}
          />
          <button className="chat-send" onClick={pullModel} disabled={pulling} style={{ padding: '0 20px' }}>
            {pulling ? '⏳' : '📥 Pull'}
          </button>
        </div>
        {pullProgress && (
          <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--bg3)', borderRadius: 8, fontSize: 13, color: 'var(--text2)' }}>
            {pullProgress}
          </div>
        )}
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text3)' }}>
          Популярные: gemma3:4b · qwen2.5:7b · qwen2.5:14b · llama3.1:8b · nomic-embed-text
        </div>
      </div>

      {/* Endpoints Status */}
      {status && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">🚀 Inference Engine</div>
          <div style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 12 }}>
            Backend: Ollama · Модель по умолчанию: {status.default_model}
          </div>
          {status.endpoints.map((ep, i) => (
            <div key={i} className="llm-endpoint">
              <div className={`ep-dot ${ep.healthy ? 'ok' : 'fail'}`} />
              <div style={{ flex: 1 }}>
                <div className="ep-name">{ep.name}</div>
                <div className="ep-meta">{ep.url}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Loaded Models (in GPU) */}
      {status?.loaded_models && status.loaded_models.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">⚡ Загружено в GPU</div>
          {status.loaded_models.map((m, i) => (
            <div key={i} className="llm-endpoint">
              <div className="ep-dot ok" />
              <div style={{ flex: 1 }}>
                <div className="ep-name">{m.name}</div>
                <div className="ep-meta">VRAM: {m.vram_gb} ГБ · Размер: {m.size_gb} ГБ</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Installed Models */}
      <div className="card-title" style={{ marginBottom: 12, paddingLeft: 4 }}>📦 Установленные модели</div>
      <div className="grid">
        {status?.models.map((m, i) => (
          <div key={i} className="model-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <div>
                <div className="model-name">{m.name}</div>
                <div className="model-meta">
                  {m.parameters && <span>🧮 {m.parameters}</span>}
                  {m.family && <span> · 🏷️ {m.family}</span>}
                  {m.quantization && <span> · 📦 {m.quantization}</span>}
                </div>
                <div className="model-meta" style={{ marginTop: 4 }}>
                  💾 {m.size_gb} ГБ
                </div>
              </div>
              <button className="file-delete" onClick={() => deleteModel(m.name)}>Удалить</button>
            </div>
          </div>
        ))}
        {(!status?.models || status.models.length === 0) && (
          <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text3)' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
            <div>Нет установленных моделей</div>
            <div style={{ fontSize: 13, marginTop: 8 }}>
              Загрузите модель через форму выше, например: <strong>gemma3:4b</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
