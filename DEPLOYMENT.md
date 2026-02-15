# AI ServerClaw 部署说明

本文档详细说明了如何将 AI ServerClaw 项目部署到生产环境中。

## 部署前准备

### 服务器要求

- **操作系统**：Linux (推荐 Ubuntu 20.04+ 或 CentOS 7+)
- **CPU**：至少 2 核
- **内存**：至少 4GB
- **存储空间**：至少 20GB
- **网络**：可以访问互联网（用于拉取 Docker 镜像和 LLM API）

### 软件要求

- **Docker**：20.10.0 或更高版本
- **Docker Compose**：1.29.0 或更高版本

## 需要上传到服务器的文件

将以下文件和目录上传到服务器的同一个目录中（例如 `/opt/ai-serverclaw`）：

```
.
├── client/              # 前端代码目录
│   ├── Dockerfile        # 前端 Docker 构建文件
│   ├── nginx.conf        # Nginx 配置文件
│   ├── package.json      # 前端依赖配置
│   ├── package-lock.json # 前端依赖锁定文件
│   ├── vite.config.ts    # Vite 配置文件
│   └── src/              # 前端源代码
├── server/              # 后端代码目录
│   ├── Dockerfile        # 后端 Docker 构建文件
│   ├── requirements.txt  # 后端依赖配置
│   └── app/              # 后端源代码
├── docker-compose.yml    # Docker Compose 配置文件
└── DEPLOYMENT.md         # 部署说明文档
```

## Docker 环境搭建

### 在 Ubuntu 上安装 Docker 和 Docker Compose

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
apt install -y docker.io

# 启动 Docker 服务
systemctl start docker

# 设置 Docker 服务开机自启
systemctl enable docker

# 安装 Docker Compose
apt install -y docker-compose
```

### 在 CentOS 上安装 Docker 和 Docker Compose

```bash
# 更新系统
yum update -y

# 安装 Docker
yum install -y docker

# 启动 Docker 服务
systemctl start docker

# 设置 Docker 服务开机自启
systemctl enable docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

## 部署步骤

### 1. 上传文件到服务器

使用 SCP 或其他文件传输工具将上述文件和目录上传到服务器的指定目录。

### 2. 进入项目目录

```bash
cd /opt/ai-serverclaw
```

### 3. 修改环境变量（可选）

如果需要修改环境变量，编辑 `docker-compose.yml` 文件：

```yaml
backend:
  environment:
    - DATABASE_URL=sqlite+aiosqlite:///./ai_terminal.db
    - SECRET_KEY=your-secret-key-here  # 修改为更安全的值
    - ALGORITHM=HS256
    - ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4. 构建和启动服务

```bash
# 构建并启动服务
docker-compose up --build -d

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f
```

### 5. 验证服务

- **前端服务**：打开浏览器，访问 `http://服务器IP`
- **后端服务**：访问 `http://服务器IP:8000/api/auth/register`，应该返回 422 状态码（因为缺少必要的参数），这说明后端服务已经成功启动

## 服务管理

### 启动服务

```bash
docker-compose up -d
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart
```

### 查看服务状态

```bash
docker-compose ps
```

### 查看服务日志

```bash
# 查看所有服务的日志
docker-compose logs -f

# 查看特定服务的日志
docker-compose logs -f frontend
# 或
docker-compose logs -f backend
```

### 进入容器

```bash
# 进入前端容器
docker exec -it ai-server-frontend /bin/sh

# 进入后端容器
docker exec -it ai-server-backend /bin/bash
```

## 常见问题及解决方案

### 1. 服务启动失败

**症状**：`docker-compose ps` 显示服务状态为 `Exited`

**解决方案**：查看服务日志，找出失败原因

```bash
docker-compose logs -f
```

### 2. 前端无法访问后端 API

**症状**：前端页面加载正常，但无法与后端 API 通信

**解决方案**：检查 Nginx 配置文件 `client/nginx.conf`，确保代理配置正确

### 3. 数据库连接失败

**症状**：后端服务启动失败，日志显示数据库连接错误

**解决方案**：检查 `docker-compose.yml` 文件中的 `DATABASE_URL` 环境变量，确保它指向正确的数据库

### 4. 端口冲突

**症状**：服务启动失败，日志显示端口已被占用

**解决方案**：修改 `docker-compose.yml` 文件中的端口映射，使用未被占用的端口

## 注意事项

### 1. 安全性

- **生产环境**：修改 `docker-compose.yml` 文件中的 `SECRET_KEY`，使用一个更安全的值
- **HTTPS**：在生产环境中，建议配置 HTTPS，以确保数据传输的安全性
- **防火墙**：配置服务器防火墙，只开放必要的端口（如 80、443）

### 2. 数据库

- **SQLite**：默认使用 SQLite 数据库，适用于小规模部署
- **生产环境**：对于大规模部署，建议使用 PostgreSQL 或 MySQL 数据库

### 3. 性能

- **资源限制**：在生产环境中，建议为 Docker 容器设置资源限制，避免资源耗尽
- **缓存**：启用 Nginx 缓存，提高前端性能

### 4. 监控

- **日志**：定期查看服务日志，及时发现和解决问题
- **监控工具**：考虑使用 Prometheus、Grafana 等工具监控服务状态

## 升级部署

### 1. 停止服务

```bash
docker-compose down
```

### 2. 上传新文件

将更新后的文件上传到服务器的项目目录

### 3. 构建和启动服务

```bash
docker-compose up --build -d
```

### 4. 验证服务

确保服务正常运行，检查是否有任何错误

## 卸载部署

### 1. 停止服务

```bash
docker-compose down
```

### 2. 删除项目目录

```bash
rm -rf /opt/ai-serverclaw
```

### 3. 删除 Docker 镜像

```bash
# 查看所有镜像
docker images

# 删除特定镜像
docker rmi <镜像ID>
```

---

## 总结

本文档详细说明了如何将 AI ServerClaw 项目部署到生产环境中，包括部署前的准备工作、需要上传的文件、Docker 环境搭建、部署步骤、服务管理、常见问题及解决方案等内容。按照本文档的步骤操作，应该能够成功部署 AI ServerClaw 项目。

如果在部署过程中遇到任何问题，请参考常见问题及解决方案部分，或者查看服务日志，找出问题所在。