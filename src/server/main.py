# -*- coding: utf-8 -*-
# FastAPI 问答服务：启动时从 config.KB_DIR 加载建库产物组装 pipeline，
# 提供 POST /ask（问答，强制来源引用）与 GET /health（服务与索引加载状态）
# 启动方式：python -m src.server.main（或 uvicorn src.server.main:app --reload）
# 问答依赖（pipeline kwargs）持有于 app.state，经 Depends 注入路由；
# 测试可经 create_app(pipeline) 工厂参数整体替换为 stub，不依赖真实 API 与索引
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field

from src.config import KB_DIR
from src.generation.answer import answer, build_pipeline


class SourceItem(BaseModel):
    # 来源条目：doc 手册名 / page 页码（取自 chunk metadata）/ model 型号
    doc: str
    page: int
    model: str


class AskRequest(BaseModel):
    # 问答请求：question 必填且非空（空字符串 / 缺字段由 pydantic 校验为 422）
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class HealthResponse(BaseModel):
    status: str
    chunks: int


def get_pipeline(request: Request) -> dict:
    # 依赖注入入口：从 app.state 取 answer() 的关键字参数包
    return request.app.state.pipeline


def create_app(pipeline: dict | None = None) -> FastAPI:
    # 应用工厂：pipeline 为 answer() 的关键字参数包（build_pipeline 产物）；
    # 传入时直接使用（测试注入 stub），未传入则在启动时从 KB_DIR 加载真实索引

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时加载索引与词表，服务运行期间复用，不逐请求重建
        if pipeline is None:
            app.state.pipeline = build_pipeline(KB_DIR)
        yield

    app = FastAPI(title="注塑机售后知识库智能问答", lifespan=lifespan)
    if pipeline is not None:
        app.state.pipeline = pipeline

    @app.get("/health", response_model=HealthResponse)
    def health(pipe: dict = Depends(get_pipeline)):
        # 健康检查：返回服务状态与已加载 chunk 数
        return {"status": "ok", "chunks": len(pipe["kb"].chunks)}

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest, pipe: dict = Depends(get_pipeline)):
        # 问答接口：调用 answer() 编排（识别 -> 检索 -> 生成），
        # 返回 {"answer", "sources"}，sources 页码取自 metadata
        return answer(req.question, **pipe)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.server.main:app", host="0.0.0.0", port=8000, reload=True)
