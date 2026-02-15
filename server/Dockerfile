# 使用 Python 3.11 基础镜像
FROM python:3.11-slim

WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 安装系统依赖（用于 asyncssh 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露 8000 端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]