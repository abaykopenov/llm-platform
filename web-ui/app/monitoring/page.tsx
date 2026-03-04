'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || ''

interface MachineData {
    hostname: string
    uptime: string
    cpu: {
        percent_avg: number
        cores: number
        freq_current: number
        percent_per_core: number[]
    }
    memory: {
        percent: number
        total_gb: number
        used_gb: number
        available_gb: number
    }
    gpu: {
        available: boolean
        name?: string
        temperature?: string
        utilization?: string
        power_draw?: string
        memory_used?: string
        memory_total?: string
    }
    disk: {
        percent: number
        total_gb: number
        used_gb: number
        free_gb: number
    }
    network: {
        bytes_sent_mb: number
        bytes_recv_mb: number
    }
    processes: Array<{
        pid: number
        name: string
        memory_percent: number
        cpu_percent: number
    }>
}

interface MachineEntry {
    data: MachineData | null
    error: string | null
    last_update: number
}

function getColor(pct: number): string {
    return pct < 60 ? 'green' : pct < 85 ? 'yellow' : 'red'
}

function getColorHex(pct: number): string {
    return pct < 60 ? 'var(--green)' : pct < 85 ? 'var(--yellow)' : 'var(--red)'
}

export default function MonitoringPage() {
    const [machines, setMachines] = useState<Record<string, MachineEntry>>({})
    const [activeMachine, setActiveMachine] = useState<string | null>(null)
    const [health, setHealth] = useState<any>(null)

    const fetchData = async () => {
        try {
            const [machResp, healthResp] = await Promise.all([
                fetch(`${API}/api/all`),
                fetch(`${API}/health`),
            ])
            const machData = await machResp.json()
            const healthData = await healthResp.json()

            setMachines(machData)
            setHealth(healthData)

            const names = Object.keys(machData)
            if (!activeMachine || !machData[activeMachine]) {
                setActiveMachine(names[0] || null)
            }
        } catch (e) { console.error(e) }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 5000)
        return () => clearInterval(interval)
    }, [])

    const names = Object.keys(machines)
    const activeEntry = activeMachine ? machines[activeMachine] : null
    const d = activeEntry?.data

    return (
        <div className="container">
            <div className="header"><h1>⚡ LLM Platform</h1></div>
            <div className="nav-tabs">
                <Link href="/" className="nav-tab">💬 Чат</Link>
                <Link href="/files" className="nav-tab">📁 Файлы</Link>
                <Link href="/models" className="nav-tab">🤖 Модели</Link>
                <span className="nav-tab active">📊 Мониторинг</span>
            </div>

            {/* Service Health */}
            {health && (
                <div className="card" style={{ marginBottom: 16 }}>
                    <div className="card-title">🏥 Здоровье сервисов</div>
                    <div className="stats-row">
                        {Object.entries(health.services || {}).map(([name, info]: [string, any]) => (
                            <div key={name} className="stat-item">
                                <div className="stat-value">
                                    <span className={`status-dot ${info.status === 'healthy' ? 'online' : 'offline'}`} />
                                    {name}
                                </div>
                                <div className="stat-label">{info.status}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Machine Overview Bar */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 20 }}>
                {names.map(name => {
                    const entry = machines[name]
                    const data = entry?.data
                    const isActive = name === activeMachine
                    const online = !entry?.error && data

                    return (
                        <div key={name}
                            className={`card ${isActive ? 'active' : ''}`}
                            style={{ cursor: 'pointer', padding: 14, ...(isActive ? { borderColor: 'var(--accent)' } : {}) }}
                            onClick={() => setActiveMachine(name)}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <span className={`status-dot ${online ? 'online' : 'offline'}`} />
                                <span style={{ fontWeight: 600, fontSize: 15 }}>{data?.hostname || name}</span>
                            </div>
                            {data && (
                                <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 12, color: 'var(--text3)' }}>
                                    <span>CPU {data.cpu.percent_avg}%</span>
                                    <span>RAM {data.memory.percent}%</span>
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>

            {/* Machine Detail */}
            {d ? (
                <>
                    <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                        <span className="chat-toggle" style={{ cursor: 'default' }}>🖥️ {d.hostname}</span>
                        <span className="chat-toggle" style={{ cursor: 'default' }}>⏱️ {d.uptime}</span>
                    </div>

                    <div className="grid">
                        {/* CPU */}
                        <div className="card">
                            <div className="card-title">🧠 Процессор</div>
                            <div className={`big-num ${getColor(d.cpu.percent_avg)}`}>
                                {d.cpu.percent_avg}<span className="big-num-unit">%</span>
                            </div>
                            <div className="progress-container">
                                <div className="progress-bar">
                                    <div className={`progress-fill ${getColor(d.cpu.percent_avg)}`} style={{ width: `${d.cpu.percent_avg}%` }} />
                                </div>
                            </div>
                            <div className="stats-row">
                                <div className="stat-item"><div className="stat-value">{d.cpu.cores}</div><div className="stat-label">ядер</div></div>
                                <div className="stat-item"><div className="stat-value">{d.cpu.freq_current}</div><div className="stat-label">МГц</div></div>
                            </div>
                        </div>

                        {/* Memory */}
                        <div className="card">
                            <div className="card-title">💾 Память</div>
                            <div className={`big-num ${getColor(d.memory.percent)}`}>
                                {d.memory.percent}<span className="big-num-unit">%</span>
                            </div>
                            <div className="progress-container">
                                <div className="progress-label"><span>RAM</span><span>{d.memory.used_gb} / {d.memory.total_gb} ГБ</span></div>
                                <div className="progress-bar"><div className="progress-fill blue" style={{ width: `${d.memory.percent}%` }} /></div>
                            </div>
                            <div className="stats-row">
                                <div className="stat-item"><div className="stat-value">{d.memory.total_gb}</div><div className="stat-label">Всего ГБ</div></div>
                                <div className="stat-item"><div className="stat-value">{d.memory.used_gb}</div><div className="stat-label">Занято ГБ</div></div>
                                <div className="stat-item"><div className="stat-value">{d.memory.available_gb}</div><div className="stat-label">Доступно ГБ</div></div>
                            </div>
                        </div>

                        {/* GPU */}
                        <div className="card">
                            <div className="card-title">🎮 GPU</div>
                            {d.gpu.available ? (
                                <>
                                    <div className="big-num blue">{d.gpu.temperature}<span className="big-num-unit">°C</span></div>
                                    <div className="big-num-label">{d.gpu.name}</div>
                                    <div className="progress-container">
                                        <div className="progress-label"><span>GPU Load</span><span>{d.gpu.utilization}%</span></div>
                                        <div className="progress-bar">
                                            <div className={`progress-fill ${getColor(parseInt(d.gpu.utilization || '0'))}`}
                                                style={{ width: `${parseInt(d.gpu.utilization || '0')}%` }} />
                                        </div>
                                    </div>
                                    <div className="stats-row">
                                        <div className="stat-item"><div className="stat-value">{d.gpu.power_draw}</div><div className="stat-label">Мощность W</div></div>
                                        <div className="stat-item"><div className="stat-value">{d.gpu.memory_used} MiB</div><div className="stat-label">VRAM</div></div>
                                    </div>
                                </>
                            ) : (
                                <div style={{ color: 'var(--text3)', padding: '20px 0' }}>GPU не обнаружен</div>
                            )}
                        </div>
                    </div>

                    <div className="grid">
                        {/* Disk */}
                        <div className="card">
                            <div className="card-title">💿 Диск</div>
                            <div className="progress-container">
                                <div className="progress-label"><span>Диск</span><span>{d.disk.used_gb} / {d.disk.total_gb} ГБ ({d.disk.percent}%)</span></div>
                                <div className="progress-bar"><div className={`progress-fill ${getColor(d.disk.percent)}`} style={{ width: `${d.disk.percent}%` }} /></div>
                            </div>
                        </div>

                        {/* Network */}
                        <div className="card">
                            <div className="card-title">🌐 Сеть</div>
                            <div className="stats-row">
                                <div className="stat-item"><div className="stat-value">{d.network.bytes_sent_mb}</div><div className="stat-label">Отправлено МБ</div></div>
                                <div className="stat-item"><div className="stat-value">{d.network.bytes_recv_mb}</div><div className="stat-label">Получено МБ</div></div>
                            </div>
                        </div>
                    </div>

                    {/* Processes */}
                    <div className="card">
                        <div className="card-title">📊 Топ процессов</div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                            <thead><tr>
                                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text3)', fontWeight: 500, fontSize: 11, letterSpacing: '0.5px', borderBottom: '1px solid var(--border)' }}>PID</th>
                                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text3)', fontWeight: 500, fontSize: 11, letterSpacing: '0.5px', borderBottom: '1px solid var(--border)' }}>Процесс</th>
                                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text3)', fontWeight: 500, fontSize: 11, letterSpacing: '0.5px', borderBottom: '1px solid var(--border)' }}>RAM %</th>
                                <th style={{ textAlign: 'left', padding: 8, color: 'var(--text3)', fontWeight: 500, fontSize: 11, letterSpacing: '0.5px', borderBottom: '1px solid var(--border)' }}>CPU %</th>
                            </tr></thead>
                            <tbody>
                                {d.processes.map((p, i) => (
                                    <tr key={i}>
                                        <td style={{ padding: 8, color: 'var(--text3)', borderBottom: '1px solid var(--border)' }}>{p.pid}</td>
                                        <td style={{ padding: 8, borderBottom: '1px solid var(--border)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</td>
                                        <td style={{ padding: 8, borderBottom: '1px solid var(--border)' }}>{p.memory_percent}%</td>
                                        <td style={{ padding: 8, borderBottom: '1px solid var(--border)' }}>{p.cpu_percent}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            ) : activeEntry?.error ? (
                <div className="card" style={{ textAlign: 'center', padding: 60 }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>🔌</div>
                    <div style={{ fontSize: 18, color: 'var(--red)', marginBottom: 8 }}>Нет связи с {activeMachine}</div>
                    <div style={{ fontSize: 13, color: 'var(--text3)' }}>{activeEntry.error}</div>
                </div>
            ) : (
                <div className="card" style={{ textAlign: 'center', padding: 60 }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
                    <div style={{ color: 'var(--text3)' }}>Ожидание данных мониторинга...</div>
                </div>
            )}
        </div>
    )
}
