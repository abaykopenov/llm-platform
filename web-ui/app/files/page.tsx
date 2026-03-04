'use client'

import { useState, useEffect, useRef, ChangeEvent } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || ''

interface FileInfo {
    file_id: string
    original_name: string
    chunks_count: number
    collection: string
    ingested_at: string
}

const FILE_ICONS: Record<string, string> = {
    pdf: '📕', docx: '📘', doc: '📘', txt: '📄', md: '📝',
    csv: '📊', pptx: '📙', xlsx: '📗', html: '🌐',
}

export default function FilesPage() {
    const [files, setFiles] = useState<FileInfo[]>([])
    const [collections, setCollections] = useState<string[]>(['general'])
    const [activeCollection, setActiveCollection] = useState('general')
    const [dragOver, setDragOver] = useState(false)
    const [uploading, setUploading] = useState<string | null>(null)
    const [uploadError, setUploadError] = useState<string | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    const fetchFiles = async () => {
        try {
            const [fResp, cResp] = await Promise.all([
                fetch(`${API}/api/files`),
                fetch(`${API}/api/collections`),
            ])
            const f = await fResp.json()
            const c = await cResp.json()
            if (Array.isArray(f)) setFiles(f)
            if (Array.isArray(c) && c.length) setCollections(c)
        } catch { }
    }

    useEffect(() => { fetchFiles() }, [])

    const handleFiles = async (fileList: FileList) => {
        setUploadError(null)
        for (const file of Array.from(fileList)) {
            setUploading(`Загрузка: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} МБ)...`)
            const fd = new FormData()
            fd.append('file', file)
            fd.append('collection', activeCollection)
            try {
                const resp = await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
                if (!resp.ok) {
                    const err = await resp.text()
                    setUploadError(`❌ Ошибка при загрузке ${file.name}: ${err}`)
                } else {
                    setUploading(`✅ ${file.name} — загружен!`)
                }
            } catch (e: any) {
                setUploadError(`❌ Ошибка: ${e.message}`)
            }
        }
        setUploading(null)
        fetchFiles()
    }

    const deleteFile = async (id: string) => {
        if (!confirm('Удалить файл и его векторы?')) return
        await fetch(`${API}/api/files/${id}`, { method: 'DELETE' })
        fetchFiles()
    }

    const createCollection = async () => {
        const name = prompt('Имя новой коллекции:')
        if (!name) return
        await fetch(`${API}/api/collections`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        })
        fetchFiles()
    }

    const getIcon = (name: string) => {
        const ext = name.split('.').pop()?.toLowerCase() || ''
        return FILE_ICONS[ext] || '📎'
    }

    return (
        <div className="container">
            <div className="header"><h1>⚡ LLM Platform</h1></div>
            <div className="nav-tabs">
                <Link href="/" className="nav-tab">💬 Чат</Link>
                <span className="nav-tab active">📁 Файлы</span>
                <Link href="/models" className="nav-tab">🤖 Модели</Link>
                <Link href="/monitoring" className="nav-tab">📊 Мониторинг</Link>
            </div>

            <div className="chat-controls">
                <select className="chat-select" value={activeCollection} onChange={e => setActiveCollection(e.target.value)}>
                    {collections.map(c => <option key={c} value={c}>📚 {c}</option>)}
                </select>
                <button className="chat-toggle" onClick={createCollection}>+ Новая коллекция</button>
            </div>

            <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
                onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onClick={() => inputRef.current?.click()}
            >
                <div className="icon">{uploading ? '⏳' : '📄'}</div>
                <div className="label">{uploading || 'Перетащите файлы сюда или нажмите для выбора'}</div>
                <div className="sub">PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, HTML</div>
                <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.html"
                    style={{ display: 'none' }} onChange={(e: ChangeEvent<HTMLInputElement>) => e.target.files && handleFiles(e.target.files)} />
            </div>

            {uploadError && (
                <div style={{ padding: '10px 14px', background: 'rgba(255,50,50,0.1)', border: '1px solid var(--red)', borderRadius: 8, margin: '12px 0', fontSize: 13, color: 'var(--red)' }}>
                    {uploadError}
                </div>
            )}

            <div className="file-list">
                {files.map(f => (
                    <div key={f.file_id} className="file-item">
                        <div className="file-icon">{getIcon(f.original_name)}</div>
                        <div className="file-info">
                            <div className="file-name">{f.original_name}</div>
                            <div className="file-meta">{f.chunks_count} чанков · {f.collection} · {f.ingested_at}</div>
                        </div>
                        <span className="file-badge ok">✓ Векторизирован</span>
                        <button className="file-delete" onClick={() => deleteFile(f.file_id)}>Удалить</button>
                    </div>
                ))}
                {files.length === 0 && (
                    <div style={{ textAlign: 'center', padding: 40, color: 'var(--text3)' }}>
                        Нет загруженных файлов
                    </div>
                )}
            </div>
        </div>
    )
}
