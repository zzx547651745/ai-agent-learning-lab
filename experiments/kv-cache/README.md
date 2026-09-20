# KV Cache：稳定前缀实验（第 2 章实验 2-3）

上游：[bojieli/ai-agent-book 的实验说明](https://github.com/bojieli/ai-agent-book/tree/main/chapter2/kv-cache)。本目录是独立复现，使用 Python 标准库，不复制上游源码。目标是比较六种请求构造策略对前缀连续性和服务商报告的缓存 token 的影响。

需要从目标、原理到结论的完整说明，可阅读[实验讲解](EXPLANATION.md)。

## 环境与运行

- Python 3.10 或更高版本；本机已用 Python 3.12.5 验证。
- 无 Key 时，运行离线结构验证：

```powershell
cd experiments/kv-cache
python -m unittest -v test_experiment.py
python experiment.py --dry-run
```

- 有 Moonshot/Kimi Key 时，运行在线测量。每种模式发起 5 次请求，六种模式共 30 次请求，可能产生费用。Key 只从环境变量读取，不写入仓库。

```powershell
$env:MOONSHOT_API_KEY = "你的 Key"
python experiment.py --mode correct
python experiment.py --compare
python experiment.py --report results/result_*.json
```

若使用 **OpenAI Platform API Key**，设置 `OPENAI_API_KEY` 后选用 OpenAI 服务商：

```powershell
$env:OPENAI_API_KEY = "你的 Platform API Key"
python experiment.py --provider openai --mode correct
python experiment.py --provider openai --compare
python experiment.py --report results/result_openai_*.json
```

OpenAI 模式默认 `gpt-4.1-mini` 和 `https://api.openai.com/v1`，读取 `usage.prompt_tokens_details.cached_tokens`。Codex 的 ChatGPT 登录凭证不是通用 API Key；程序不会读取 Codex 的认证缓存。OpenAI Platform API 使用独立计费。可用 `--model`、`--base-url`、`--timeout` 和 `--output-dir` 调整配置。在线结果保存到 `results/`，此目录被 Git 忽略。

本机已登录 Codex CLI 时，可直接复用其登录状态运行，无需导出 Key：

```powershell
python experiment.py --provider codex-cli --mode correct
python experiment.py --provider codex-cli --compare
python experiment.py --report results/result_codex-cli_*.json
```

这个路径使用官方 `codex exec --json`，读取 `turn.completed.usage.input_tokens` 和 `cached_input_tokens`。每轮启动独立只读、临时会话，并尽量关闭与实验无关的 CLI 能力。实验提示通过标准输入传递，避免 Windows 的 `.cmd` 参数转义破坏 JSON。CLI 会附带自己的隐藏指令和工具上下文；实验中的 system 和工具定义是作为 JSON 文本交给 CLI，**不是 API 的原生 system 消息或真实工具 Schema**。因此它展示 Codex CLI 路径的缓存情况，结果不能与 OpenAI/Moonshot API 路径直接作同口径比较，尤其 `shuffled_tools` 只改变文本顺序。启动开销也包含在总耗时里。

## 六种策略

| 模式 | 请求构造 |
| --- | --- |
| `correct` | 固定 system、固定工具顺序、保留结构化历史 |
| `dynamic_system` | 每次在 system 开头插入变化的时间戳 |
| `shuffled_tools` | 每次轮换工具定义顺序 |
| `dynamic_profile` | 每次在 system 开头插入变化的积分数 |
| `sliding_window` | 只保留最近 4 条历史消息 |
| `text_format` | 把历史拼成单条 user 文本 |

各模式使用相同的 5 个任务、模型、固定规则文本和工具定义。工具选择为 `none`，所以本复现比较请求结构而不执行 ReAct 工具链。Moonshot 模式设置 `temperature=1` 以符合 Kimi 推理模型约束；OpenAI 模式由模型使用默认温度。

## 结果与判读

`--dry-run` 输出**序列化请求的共同前缀字节占比**。这是本地结构代理指标，不是实际 KV Cache 命中，也不是 token 命中率。它可以确认策略确实改变了请求前缀。

在线结果记录每轮 `prompt_tokens`、`cached_tokens`、回答和端到端耗时。`cache_ratio_percent = cached_tokens / prompt_tokens × 100`。若 API 没有返回缓存字段，显示 `null`，不能把它解释为零命中。这里测量的是完整请求耗时，**不是 TTFT**。动态信息放在 system 开头用于清楚地展示失效边界；不同服务商可能有不同的缓存粒度、阈值和计费方式，所以不要仅凭一次运行推断固定的速度或节省比例。

离线与本机 Codex CLI 实测结果（2026-09-20，Python 3.12.5）：见本目录的 `RESULTS.md`。本机未配置 Platform API Key，尚无直接 API 路径的实测数据。

## 失败案例与主项目迁移

- 把每轮时间戳、积分和阶段号放进系统前缀，会使请求在开头就不同。主持人项目中的动态 `GameState` 应放在稳定规则之后，避免改写规则本身。
- 随机排列工具定义会改变前缀；主持人项目应固定工具注册顺序和 Schema 序列化顺序。
- 裁剪历史可能降低总输入量，也可能丢失必要事实；应分别观察任务质量、总 token 和缓存 token，不能只看缓存百分比。
- 把历史拼成一段文本会丢失角色边界；主持人项目应保留 system、user、assistant、tool 的结构化消息。
