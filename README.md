# Dropbox Monitor & Lark Notification

这是一个轻量级的自动化工具，用于监控 Dropbox 共享文件夹的更新，并通过 Lark (飞书) 发送通知。

## ✨ 核心功能

1. **智能监控 & 下载**
    - 定时检查 Dropbox 共享链接。
    - **自动重命名**: 下载的文件会自动执行标准化重命名，规则如下：
        - 转为小写 (e.g., `Report.PDF` -> `report.pdf`)
        - 替换空格为连字符 (e.g., `Daily Report` -> `daily-report`)
        - 去除首尾多余空格
2. **飞书 (Lark) 集成**
    - **消息卡片推送**: 发送美观的富文本卡片通知。
    - **云文档集成**: (可选) 自动将文件上传到飞书云文档，并在通知中直接附带预览链接，无需跳出。

## 目录结构

```
.
├── monitor.py                  # 核心脚本
├── .env.example                # 配置文件模版
├── requirements.txt            # 依赖列表
└── com.user.dropbox.monitor.plist.template # macOS 定时任务配置模版
```

## 🚀 快速开始

### 1. 安装依赖

确保已安装 Python 3。

```bash
git clone <your-repo-url>
cd dropbox-monitor
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
nano .env
```

### 3. 配置 Lark (飞书) 机器人

#### 方案 A: 简易模式 (仅通知)
1. 在飞书群组中添加"自定义机器人"。
2. 复制 Webhook 地址 (格式: `https://open.larksuite.com/.../hook/...`)。
3. 填入 `.env` 的 `LARK_WEBHOOK_URL`。

#### 方案 B: 高级模式 (支持文件上传 & 预览)
1. 登录 [飞书开放平台](https://open.larksuite.com/) 创建企业自建应用。
2. 启用 **机器人** 能力。
3. 在 **权限管理** 中开启以下权限：
    - `im:message:send_as_bot` (以应用身份发消息)
    - `drive:drive:readonly` (查看云文档)
    - `drive:file:upload` (上传文件)
4. 获取 App ID 和 App Secret，填入 `.env`。

### 4. 运行测试

```bash
python3 monitor.py
```

---

## 📢 通知模版示例

当检测到新文件时，机器人会发送如下格式的交互式卡片：

| 元素 | 内容示例 |
|------|----------|
| **标题** | 🔔 Dropbox 文件更新 (颜色: Orange/Blue) |
| **正文** | **最新文件：**<br>`daily-report-2024.pdf` |
| **链接** | [📂 点击查看云文档] (仅高级模式)<br>或 [点击前往 Dropbox 查看] |

**无新文件时** (如开启心跳):
- 标题: 监控心跳-✖️
- 正文: 暂无更新
- 颜色: Grey

---

## 自动化运行 (macOS)

使用 `launchd` 实现定时运行。

1. 修改 `com.user.dropbox.monitor.plist.template` 中的路径配置：
    - 修改 `python3` 的绝对路径 (可通过 `which python3` 获取)。
    - 修改 `monitor.py` 的绝对路径。
2. 将文件移动到 `~/Library/LaunchAgents/`：
    ```bash
    cp com.user.dropbox.monitor.plist.template ~/Library/LaunchAgents/com.user.dropbox.monitor.plist
    ```
3. 加载任务：
    ```bash
    launchctl load ~/Library/LaunchAgents/com.user.dropbox.monitor.plist
    ```

---

## 作为 Agent Skill 使用

本工具可作为 Agent 的被动感知技能。

**Skill 指令**:
- **Run**: 直接执行 `python3 monitor.py` 即可触发一次完整检查。
- **Reset**: 删除 `data/snapshot.json` 文件，Agent 下次运行时将重新处理并推送所有文件。
