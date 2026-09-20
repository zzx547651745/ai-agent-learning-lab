# 实验记录

日期：2026-09-20。环境：Windows PowerShell，Python 3.12.5。

## 目标

验证稳定请求前缀与六种上下文构造策略的差异，并在有 API Key 时收集服务商返回的缓存指标。

## 执行与结果

本机无 `MOONSHOT_API_KEY`、`KIMI_API_KEY` 或 `OPENAI_API_KEY`。已完成离线结构验证和复用 ChatGPT 登录状态的 Codex CLI 路径实测；直接 API 路径尚未运行。离线数据可通过 `python experiment.py --dry-run` 复现，单元验证通过 `python -m unittest -v test_experiment.py` 复现。

| 模式 | 第 2–5 轮平均共同前缀字节占比 |
| --- | ---: |
| correct | 98.5% |
| dynamic_system | 8.8% |
| shuffled_tools | 0.6% |
| dynamic_profile | 8.8% |
| sliding_window | 97.3% |
| text_format | 98.8% |

离线的共同前缀字节占比只说明请求结构如何变化。它不能替代服务商缓存命中率。尤其滑动窗口改变了请求长度，单独比较百分比容易误读。`text_format` 在这组任务里依然保有很长的字节前缀，所以不能断言它必然造成缓存失效；它的明确问题是丢失消息角色边界。

## Codex CLI 在线实测

命令：`python -B experiment.py --provider codex-cli --compare --timeout 180`。CLI 状态：`Logged in using ChatGPT`。2026-09-20 顺序执行，每个模式 5 轮，回答均对应各轮问题。读取 CLI 的 `turn.completed.usage`；原始 JSON 位于本地 `results/`（Git 忽略）。

| 模式 | 输入 tokens | 缓存输入 tokens | 缓存占比 | 总耗时 |
| --- | ---: | ---: | ---: | ---: |
| correct | 63,902 | 52,096 | 81.5% | 52.9 秒 |
| dynamic_system | 62,713 | 53,120 | 84.7% | 47.6 秒 |
| shuffled_tools | 62,644 | 54,144 | 86.4% | 56.4 秒 |
| dynamic_profile | 62,685 | 53,120 | 84.7% | 50.6 秒 |
| sliding_window | 62,520 | 58,240 | 93.2% | 34.6 秒 |
| text_format | 63,858 | 54,144 | 84.8% | 37.1 秒 |

这组数字**不能验证六种原生 API 策略的缓存优劣**：Codex CLI 会在实验文本之前附加自己的大段固定上下文，后运行模式还可能受前面调用的缓存预热影响。六种模式的 system、历史和工具定义在 CLI 路径中都是用户提示内的 JSON 文本；`shuffled_tools` 没有真正重排 CLI 的工具 Schema。初次实现曾把 JSON 放在 Windows `codex.cmd` 命令行参数中，CLI 收到不完整提示并回答“未提供 JSON 对话”；这些无效结果已删除。改为 stdin 后重新运行并检查了回答。

## 后续在线验收

设置 Moonshot Key 后执行 `python experiment.py --compare`，或设置 OpenAI Platform Key 后执行 `python experiment.py --provider openai --compare`。将 `results/` 中六份 JSON 作为原始记录，使用 `--report` 横向汇总。判读时优先看 `cached_tokens / prompt_tokens`，同时看总输入 token 和总耗时；若缓存字段为 `null`，注明服务商未提供该指标。不同服务商的结果应分开比较。
