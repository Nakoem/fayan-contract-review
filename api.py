"""
法眼 · 合同审查 API 服务

启动: uvicorn api:app --host 0.0.0.0 --port 8000
文档: http://localhost:8000/docs
"""

import os
import uuid
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from logger import init_logger, attach_web_buffer, detach_web_buffer

load_dotenv()

init_logger(mode="web")

app = FastAPI(
    title="法眼 · 合同审查 API",
    description="AI驱动的合同审查服务，支持6种合同类型、10工具ReAct Agent、四重知识库交叉验证",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 合同类型 ──
CONTRACT_TYPES = [
    "房屋租赁合同", "劳动合同", "买卖合同",
    "服务合同", "合作协议", "借款合同",
]

# ── 异步任务存储（内存） ──
_async_tasks: dict[str, dict] = {}


# ══════════════════════════════════════════════════════
# 请求 / 响应模型
# ══════════════════════════════════════════════════════

class ReviewRequest(BaseModel):
    contract_text: str = Field(..., description="合同全文", min_length=10)
    contract_type: str = Field(..., description="合同类型，如'房屋租赁合同'")


class ReviewResponse(BaseModel):
    contract_type: str
    report: str
    elapsed_seconds: float


class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str  # "pending" | "running" | "completed" | "failed"
    contract_type: str | None = None
    report: str | None = None
    elapsed_seconds: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str
    contract_types: list[str]


# ══════════════════════════════════════════════════════
# API 路由
# ══════════════════════════════════════════════════════

@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    """健康检查。"""
    return HealthResponse(
        status="ok",
        model=os.getenv("LLM_MODEL", "qwen-plus"),
        version="1.0.0",
        contract_types=CONTRACT_TYPES,
    )


@app.get("/api/v1/contract-types")
def contract_types():
    """返回支持的合同类型列表。"""
    return {"contract_types": CONTRACT_TYPES}


@app.post("/api/v1/review", response_model=ReviewResponse)
def review(request: ReviewRequest):
    """同步审查合同，等待完成后返回报告。"""
    if request.contract_type not in CONTRACT_TYPES and request.contract_type != "自定义":
        raise HTTPException(
            400, f"不支持的合同类型: {request.contract_type}。支持: {', '.join(CONTRACT_TYPES)}"
        )

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(500, "服务端未配置 DASHSCOPE_API_KEY")

    from main import review_contract
    import time

    t0 = time.perf_counter()
    try:
        report = review_contract(request.contract_text, request.contract_type, api_key)
    except Exception as e:
        raise HTTPException(500, f"审查失败: {e}")

    elapsed = time.perf_counter() - t0
    return ReviewResponse(
        contract_type=request.contract_type,
        report=report,
        elapsed_seconds=round(elapsed, 1),
    )


@app.post("/api/v1/review/async", response_model=AsyncTaskResponse)
def review_async(request: ReviewRequest):
    """异步审查合同，返回task_id，通过 GET /review/{task_id} 轮询结果。"""
    if request.contract_type not in CONTRACT_TYPES and request.contract_type != "自定义":
        raise HTTPException(
            400, f"不支持的合同类型: {request.contract_type}"
        )

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(500, "服务端未配置 DASHSCOPE_API_KEY")

    task_id = str(uuid.uuid4())[:8]
    _async_tasks[task_id] = {
        "status": "pending",
        "contract_type": request.contract_type,
        "report": None,
        "elapsed_seconds": None,
        "error": None,
    }

    def _run():
        import time
        from main import review_contract

        _async_tasks[task_id]["status"] = "running"
        t0 = time.perf_counter()
        try:
            report = review_contract(request.contract_text, request.contract_type, api_key)
            _async_tasks[task_id]["report"] = report
            _async_tasks[task_id]["elapsed_seconds"] = round(time.perf_counter() - t0, 1)
            _async_tasks[task_id]["status"] = "completed"
        except Exception as e:
            _async_tasks[task_id]["error"] = str(e)
            _async_tasks[task_id]["status"] = "failed"

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return AsyncTaskResponse(
        task_id=task_id,
        status="pending",
        contract_type=request.contract_type,
    )


@app.get("/api/v1/review/{task_id}", response_model=AsyncTaskResponse)
def get_review_result(task_id: str):
    """查询异步审查结果。"""
    task = _async_tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return AsyncTaskResponse(
        task_id=task_id,
        status=task["status"],
        contract_type=task.get("contract_type"),
        report=task.get("report"),
        elapsed_seconds=task.get("elapsed_seconds"),
        error=task.get("error"),
    )


# ══════════════════════════════════════════════════════
# 启动入口
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
