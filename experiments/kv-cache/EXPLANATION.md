# KV Cache 与上下文管理：实验讲解

本实验对应《深入理解 AI Agent》第 2 章实验 2-3，参考[上游实验](https://github.com/bojieli/ai-agent-book/tree/main/chapter2/kv-cache)。本仓库的[实现](experiment.py)、[运行说明](README.md)和[原始实验记录](RESULTS.md)可用于复现下文的数据。

## 一、实验目标

1. 理解多轮 Agent 请求中“稳定前缀”的含义，以及它为什么可能提高 KV Cache 复用率。
2. 比较六种上下文构造方式：稳定上下文、动态系统提示、工具顺序变化、动态用户资料、滑动窗口和文本拼接历史。
3. 分清两类证据：本地请求结构的共同前缀，以及模型服务实际报告的缓存 token。前者不能冒充后者。
4. 将结论用于 AI 剧本杀主持人的上下文设计：固定规则与工具定义，妥善放置动态状态，并保留消息角色边界。

## 二、实验原理

模型处理输入时，会为注意力计算生成 Key 和 Value。服务端若支持跨请求的前缀缓存，后续请求与已有请求相同的前缀就有机会复用已计算的部分。缓存是否命中、命中多少由服务端决定；Python 中是否复用同一个消息列表对象并不是判定依据。

例如，把固定规则放在前面、逐轮对话追加在后面，前几轮内容可形成稳定前缀。反过来，每次在 system 开头写入时间戳或积分，会让请求从靠前的位置开始变化；重排工具定义也会改变前部内容。裁剪历史会缩短输入，但可能丢失事实，所以应同时观察总 token、任务质量和缓存 token。

实验使用两个不同指标：

- **离线共同前缀占比**：把工具定义和消息序列化为 UTF-8 字节，计算相邻两轮从第一个字节起连续相同的长度，再除以本轮请求字节数。这只检查本地构造方式。
- **在线缓存占比**：`cached_input_tokens / input_tokens × 100%`。Codex CLI 从 `turn.completed.usage` 获取这两个值；直接 API 路径则读取响应中的缓存 token 字段。在线的“总耗时”包含完整调用过程，不是首 token 延迟（TTFT）。

## 三、实验过程

环境为 Windows PowerShell、Python 3.12.5。本机 Codex CLI 已通过 ChatGPT 登录，没有配置 Moonshot 或 OpenAI Platform API Key。脚本用相同的五个问题、规则文本和工具定义，分别构造六种模式，每种模式运行五轮。

| 模式 | 构造差异 |
| --- | --- |
| `correct` | 固定 system 和工具顺序，保留结构化历史 |
| `dynamic_system` | 每轮在 system 开头加入变化值 |
| `shuffled_tools` | 每轮轮换工具定义顺序 |
| `dynamic_profile` | 每轮在 system 开头加入变化的用户积分 |
| `sliding_window` | 仅保留最近四条历史消息 |
| `text_format` | 将历史拼成一条 user 文本 |

先运行离线检查，再通过本机 Codex CLI 获取真实的 CLI 使用量：

```powershell
cd experiments/kv-cache
python -B -m unittest -q test_experiment.py
python -B experiment.py --dry-run
python -B experiment.py --provider codex-cli --compare --timeout 180
python -B experiment.py --report 'results/result_codex-cli_*.json'
```

CLI 路径使用官方支持的 `codex exec --json`，按轮启动只读临时会话，并从完成事件解析 token 指标。Windows 上曾发生过 `codex.cmd` 命令行参数转义导致 JSON 提示没有送达；改为从标准输入传入后，逐轮检查了模型回答，才保留最终六份结果。测试共 10 项，全部通过。

## 四、实验结果

### 1. 离线请求结构

下表为第 2–5 轮相邻请求的平均共同前缀字节占比：

| 模式 | 共同前缀占比 |
| --- | ---: |
| `correct` | 98.5% |
| `dynamic_system` | 8.8% |
| `shuffled_tools` | 0.6% |
| `dynamic_profile` | 8.8% |
| `sliding_window` | 97.3% |
| `text_format` | 98.8% |

这证明动态 system/profile 和工具轮换确实改变了本地请求前部。`sliding_window` 与 `text_format` 在这组任务里仍保留较长的字节前缀；不能据此说它们必然导致缓存失效，也不能把这些百分比当作真实缓存命中率。

### 2. Codex CLI 实测

2026-09-20 顺序运行，每种模式五轮；结果按运行顺序列出：

| 模式 | 输入 tokens | 缓存输入 tokens | 缓存占比 | 总耗时 |
| --- | ---: | ---: | ---: | ---: |
| `correct` | 63,902 | 52,096 | 81.5% | 52.9 秒 |
| `dynamic_system` | 62,713 | 53,120 | 84.7% | 47.6 秒 |
| `shuffled_tools` | 62,644 | 54,144 | 86.4% | 56.4 秒 |
| `dynamic_profile` | 62,685 | 53,120 | 84.7% | 50.6 秒 |
| `sliding_window` | 62,520 | 58,240 | 93.2% | 34.6 秒 |
| `text_format` | 63,858 | 54,144 | 84.8% | 37.1 秒 |

这些是 **Codex CLI 整个请求**的指标。CLI 在实验文本之前附加自己的大量固定上下文；在 CLI 路径中，实验的 system、历史和工具定义只是提示中的 JSON 文本，`shuffled_tools` 没有真正重排 CLI 工具 Schema。六种模式又是顺序执行，后运行模式可能受缓存预热影响。因此，表中的 `shuffled_tools` 或 `sliding_window` 占比较高，不能解释为它们比稳定上下文更好；总耗时也包含 CLI 启动开销。

## 五、总结

- **结构层面的结论已验证**：把变化内容放在请求开头或改变工具顺序，会明显缩短本地构造请求的共同前缀。
- **CLI 路径的采集已跑通**：无需读取 Codex 登录凭证，就能通过受支持的 CLI 接口获得真实的 `cached_input_tokens`；但其隐藏上下文和顺序效应使这组六模式数据不适合做缓存策略的因果排序。
- **工程实践**：主持人项目应稳定放置规则和工具定义，把每轮变化的状态放在后部；保持 system、user、assistant、tool 角色分离。历史裁剪要同时评估事实保留与 token 成本。
- **后续严格验证**：若要检验上游实验关于原生工具顺序与缓存命中的假设，需要使用独立的 OpenAI Platform 或 Moonshot API Key，直接发送结构化消息与工具 Schema，并在相同条件下重复、交错运行六种模式。当前本机未进行这一路径的实测。
