'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || ''

interface ModelInfo {
  name: string
  size_gb: number
  family: string
  parameters: string
  quantization: string
  node?: string
  node_url?: string
}

interface LoadedModel {
  name: string
  size_gb: number
  vram_gb: number
  node?: string
}

interface EndpointInfo {
  name: string
  url: string
  healthy: boolean
  server_type: string
  models_count: number
  active_requests: number
  total_requests: number
  error?: string
}

interface ClusterInfo {
  total_nodes: number
  healthy_nodes: number
  total_models: number
}

interface LLMStatus {
  strategy: string
  default_model: string
  endpoints: EndpointInfo[]
  models: ModelInfo[]
  loaded_models: LoadedModel[]
  cluster?: ClusterInfo
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

  useEffect(() => {
    fetchData()
    // Auto-refresh every 15 seconds
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [])

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
              } catch { }
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

  const hasOllamaNodes = status?.endpoints.some(ep => ep.server_type === 'ollama') ?? false

  return (
    <div className="container">
      <div className="header"><h1>⚡ LLM Platform</h1></div>
      <div className="nav-tabs">
        <Link href="/" className="nav-tab">💬 Чат</Link>
        <Link href="/files" className="nav-tab">📁 Файлы</Link>
        <span className="nav-tab active">🤖 Модели</span>
        <Link href="/monitoring" className="nav-tab">📊 Мониторинг</Link>
      </div>

      {/* Cluster Status */}
      {status?.cluster && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">🌐 Кластер</div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <div style={{ textAlign: 'center', padding: '8px 16px', background: 'var(--bg3)', borderRadius: 8 }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: status.cluster.healthy_nodes > 0 ? 'var(--green)' : 'var(--red)' }}>
                {status.cluster.healthy_nodes}/{status.cluster.total_nodes}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>Узлов онлайн</div>
            </div>
            <div style={{ textAlign: 'center', padding: '8px 16px', background: 'var(--bg3)', borderRadius: 8 }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--blue)' }}>
                {status.cluster.total_models}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>Моделей</div>
            </div>
            <div style={{ textAlign: 'center', padding: '8px 16px', background: 'var(--bg3)', borderRadius: 8 }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text2)' }}>
                {status.strategy}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>Стратегия</div>
            </div>
          </div>
        </div>
      )}

      {/* Pull Model (only if Ollama nodes available) */}
      {hasOllamaNodes && (
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
      )}

      {/* Inference Nodes */}
      {status && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">🖥️ Inference-узлы</div>
          <div style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 12 }}>
            Модель по умолчанию: {status.default_model}
          </div>
          {status.endpoints.map((ep, i) => (
            <div key={i} className="llm-endpoint">
              <div className={`ep-dot ${ep.healthy ? 'ok' : 'fail'}`} />
              <div style={{ flex: 1 }}>
                <div className="ep-name">
                  {ep.name}
                  <span style={{ fontSize: 11, marginLeft: 8, padding: '2px 6px', borderRadius: 4, background: 'var(--bg3)', color: 'var(--text3)' }}>
                    {ep.server_type}
                  </span>
                </div>
                <div className="ep-meta">
                  {ep.url}
                  {ep.models_count > 0 && <span> · {ep.models_count} моделей</span>}
                  {ep.active_requests > 0 && <span> · ⚡ {ep.active_requests} запросов</span>}
                  {ep.total_requests > 0 && <span> · 📊 {ep.total_requests} всего</span>}
                  {ep.error && <span style={{ color: 'var(--red)' }}> · ❌ {ep.error}</span>}
                </div>
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
                <div className="ep-meta">
                  VRAM: {m.vram_gb} ГБ · Размер: {m.size_gb} ГБ
                  {m.node && <span> · 🖥️ {m.node}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Installed Models */}
      <div className="card-title" style={{ marginBottom: 12, paddingLeft: 4 }}>📦 Доступные модели</div>
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
                  {m.size_gb > 0 && <span>💾 {m.size_gb} ГБ · </span>}
                  {m.node && <span>🖥️ {m.node}</span>}
                </div>
              </div>
              {hasOllamaNodes && (
                <button className="file-delete" onClick={() => deleteModel(m.name)}>Удалить</button>
              )}
            </div>
          </div>
        ))}
        {(!status?.models || status.models.length === 0) && (
          <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text3)' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
            <div>Нет доступных моделей</div>
            <div style={{ fontSize: 13, marginTop: 8 }}>
              {hasOllamaNodes
                ? <>Загрузите модель через форму выше, например: <strong>gemma3:4b</strong></>
                : <>Убедитесь что inference-узлы работают и имеют загруженные модели</>
              }
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
