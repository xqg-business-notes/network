# 哪些 AI 工具可以使用

这两个工具以 Agent Skill 文件夹发布，包含对话指令、参考说明和 Python 客户端。安装在 AI 工具中后，由那个工具读取指令、运行客户端并访问小强哥的服务。它们不是独立聊天网站，也不是安装到大模型本身。

## 使用条件

你的 AI 工具需要能够读取 `SKILL.md` 及其配套文件，运行 Python 3 脚本，并在你的授权下联网访问服务、在本地保存连接标识。不同系统的 Python 命令可能是 `python3`、`python` 或 `py -3`，由安装助手检查实际环境。

能读到文件或显示“安装成功”，还需要进一步确认服务连接正常；连接正常也不等于所有功能都已验证。不会运行脚本的普通聊天窗口，只粘贴 GitHub 链接不能获得这两个 Skill 的完整功能。

| 工具或入口 | 当前说明 |
|---|---|
| Codex | 官方支持 Skill 文件夹、配套脚本和参考资料；本项目已有安装与使用记录，具体能力受当前权限和网络影响。 |
| WorkBuddy | 官方支持导入技能包、执行脚本及调用第三方 API；已有用户反馈可安装使用小强哥的 Skill，但这两个 Skill 尚未逐一完成各系统、各功能的完整验证。 |
| Kimi Code CLI | 官方明确支持 Agent Skills、配套文件和命令执行，可按上述条件尝试；本项目尚未完成该客户端实测。这不等于普通 Kimi 聊天入口已经支持。 |
| Kimi、DeepSeek、豆包的普通网页或手机聊天入口 | 本项目尚未确认可以直接安装并完整运行，不能宣传为已支持。以具体产品版本是否提供 Skill、脚本与网络权限为准。 |
| 使用 DeepSeek 等模型的其他 Agent 工具 | 看承载模型的工具是否满足条件；选择了某个模型，不代表自动获得 Skill 安装和执行能力。 |

AI 工具的订阅、积分或模型费用按对应平台规则执行。

## 官方说明

- [Codex：Build skills](https://learn.chatgpt.com/docs/build-skills)
- [WorkBuddy：技能](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)
- [Kimi Code CLI：Agent Skills](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html)
- [DeepSeek：API 与 Agent 工具接入](https://api-docs.deepseek.com/)

以上文档说明平台能力，不代表平台为本项目背书，也不替代本项目在该平台上的实际测试。WorkBuddy 的使用反馈来自用户；本文没有将其写成完整兼容性认证。
