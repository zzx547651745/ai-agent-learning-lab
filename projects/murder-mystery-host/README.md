# AI 剧本杀主持人

## MVP

- 3 人、文本互动、一个人工编写的短剧本；
- 主持人 Agent 只生成候选事件或工具调用；
- 服务端状态机与规则引擎校验后才写入事件流；
- 角色信息、线索和私有记忆必须按权限隔离；
- 每局可保留 Trace，后续接入 Eval 与 Replay。

## 核心数据对象

`Scenario`、`Character`、`Clue`、`GameState`、`Event`、`PrivateMemory`、`Trace`。

## 当前状态

尚未开始实现。第 1 周从 FastAPI、最小状态模型和 `HostAgent` 开始。

