'use client'

import { useState, useRef, useEffect, FormEvent } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || ''
const STORAGE_KEY = 'llm-platform-chat'

// Embedding-only models to hide from chat selector
const EMBEDDING_MODELS = ['nomic-embed-text', 'mxbai-embed-large', 'all-minilm', 'bge-m3', 'snowflake-arctic-embed']

interface Message {
    role: 'user' | 'assistant' | 'system'
    content: string
}

const DEFAULT_MSG: Message = {
    role: 'assistant',
    content: 'Привет! Я готов к работе. Задайте вопрос — если включён RAG, я буду использовать загруженные документы как контекст.'
}

function loadHistory(): Message[] {
    if (typeof window === 'undefined') return [DEFAULT_MSG]
    try {
        const saved = localStorage.getItem(STORAGE_KEY)
        if (saved) {
            const parsed = JSON.parse(saved)
            if (Array.isArray(parsed) && parsed.length > 0) return parsed
        }
    } catch { }
    return [DEFAULT_MSG]
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>(loadHistory)
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [ragEnabled, setRagEnabled] = useState(false)
    const [collection, setCollection] = useState('general')
    const [collections, setCollections] = useState<string[]>(['general'])
    const [llmOnline, setLlmOnline] = useState<boolean | null>(null)
    const [models, setModels] = useState<string[]>([])
    const [selectedModel, setSelectedModel] = useState('')
    const messagesEnd = useRef<HTMLDivElement>(null)

    // Save messages to localStorage
    useEffect(() => {
        if (messages.length > 0) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
        }
    }, [messages])

    useEffect(() => {
        // Fetch collections
        fetch(`${API}/api/collections`).then(r => r.json()).then(c => {
            if (Array.isArray(c) && c.length) {
                setCollections(c)
                if (!c.includes(collection)) setCollection(c[0])
            }
        }).catch(() => { })

        // Check LLM status + get models (filter out embedding models)
        fetch(`${API}/api/llm/status`).then(r => r.json()).then(s => {
            setLlmOnline(s.endpoints?.some((e: any) => e.healthy) ?? false)
            const allModels = (s.models || []).map((m: any) => m.name)
            const chatModels = allModels.filter((name: string) =>
                !EMBEDDING_MODELS.some(emb => name.toLowerCase().startsWith(emb))
            )
            setModels(chatModels)
            if (chatModels.length > 0 && !selectedModel) setSelectedModel(chatModels[0])
        }).catch(() => setLlmOnline(false))
    }, [])

    useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

    const clearHistory = () => {
        if (confirm('Очистить историю чата?')) {
            setMessages([DEFAULT_MSG])
            localStorage.removeItem(STORAGE_KEY)
        }
    }

    const sendMessage = async (e?: FormEvent) => {
        e?.preventDefault()
        const text = input.trim()
        if (!text || isLoading) return

        const userMsg: Message = { role: 'user', content: text }
        const newHistory = [...messages, userMsg]
        setMessages(newHistory)
        setInput('')
        setIsLoading(true)

        try {
            const resp = await fetch(`${API}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: newHistory.filter(m => m.role !== 'system' || newHistory.indexOf(m) === 0),
                    collection: ragEnabled ? collection : '',
                    model: selectedModel || undefined,
                    stream: true,
                }),
            })

            const reader = resp.body?.getReader()
            const decoder = new TextDecoder()
            let fullText = ''

            setMessages(prev => [...prev, { role: 'assistant', content: '' }])

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read()
                    if (done) break
                    const chunk = decoder.decode(value, { stream: true })
                    for (const line of chunk.split('\n')) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6)
                            if (data === '[DONE]') continue
                            try {
                                const parsed = JSON.parse(data)
                                // Handle source citations from RAG
                                if (parsed.sources) {
                                    const srcText = '\n\n📎 **Источники:** ' +
                                        parsed.sources.map((s: any) => `[${s.index}] ${s.source}`).join(', ')
                                    fullText += srcText
                                    setMessages(prev => {
                                        const updated = [...prev]
                                        updated[updated.length - 1] = { role: 'assistant', content: fullText }
                                        return updated
                                    })
                                    continue
                                }
                                const delta = parsed.choices?.[0]?.delta?.content
                                if (delta) {
                                    fullText += delta
                                    setMessages(prev => {
                                        const updated = [...prev]
                                        updated[updated.length - 1] = { role: 'assistant', content: fullText }
                                        return updated
                                    })
                                }
                            } catch { }
                        }
                    }
                }
            }
        } catch (e: any) {
            setMessages(prev => [...prev, { role: 'assistant', content: '❌ Ошибка: ' + e.message }])
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="container">
            <div className="header"><h1>⚡ LLM Platform</h1></div>
            <div className="nav-tabs">
                <span className="nav-tab active">💬 Чат</span>
                <Link href="/files" className="nav-tab">📁 Файлы</Link>
                <Link href="/models" className="nav-tab">🤖 Модели</Link>
                <Link href="/monitoring" className="nav-tab">📊 Мониторинг</Link>
            </div>

            <div className="chat-controls">
                <select className="chat-select" value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
                    {models.length === 0 && <option value="">Нет моделей</option>}
                    {models.map(m => <option key={m} value={m}>🤖 {m}</option>)}
                </select>
                <select className="chat-select" value={collection} onChange={e => setCollection(e.target.value)}
                    style={{ opacity: ragEnabled ? 1 : 0.5 }}
                >
                    {collections.map(c => <option key={c} value={c}>📚 {c}</option>)}
                </select>
                <button className={`chat-toggle ${ragEnabled ? 'active' : ''}`} onClick={() => setRagEnabled(!ragEnabled)}>
                    🔍 RAG {ragEnabled ? 'ON' : 'OFF'}
                </button>
                <button className="chat-toggle" onClick={clearHistory} title="Очистить историю">
                    🗑️
                </button>
                <span style={{ fontSize: 12, color: llmOnline === null ? 'var(--text3)' : llmOnline ? 'var(--green2)' : 'var(--red)' }}>
                    {llmOnline === null ? '⏳ Проверка...' : llmOnline ? '🟢 Online' : '🔴 Offline'}
                </span>
            </div>

            <div className="chat-container">
                <div className="chat-messages">
                    {messages.map((m, i) => (
                        <div key={i} className={`chat-msg ${m.role}`}>
                            <div className="avatar">{m.role === 'user' ? '👤' : '🤖'}</div>
                            <div className="bubble">{m.content || '●●●'}</div>
                        </div>
                    ))}
                    <div ref={messagesEnd} />
                </div>
                <form className="chat-input-bar" onSubmit={sendMessage}>
                    <textarea
                        className="chat-input"
                        placeholder="Введите сообщение..."
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
                        rows={1}
                    />
                    <button type="submit" className="chat-send" disabled={isLoading}>
                        {isLoading ? '⏳' : 'Отправить →'}
                    </button>
                </form>
            </div>
        </div>
    )
}
