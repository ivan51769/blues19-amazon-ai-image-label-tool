# Agent 一句话安装提示词

把下面这一句话完整复制给 Codex、Claude Code 或其他能够操作 Windows 的 Agent：

```text
请从 https://github.com/ivan51769/blues19-amazon-ai-image-label-tool/releases/latest 在这台 Windows 10/11 电脑上安全安装或更新“亚马逊 AI 人物图片标签工具”：先确认 Release 属于 ivan51769 的公开仓库并检查现有安装；使用 HTTPS 将 blues19-amazon-ai-image-label-tool.exe 和 blues19-SHA256SUMS.txt 下载到范围明确的新临时目录，不覆盖用户源码或图片；用 Get-FileHash 计算 EXE 的 SHA-256 并与校验文件中同名文件的值比较，不一致时立即停止且不得运行；校验通过后将 EXE 安装到 %LOCALAPPDATA%\Programs\blues19-amazon-ai-image-label-tool，并在桌面创建当前用户快捷方式；更新时保留用户设置，只替换程序文件；启动后确认进程正常响应、主面板可见、拖入区域和悬浮窗可用，但不要擅自修改或处理用户图片；不要读取或输出浏览器登录信息、密码、令牌及其他凭据，不要关闭安全软件，不要执行 git reset、递归删除用户目录或放宽 PowerShell 安全策略；最后报告 Release 版本、安装路径、SHA-256 校验结果、进程状态和任何未完成项，不得仅声称“安装成功”。
```

## 验收标准

- 来源确认为 `ivan51769/blues19-amazon-ai-image-label-tool`。
- EXE 的 SHA-256 与 Release 校验文件一致。
- EXE 位于明确的当前用户安装目录。
- 桌面快捷方式存在，程序能够启动并正常响应。
- 未处理任何用户图片，除非用户随后明确指定。
- 最终结果包含实际验证信息和未完成项。

## 安全边界

- 不读取、回显或保存密码、令牌、Cookie、验证码和账户数据。
- 不关闭防病毒软件，不降低系统或 PowerShell 安全策略。
- 不使用管理员权限，除非安装必要组件时确实需要且用户明确批准。
- 不覆盖用户图片或其他项目文件。
- 不把“完成下载”当成“完成安装”，必须实际运行测试并验证程序进程。
