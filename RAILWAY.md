# Railway 部署配置指南

本指南使用 **Railway + Neo4j Aura + Qdrant Cloud** 的组合部署方案。

## 架构说明

| 组件 | 服务 | 费用 |
|------|------|------|
| 应用 | Railway | 免费（$5/月额度） |
| 图数据库 | Neo4j Aura Free | 免费 |
| 向量数据库 | Qdrant Cloud Free | 免费 |
| LLM | Gemini API | 按量（有免费额度） |

---

## 第一步：注册云数据库服务

### 1.1 Neo4j Aura（图数据库）

1. 访问 https://neo4j.com/cloud/aura/
2. 注册账号（免费）
3. 创建新实例：
   - 选择 **AuraDB Free**
   - 类型选择 **Neo4j 5**
   - 选择区域（推荐离你最近的）
4. 创建后获取连接信息：
   - **Connection URL**: 类似 `bolt+s://xxxxx.databases.neo4j.io:7687`
   - **Password**: 自动生成的密码

**免费额度**: 200k 节点 + 400k 关系

### 1.2 Qdrant Cloud（向量数据库）

1. 访问 https://cloud.qdrant.io/
2. 注册账号（免费）
3. 创建新集群：
   - 点击 "Create Cluster"
   - 选择 **Free** 计划
   - 选择区域
4. 创建后获取连接信息：
   - **REST API URL**: 类似 `https://xxxxx.aws.cloud.qdrant.io:6333`
   - **API Key**: 在 Dashboard 的 "API Keys" 页面创建

**免费额度**: 1GB 存储

### 1.3 Gemini API Key

1. 访问 https://aistudio.google.com/apikey
2. 创建新的 API Key

---

## 第二步：在 Railway 部署应用

### 2.1 创建 Railway 项目

1. 访问 https://railway.app/
2. 登录后点击 **New Project**
3. 选择 **Deploy from GitHub repo**
4. 授权 GitHub 并选择 `kun-dehuang/memory-select` 仓库
5. 等待 Railway 检测项目类型（Python）

### 2.2 配置环境变量

在 Railway 项目中：
1. 点击项目名称进入设置
2. 选择 **Variables** 标签
3. 添加以下环境变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `GEMINI_API_KEY` | `你的 Gemini API Key` | 从 Google AI Studio 获取 |
| `MEM0_NEO4J_URI` | `bolt+s://xxxxx.databases.neo4j.io:7687` | Neo4j Aura 连接 URL |
| `MEM0_NEO4J_USER` | `neo4j` | 固定值 |
| `MEM0_NEO4J_PASSWORD` | `你的 Aura 密码` | Neo4j Aura 密码 |
| `MEM0_QDRANT_HOST` | `https://xxxxx.aws.cloud.qdrant.io:6333` | Qdrant REST API URL（含端口） |
| `QDRANT_API_KEY` | `你的 Qdrant API Key` | Qdrant 云服务密钥 |

### 2.3 部署

配置完成后，Railway 会自动重新部署。查看 **Deployments** 标签确认部署成功。

---

## 第三步：测试部署

部署成功后，Railway 会提供一个公网 URL，例如：
```
https://memory-select-production.up.railway.app
```

### 测试端点

```bash
# 1. 健康检查
curl https://your-app.up.railway.app/health

# 预期输出:
# {"status":"healthy","version":"0.1.0"}

# 2. 获取 OpenAI Functions Schema
curl https://your-app.up.railway.app/api/v1/functions/schema

# 3. 统计记忆数量
curl "https://your-app.up.railway.app/api/v1/memory/count?uid=test_user"

# 4. 添加一条记忆
curl -X POST https://your-app.up.railway.app/api/v1/memory/add \
  -H "Content-Type: application/json" \
  -d '{"uid": "test_user", "text": "测试 Railway 部署"}'

# 5. 搜索记忆
curl -X POST https://your-app.up.railway.app/api/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Railway", "uid": "test_user", "limit": 5}'
```

---

## 故障排查

### 1. 部署失败 - mem0 安装错误

**问题**: Git 依赖安装失败

**解决方案**:
- 确保 fork 的 mem0 仓库是公开的
- 检查仓库地址: `git+https://github.com/kun-dehuang/mem0-code.git@main#egg=mem0ai`

### 2. 数据库连接失败

**问题**: 无法连接到 Neo4j 或 Qdrant

**解决方案**:
- 检查环境变量是否正确设置
- Neo4j URL 必须是 `bolt+s://` 格式
- Qdrant URL 必须是完整的 `https://` 地址（含端口 `:6333`）
- 查看 Railway 部署日志获取详细错误

### 3. 内存不足

**问题**: Railway 免费版内存限制 512MB

**解决方案**:
- 升级到 Railway 付费计划（$5/月起）
- 或优化代码减少内存使用

### 4. API 密钥无效

**问题**: Gemini API 或 Qdrant API 认证失败

**解决方案**:
- 重新生成 API Key
- 确认 API Key 没有多余的空格或换行符
- 检查 API Key 是否有足够的配额

---

## 本地开发 vs 生产部署

| 项目 | 本地开发 | Railway 生产 |
|------|----------|-------------|
| mem0 安装 | `pip install -e /path/to/mem0-code` | 从 GitHub 自动安装 |
| Qdrant | `localhost:6333` (Docker) | Qdrant Cloud |
| Neo4j | `bolt://localhost:7687` (Docker) | Neo4j Aura |
| 启动命令 | `uvicorn api.main:app --reload` | Railway 自动处理 |
| 访问地址 | `http://localhost:8000` | `https://your-app.up.railway.app` |

---

## 费用估算

| 服务 | 免费额度 | 超出后费用 |
|------|---------|-----------|
| Railway | $5/月额度 | $0.00028/GB-hour |
| Neo4j Aura | 200k 节点 | 从 $7/月起 |
| Qdrant Cloud | 1GB 存储 | 从 $25/月起 |
| Gemini API | 每日免费额度 | 按使用量计费 |

小型项目完全在免费额度内。

---

## 下一步

部署成功后，你可以：

1. **设置自定义域名** (Railway 支持)
2. **配置监控和告警**
3. **添加 API 认证** (如果需要公开访问)
4. **连接你的 Agent** 使用 Memory API
