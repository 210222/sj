FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY src/ ./src/
COPY tests/ ./tests/
COPY config/ ./config/
COPY contracts/ ./contracts/
COPY scripts/ ./scripts/

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python scripts/smoke_outer.py || exit 1

# 默认启动：运行冒烟 + 外圈测试
CMD ["python", "scripts/regression_gate.py"]
