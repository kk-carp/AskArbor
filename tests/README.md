# 测试目录说明

测试按边界分为两层：

- `tests/unit/`：纯函数与单模块逻辑（切片、解析、存储、检索、问答编排、授权规则）。
- `tests/integration/`：跨模块协作与应用集成点（路由认证流程、数据库初始化流程）。

## 覆盖边界标注

| 目录 | 覆盖对象 | 不覆盖对象 |
| --- | --- | --- |
| `tests/unit/` | `infra`、`domain`、`services` 的单模块行为 | FastAPI 生命周期、真实数据库、真实模型调用 |
| `tests/integration/` | `routes` + 服务协作、`db.init_db` 初始化编排 | 真实 DeepSeek/BGE-M3 在线调用 |
