# PaperPilot 在线部署说明

本文档用于将 PaperPilot 部署为可运行 Demo。当前推荐使用 Streamlit Community Cloud，因为项目入口是 `streamlit run app.py`。

## 1. 本地运行

```bash
git clone <repo-url>
cd paperpilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

启动后访问 `http://localhost:8501`。

`.env` 只用于本地运行，文件中不要提交真实 API Key。没有 API Key 时，系统仍会以基础模式启动。

## 2. Streamlit Community Cloud 在线部署

1. 将代码上传到 GitHub 仓库。
2. 打开 Streamlit Community Cloud。
3. 点击 New app。
4. 选择对应 GitHub 仓库和分支。
5. Main file path 填写 `app.py`。
6. Python 版本使用 `runtime.txt` 中的 `python-3.11`。
7. 在 App settings / Secrets 中配置 API Key，或保持为空，让用户在页面侧边栏临时输入自己的 API Key。
8. 点击 Deploy。
9. 部署完成后复制公开访问链接，填写到 README 的 Online Demo 部分。

## 3. Streamlit Secrets 示例

推荐使用项目自己的 OpenAI 兼容配置名：

```toml
LLM_API_KEY = "your_openai_compatible_api_key_here"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

如果只使用 OpenAI 默认环境变量名，也可以配置：

```toml
OPENAI_API_KEY = "your_openai_api_key_here"
```

不要在 GitHub 仓库中提交 `.env` 或 `.streamlit/secrets.toml`。

## 4. 在线输入 API Key

如果部署者不希望在 Streamlit Secrets 中配置自己的 API Key，可以保持 Secrets 为空。用户打开在线 Demo 后，可在侧边栏“LLM API 设置”中临时输入自己的 API Key、Base URL 和模型名称。

该方式适合公开演示，因为 API Key 只保存在当前 Streamlit 会话中，不会写入仓库或项目文件。页面刷新、会话过期或服务重启后，用户可能需要重新输入。

注意事项：

- 不要把真实 API Key 写入 README；
- 不要把真实 API Key 写入 `.env.example`；
- 不要提交 `.env`；
- 不要提交 `.streamlit/secrets.toml`；
- 在线输入的 API Key 只用于当前会话。

## 5. 无 API Key 模式说明

未配置 API Key 时，系统仍可运行基础论文搜索、排序、PDF 解析、基础总结、关键词问答、趋势分析、关系图谱、文献综述和科研洞察等流程。依赖 LLM 的摘要生成、问答、Reviewer 分析和创新点分析会自动降级为规则或模板模式，页面不会因为缺少 API Key 直接崩溃。

## 6. Docker 兜底运行

如果考核环境更适合 Docker，可以使用：

```bash
docker build -t paperpilot .
docker run -p 8501:8501 --env-file .env paperpilot
```

如果没有 `.env`，也可以直接运行：

```bash
docker run -p 8501:8501 paperpilot
```

## 7. 常见问题

### ModuleNotFoundError

检查是否已经运行：

```bash
pip install -r requirements.txt
```

### API Key not found

本地运行时检查 `.env`；在线部署时检查 Streamlit Cloud 的 Secrets，或在侧边栏“LLM API 设置”中临时输入 API Key。没有 API Key 时系统会进入基础模式，不应导致首页崩溃。

### FileNotFoundError

检查项目是否包含 `data/` 目录。系统会自动创建 `data/notes` 和 `data/uploads`，但部署时仍建议保留目录中的 `.gitkeep`。

### Streamlit 页面空白

查看 Streamlit Cloud 部署日志，重点检查依赖安装、Python 版本、Main file path 是否为 `app.py`。
