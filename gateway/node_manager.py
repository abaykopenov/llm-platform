"""
Node Manager — Dynamic inference node management.
Manages multiple inference endpoints (Ollama, vLLM, etc.)
with auto-detection, health monitoring, and load balancing.

Usage in .env:
    INFERENCE_NODES=http://192.168.8.7:11434,http://192.168.8.8:11434
    # or single node (backward compatible):
    INFERENCE_URL=http://192.168.8.7:11434
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx


@dataclass
class InferenceNode:
    """Single inference endpoint."""
    url: str
    name: str = ""
    server_type: str = "unknown"  # "ollama", "openai", "unknown"
    healthy: bool = False
    models: list = field(default_factory=list)
    loaded_models: list = field(default_factory=list)
    gpu_info: dict = field(default_factory=dict)
    last_check: float = 0.0
    active_requests: int = 0
    total_requests: int = 0
    avg_latency_ms: float = 0.0
    error: str = ""

    @property
    def label(self) -> str:
        return self.name or self.url


class NodeManager:
    """
    Manages a pool of inference nodes.
    - Auto-detects server type (Ollama vs OpenAI-compatible)
    - Periodic health checks
    - Load balancing (least-connections)
    - Model aggregation across all nodes
    """

    def __init__(self):
        self.nodes: List[InferenceNode] = []
        self._check_interval = 15  # seconds
        self._check_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    def configure(self, urls: List[str], client: httpx.AsyncClient):
        """Initialize nodes from URL list."""
        self._client = client
        self.nodes = []
        for i, url in enumerate(urls):
            url = url.strip().rstrip("/")
            if not url:
                continue
            node = InferenceNode(
                url=url,
                name=f"node-{i+1}",
            )
            self.nodes.append(node)
        print(f"🔧 NodeManager: configured {len(self.nodes)} node(s)")
        for n in self.nodes:
            print(f"   → {n.name}: {n.url}")

    async def start(self):
        """Start periodic health checks."""
        if not self.nodes:
            return
        # Initial check
        await self.check_all_nodes()
        # Start background task
        self._check_task = asyncio.create_task(self._periodic_check())

    async def stop(self):
        """Stop health checks."""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

    async def _periodic_check(self):
        """Background health check loop."""
        while True:
            await asyncio.sleep(self._check_interval)
            try:
                await self.check_all_nodes()
            except Exception as e:
                print(f"NodeManager health check error: {e}")

    async def check_all_nodes(self):
        """Check all nodes in parallel."""
        if not self._client:
            return
        tasks = [self._check_node(node) for node in self.nodes]
        await asyncio.gather(*tasks, return_exceptions=True)

        healthy_count = sum(1 for n in self.nodes if n.healthy)
        total_models = sum(len(n.models) for n in self.nodes)
        print(
            f"🏥 NodeManager: {healthy_count}/{len(self.nodes)} healthy, "
            f"{total_models} models total"
        )

    async def _check_node(self, node: InferenceNode):
        """Check single node: detect type, health, models, GPU."""
        node.last_check = time.time()

        # ── Detect server type & health ─────────────────────
        node.server_type = "unknown"
        node.healthy = False
        node.error = ""

        # Try Ollama
        try:
            resp = await self._client.get(
                f"{node.url}/api/tags", timeout=5.0
            )
            if resp.status_code == 200:
                node.server_type = "ollama"
                node.healthy = True
                data = resp.json()
                node.models = [
                    {
                        "name": m.get("name", ""),
                        "size_gb": round(m.get("size", 0) / (1024**3), 1),
                        "family": m.get("details", {}).get("family", ""),
                        "parameters": m.get("details", {}).get("parameter_size", ""),
                        "quantization": m.get("details", {}).get("quantization_level", ""),
                        "node": node.name,
                        "node_url": node.url,
                    }
                    for m in data.get("models", [])
                ]
        except Exception:
            pass

        # Try OpenAI-compatible
        if node.server_type == "unknown":
            try:
                resp = await self._client.get(
                    f"{node.url}/v1/models", timeout=5.0
                )
                if resp.status_code == 200:
                    node.server_type = "openai"
                    node.healthy = True
                    data = resp.json()
                    node.models = [
                        {
                            "name": m.get("id", ""),
                            "size_gb": 0,
                            "family": m.get("owned_by", ""),
                            "parameters": "",
                            "quantization": "",
                            "node": node.name,
                            "node_url": node.url,
                        }
                        for m in data.get("data", [])
                    ]
            except Exception as e:
                node.error = str(e)

        if not node.healthy:
            node.models = []
            node.loaded_models = []
            return

        # ── Loaded models (Ollama only) ────────────────────
        if node.server_type == "ollama":
            try:
                resp = await self._client.get(
                    f"{node.url}/api/ps", timeout=5.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    node.loaded_models = [
                        {
                            "name": m.get("name", ""),
                            "size_gb": round(m.get("size", 0) / (1024**3), 1),
                            "vram_gb": round(m.get("size_vram", 0) / (1024**3), 1),
                            "node": node.name,
                        }
                        for m in data.get("models", [])
                    ]
            except Exception:
                node.loaded_models = []

    # ─── Load Balancing ──────────────────────────────────────

    def get_best_node(self, model: str = None) -> Optional[InferenceNode]:
        """
        Pick the best node for a request (least-connections).
        If model is specified, prefer nodes that have it loaded.
        """
        healthy_nodes = [n for n in self.nodes if n.healthy]
        if not healthy_nodes:
            return None

        # If model specified, prefer nodes with that model loaded
        if model:
            # First: nodes with model loaded in GPU
            loaded_nodes = [
                n for n in healthy_nodes
                if any(m.get("name", "").startswith(model.split(":")[0])
                       for m in n.loaded_models)
            ]
            if loaded_nodes:
                healthy_nodes = loaded_nodes
            else:
                # Second: nodes that have the model installed
                model_nodes = [
                    n for n in healthy_nodes
                    if any(m.get("name", "") == model for m in n.models)
                ]
                if model_nodes:
                    healthy_nodes = model_nodes

        # Least connections
        return min(healthy_nodes, key=lambda n: n.active_requests)

    def get_node_url(self, model: str = None) -> str:
        """Get the best node URL for a request. Backward compatible."""
        node = self.get_best_node(model)
        if node:
            return node.url
        # Fallback to first node even if unhealthy
        if self.nodes:
            return self.nodes[0].url
        return "http://localhost:11434"

    def track_request_start(self, node_url: str):
        """Track that a request started on a node."""
        for n in self.nodes:
            if n.url == node_url:
                n.active_requests += 1
                n.total_requests += 1
                break

    def track_request_end(self, node_url: str):
        """Track that a request ended on a node."""
        for n in self.nodes:
            if n.url == node_url:
                n.active_requests = max(0, n.active_requests - 1)
                break

    # ─── Aggregated Data ──────────────────────────────────────

    def get_all_models(self) -> list:
        """Get models from all healthy nodes."""
        all_models = []
        for node in self.nodes:
            if node.healthy:
                all_models.extend(node.models)
        return all_models

    def get_all_loaded(self) -> list:
        """Get loaded models from all nodes."""
        all_loaded = []
        for node in self.nodes:
            if node.healthy:
                all_loaded.extend(node.loaded_models)
        return all_loaded

    def get_status(self) -> dict:
        """Full cluster status."""
        return {
            "total_nodes": len(self.nodes),
            "healthy_nodes": sum(1 for n in self.nodes if n.healthy),
            "total_models": len(self.get_all_models()),
            "nodes": [
                {
                    "name": n.name,
                    "url": n.url,
                    "server_type": n.server_type,
                    "healthy": n.healthy,
                    "error": n.error,
                    "models_count": len(n.models),
                    "loaded_count": len(n.loaded_models),
                    "active_requests": n.active_requests,
                    "total_requests": n.total_requests,
                    "last_check": n.last_check,
                }
                for n in self.nodes
            ],
        }


# Singleton instance
node_manager = NodeManager()
