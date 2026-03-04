# Railway 部署配置指南

## 环境变量设置

在 Railway 项目设置中添加以下环境变量：

### 必需的环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API Key | `xxx...` |
| `MEM0_QDRANT_HOST` | Qdrant 主机地址 | 使用 Railway Qdrant 插件或外部服务 |
| `MEM0_QDRANT_PORT` | Qdrant 端口 | `6333` |
| `MEM0_NEO4J_URI` | Neo4j 连接地址 | 使用 Railway Neo4j 插件或外部服务 |
| `MEM0_NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `MEM0_NEO4J_PASSWORD` | Neo4j 密码 | `password123` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `GEMINI_MODEL` | Gemini 模型名称 | `models/gemini-2.0-flash` |
| `PORT` | 服务端口 | 由 Railway 自动设置 |

## Railway 插件配置

### 推荐插件

1. **Qdrant** - 向量数据库
   - 在 Railway 中添加 Qdrant 插件
   - 插件会自动提供 `QDRANT_URL` 环境变量
   - 需要在代码中映射到 `MEM0_QDRANT_HOST`

2. **Neo4j** - 图数据库（或使用 Neo4j Aura 免费版）
   - Railway 的 Neo4j 插件或使用 Neo4j Aura
   - Aura 免费版提供 200k 节点，适合测试

## 部署步骤

### 1. 准备 GitHub 仓库

```bash
git init
git add .
git commit -m "Initial commit for Railway deployment"
git push origin main
```

### 2. 在 Railway 创建项目

1. 访问 https://railway.app/
2. 点击 "New Project" → "Deploy from GitHub repo"
3. 选择你的仓库
4. Railway 会自动检测 Python 项目并开始部署

### 3. 配置环境变量

在 Railway 项目设置中添加上述环境变量

### 4. 添加数据库插件

- 添加 Qdrant 插件（或使用外部 Qdrant）
- 添加 Neo4j 插件（或使用 Neo4j Aura）

### 5. 部署完成

Railway 会自动：
- 安装 requirements.txt 中的依赖
- 从 GitHub 安装 fork 的 mem0
- 启动 FastAPI 服务
- 提供公网 URL

## 访问服务

部署完成后，Railway 会提供一个类似 `https://your-app.railway.app` 的 URL。

### 测试端点

```bash
# 健康检查
curl https://your-app.railway.app/health

# 获取 OpenAI Functions Schema
curl https://your-app.railway.app/api/v1/functions/schema

# 添加记忆
curl -X POST https://your-app.railway.app/api/v1/memory/add \
  -H "Content-Type: application/json" \
  -d '{"uid": "test_user", "text": "Hello Railway!"}'
```

## 本地开发 vs 生产部署

|  | 本地开发 | Railway 生产 |
|---|---|---|
| mem0 安装 | `pip install -e /path/to/mem0-code` | 从 GitHub 自动安装 |
| Qdrant/Neo4j | 本地 docker | Railway 插件或外部服务 |
| 启动命令 | `uvicorn api.main:app --reload` | Railway 自动处理 |
| 访问地址 | `http://localhost:8000` | `https://your-app.railway.app` |

## 故障排查

### 1. mem0 安装失败

如果 Git 依赖安装有问题，可以考虑：
- 确保 fork 的仓库是公开的
- 或者将 fork 的代码复制到项目中作为子模块

### 2. 数据库连接失败

- 检查 Railway 插件是否正确运行
- 确认环境变量名称正确
- 查看 Railway 部署日志

### 3. 内存不足

- Railway 免费版内存限制 512MB
- 可能需要升级付费计划或优化代码
