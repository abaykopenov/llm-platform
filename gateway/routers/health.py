"""
Health Router — GET /health, GET /status
Health checks and cluster status.
"""

import os
import platform
import shutil
import subprocess
import time

import httpx
from fastapi import APIRouter, Request

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(request: Request):
    """Health check for all downstream services."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url
    rag_engine_url = request.app.state.rag_engine_url
    chromadb_url = request.app.state.chromadb_url

    services = {}

    # Check inference (Ollama)
    try:
        resp = await client.get(f"{inference_url}/api/tags", timeout=5.0)
        services["inference"] = {"status": "healthy" if resp.status_code == 200 else "unhealthy"}
    except Exception as e:
        services["inference"] = {"status": "unhealthy", "error": str(e)}

    # Check RAG engine
    try:
        resp = await client.get(f"{rag_engine_url}/health", timeout=5.0)
        services["rag_engine"] = {"status": "healthy" if resp.status_code == 200 else "unhealthy"}
    except Exception as e:
        services["rag_engine"] = {"status": "unhealthy", "error": str(e)}

    # Check ChromaDB — any response means it's alive
    chromadb_healthy = False
    for path in ["/api/v2/heartbeat", "/api/v1/heartbeat", "/"]:
        try:
            resp = await client.get(f"{chromadb_url}{path}", timeout=5.0)
            # Any response (200, 404, 410) means ChromaDB is running
            chromadb_healthy = True
            break
        except Exception:
            continue
    services["chromadb"] = {"status": "healthy" if chromadb_healthy else "unhealthy"}

    all_healthy = all(s["status"] == "healthy" for s in services.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": time.time(),
        "services": services,
    }


@router.get("/status")
async def cluster_status(request: Request):
    """Cluster status — GPU, RAM, queue info."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url
    rag_engine_url = request.app.state.rag_engine_url

    status = {
        "timestamp": time.time(),
        "inference": {},
        "rag_engine": {},
        "models": [],
    }

    # Get inference info
    try:
        resp = await client.get(f"{inference_url}/v1/models", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            status["models"] = [m.get("id", "") for m in data.get("data", [])]
    except Exception:
        pass

    # Get RAG engine stats
    try:
        resp = await client.get(f"{rag_engine_url}/stats", timeout=5.0)
        if resp.status_code == 200:
            status["rag_engine"] = resp.json()
    except Exception:
        pass

    return status


def _get_system_stats() -> dict:
    """Collect real system stats via psutil."""
    try:
        import psutil
    except ImportError:
        return None

    cpu_pct = psutil.cpu_percent(interval=0.5, percpu=True)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    net = psutil.net_io_counters()

    boot = psutil.boot_time()
    uptime_sec = time.time() - boot
    hours = int(uptime_sec // 3600)
    mins = int((uptime_sec % 3600) // 60)

    procs = []
    for p in sorted(psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]),
                     key=lambda x: x.info.get("memory_percent", 0) or 0, reverse=True)[:10]:
        info = p.info
        procs.append({
            "pid": info.get("pid", 0),
            "name": info.get("name", ""),
            "memory_percent": round(info.get("memory_percent", 0) or 0, 1),
            "cpu_percent": round(info.get("cpu_percent", 0) or 0, 1),
        })

    gpu_info = {"available": False}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = [x.strip() for x in result.stdout.strip().split(",")]
            if len(parts) >= 6:
                gpu_info = {
                    "available": True,
                    "name": parts[0],
                    "temperature": parts[1],
                    "utilization": parts[2],
                    "power_draw": parts[3],
                    "memory_used": parts[4],
                    "memory_total": parts[5],
                }
    except Exception:
        pass

    return {
        "hostname": platform.node(),
        "uptime": f"{hours}ч {mins}м",
        "cpu": {
            "percent_avg": round(sum(cpu_pct) / len(cpu_pct), 1) if cpu_pct else 0,
            "cores": psutil.cpu_count(),
            "freq_current": round(cpu_freq.current) if cpu_freq else 0,
            "percent_per_core": [round(c, 1) for c in cpu_pct],
        },
        "memory": {
            "percent": round(mem.percent, 1),
            "total_gb": round(mem.total / (1024 ** 3), 1),
            "used_gb": round(mem.used / (1024 ** 3), 1),
            "available_gb": round(mem.available / (1024 ** 3), 1),
        },
        "gpu": gpu_info,
        "disk": {
            "percent": round(disk.used / disk.total * 100, 1),
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
        },
        "network": {
            "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 1),
            "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 1),
        },
        "processes": procs,
    }


@router.get("/api/all")
async def api_all_machines(request: Request):
    """System monitoring — real stats from this machine."""
    data = _get_system_stats()
    hostname = platform.node() or "gateway"

    if data:
        return {
            hostname: {
                "data": data,
                "error": None,
                "last_update": time.time(),
            }
        }
    else:
        return {
            hostname: {
                "data": None,
                "error": "psutil not installed — pip install psutil",
                "last_update": time.time(),
            }
        }

