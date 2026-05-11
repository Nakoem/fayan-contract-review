# 法眼 · 合同审查 API
# 多阶段构建
FROM python:3.11-slim

WORKDIR /app

# 依赖层（缓存友好）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用层
COPY . .

# 日志和评估输出目录
RUN mkdir -p logs eval_results

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
