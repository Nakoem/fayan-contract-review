# 法眼 · 合同审查 Agent
# 构建: docker build -t fayan .
# 运行: docker run -p 8501:8501 --env-file .env fayan

FROM python:3.11-slim

WORKDIR /app

# 系统依赖（Chromiunm/Playwright 可选）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 项目文件
COPY . .

# Streamlit 端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
