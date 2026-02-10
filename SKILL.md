---
description: Dropbox 文件夹自动监控与 Lark 通知 Skill
---

# Dropbox Monitor Skill

## 功能概述

监控指定 Dropbox 文件夹的新文件，并通过 Lark (飞书) 发送通知。支持文件自动下载和云文档上传。

## 部署要求

- Python 3.8+
- 依赖包: `pip install -r requirements.txt`
- 环境变量配置完成 (参考 `.env.example`)

## 快速调用

本 Skill 主要作为后台服务运行，也可以通过命令行手动触发。

```bash
# 手动运行一次检查
python3 monitor.py
```

## 自动化配置

建议使用系统的定时任务管理器 (如 macOS launchd 或 Linux cron) 来定期运行此脚本。

### macOS launchd 示例

1. 编辑 `com.user.dropbox.monitor.plist`
2. 加载任务: `launchctl load com.user.dropbox.monitor.plist`

## 维护

- **日志**: 查看 `monitor.log`
- **重置**: 删除 `data/snapshot.json` 可重新处理所有文件
