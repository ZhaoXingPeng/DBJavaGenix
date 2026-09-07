---
name: java-codegen-from-db
description: 从 MySQL/PostgreSQL/SQLite 数据库表反向生成 Spring Boot Java 工程代码(Entity/DAO/Service/Controller/Mapper)。当用户提到"生成 Java 代码"、"反向工程"、"按数据库建模"、"从表生成 Spring Boot"等需求,且能提供数据库连接信息或已有连接时使用。
when_to_use:
  - 用户提供了数据库连接(host/port/user/pwd/database)并要求生成 Java 代码
  - 用户已经通过 db_connect_test 建立了连接,提到具体表名要"生成代码"/"做反向工程"
  - 用户提到 Spring Boot 项目"从数据库建模"或要求把表结构转成 Entity/Repository/Service
when_not_to_use:
  - 用户只是想"看一下表结构" → 直接用 db_table_describe,不要走完整 skill
  - 用户在做 Spring Boot 版本升级(2.x → 3.x)→ 使用 springboot-migration skill
  - 用户在调试现有代码 → 不需要生成
---

# java-codegen-from-db

## 工作流总览

本 skill 把"从数据库表生成 Java 代码"拆为 **5 个显式阶段**,每个阶段调用具体的 MCP 工具,关键决策点会暂停让用户确认。**不允许跳步**——前一步的输出是后一步的输入。

```
[1] 预检查项目  →  [2] schema 分析  →  [3] 语义增强(可选)
                                              ↓
                  [5] 写盘   ←   [4] 分层渲染(等待用户确认)
```

---

## 阶段 1: 预检查项目(必做)

**目的**: 在生成代码前确认目标 Spring Boot 项目结构合法、依赖大致齐全。否则生成出来也编译不过。

### 1.1 验证项目结构

调用 **`springboot_validate_project`**:
- 参数: `{ "check_dependencies": true, "create_missing_dirs": true, "template_category": "<用户选定的分类>" }`
- 期待返回中包含 `Project Structure: ✅ OK` 或 `✅ Project Root`
- 如果失败 → 告诉用户具体缺什么,**不要继续**

### 1.2 分析依赖健康度

调用 **`springboot_analyze_dependencies`**:
- 参数:
  ```json
  {
    "template_category": "<同上>",
    "database_type": "mysql|postgresql|sqlite",
    "include_swagger": true,
    "include_lombok": true,
    "include_mapstruct": true
  }
  ```
- 返回中提取 `Missing Dependencies: N`:
  - N == 0 → health = 100,继续
  - N ≤ 2 → health = 80,继续但提醒用户
  - N ≤ 5 → health = 60,**暂停让用户决定是否继续**
  - N > 5 → health = 40,**强烈建议先修依赖**,问用户是否要看具体清单

### 1.3 渲染依赖健康仪表盘(MCP App)

如果客户端支持 MCP Apps(`_meta` 渲染),返回值中应附加:
```json
{
  "_meta": {
    "mcp-apps/component": "dashboard",
    "mcp-apps/data": { "score": <health>, ... }
  }
}
```
现阶段如未支持,用文本表格代替。

---

## 阶段 2: schema 分析(必做)

**目的**: 拿到目标表的列、主键、外键、索引,这是模板渲染的输入。

### 2.1 建立或复用连接

如果用户尚未连接:
- 调用 **`db_connect_test`** with `{host, port, username, password, database, database_type}`
- 拿到 `connection_id`,记住它,后续所有调用都要带

### 2.2 列出表名(可选)

当用户没指明表,先列出来让用户选:
- 调用 **`db_query_tables`** with `{connection_id, database}`
- 把表名列给用户,等用户选

### 2.3 描述目标表

对每张目标表:
- 调用 **`db_table_describe`** with `{connection_id, database, table, include_java_types: true}`
- 这一步会返回列定义 + 推断的 Java 类型

### 2.4 获取外键关系

- 调用 **`db_table_foreign_keys`** with `{connection_id, database, table}`
- 多张表时一起调,然后给用户渲染 ER 图(MCP App `mermaid` 组件)

### 2.5 渲染 ER 图(MCP App)

当用户选了 ≥ 2 张表,构造 Mermaid `erDiagram` 字符串,放进 `_meta["mcp-apps/source"]`。

---

## 阶段 3: 语义增强(推荐,Phase 4 工具可用后启用)

> 当前 Phase 2 时这些工具尚未实现,跳过本阶段直接进 4。

**目的**: 让 LLM 推断"业务上合理的类名/字段名",而不是机械拼接表名。

### 3.1 推断业务命名(待实现)

- 调用 `ai_infer_business_names`(Phase 4 工具,详见 iteration-plan)
- 例: `sys_user_role` → `UserRoleAssignment`(关系实体)

### 3.2 推荐模板(待实现)

- 调用 `ai_recommend_template`
- 例: 检测到 RBAC 模式 → 建议 `MybatisPlus-Mixed` 或 `sb35-java21`

### 3.3 用户确认点 ★

LLM **必须**把推断结果呈现给用户,等用户确认或修改,再进下一步。**禁止默认接受**。

---

## 阶段 4: 分层代码生成(★ 用原子工具,而不是大工具)

**重要**: Phase 2.2 之后,我们用 7 个原子工具替代旧的 `db_codegen_generate`。**优先用原子工具**。

### 4.1 构建上下文

调用 **`codegen_build_context`**:
```json
{
  "connection_id": "<...>",
  "table_name": "<...>",
  "database": "<...>",
  "template_category": "Default | MybatisPlus | MybatisPlus-Mixed | sb35-java21",
  "author": "<...>",
  "package_name": "com.example.xxx",
  "include_swagger": true,
  "include_lombok": true,
  "include_mapstruct": true,
  "project_path": "test_project"
}
```
返回值: 完整的 `context` 对象(JSON,**不写盘**)。LLM 把这个对象作为后续 render 工具的输入。

### 4.2 分层渲染

按顺序对**每个层**调用对应工具,每次都传 `context`:

| 工具 | 渲染层 | 模板文件 |
|------|--------|----------|
| `codegen_render_entity` | 实体类 | entity.mustache |
| `codegen_render_dao` | DAO/Repository | dao.mustache |
| `codegen_render_service` | Service 接口 | service.mustache + serviceImpl.mustache |
| `codegen_render_controller` | REST Controller | controller.mustache |
| `codegen_render_mapper` | MyBatis XML | mapper.mustache(仅 MybatisPlus/Mixed) |
| `codegen_render_dto` | DTO(sb35-java21 record) | dto.mustache(可选) |

每次返回:
```json
{
  "code": "<完整 Java 源码字符串>",
  "file_path": "<相对路径,如 com/example/entity/SysUser.java>",
  "_meta": {
    "mcp-apps/component": "code-diff",
    "mcp-apps/language": "java",
    "mcp-apps/before": "<目标位置已存在文件的内容,无则 null>",
    "mcp-apps/after": "<同 code>"
  }
}
```

### 4.3 用户确认点 ★

渲染完所有层后,**先不要写盘**。让用户:
1. review 每个文件的内容(MCP App diff 渲染)
2. 修改 `context`(如包名、字段类型)
3. 重新调用对应的 `codegen_render_*`

确认无误后才进阶段 5。

### 4.4 兼容退路: 单体工具

如果某些环境只有旧版工具:
- 调用 **`db_codegen_generate`** (单次完成 2.1~4.4 + 写盘)
- 仅当用户明确要"一步到位"时使用,**默认走原子工具路径**

---

## 阶段 5: 写盘

### 5.1 调用写盘工具

> Phase 2.2 引入: 现阶段写盘逻辑在原子工具或 `db_codegen_generate` 内部。后续会拆出独立 `file_write_to_project` 工具。

### 5.2 渲染包结构树(MCP App)

写盘前/后用 `tree` 组件展示新生成文件的目录结构,让用户最后确认。

### 5.3 备份与回滚

如果目标文件已存在,生成 `*.codegen.bak` 备份,告诉用户怎么回滚(`mv x.bak x`)。

---

## 错误处理与重试规则

- **连接失败**: 不要无限重试,告诉用户检查 host/port/credentials
- **表不存在**: 调用 `db_query_table_exists` 二次确认,**不要假设**
- **依赖严重缺失** (health < 60): 暂停,问用户是否要看 `springboot_analyze_dependencies` 详细报告
- **写盘失败**: 报告具体 IO 错误,不要静默吞掉
- **模板渲染失败**: 检查 `template_context` 字段完整性(常见: `className`、`columns`、`primaryKeyType` 缺失)

## 工具调用清单速查

按调用顺序:

```
[预检] springboot_validate_project
       springboot_analyze_dependencies

[schema] db_connect_test            (若未连接)
         db_query_tables            (若未指定表)
         db_table_describe          (×N 张表)
         db_table_foreign_keys      (×N 张表)

[语义]   ai_infer_business_names    (Phase 4 后启用)
         ai_recommend_template      (Phase 4 后启用)

[生成]   codegen_build_context      (×1 per 表)
         codegen_render_entity      (×1 per 表)
         codegen_render_dao         (×1 per 表)
         codegen_render_service     (×1 per 表)
         codegen_render_controller  (×1 per 表)
         codegen_render_mapper      (×1 per 表, 仅 MybatisPlus)
         codegen_render_dto         (×1 per 表, 仅 sb35-java21)

[写盘]   (内置于上述工具,Phase 3 后拆出 file_write_to_project)
```

## 设计原则

1. **显式编排** > 黑盒自动: skill 把"做什么、按什么顺序、何时停"写死,LLM 不要自由发挥
2. **原子工具** > 大而全: 每个工具职责单一,返回值清晰
3. **用户决策点不可绕过**: 语义推断、模板选择、写盘三处必须 pause
4. **context 显式传递**: 工具间通过参数传 `context`,不依赖 server 内部状态
5. **失败要说人话**: 不要把堆栈直接糊给用户

## 与 iteration-plan 的对应

本 skill 实现 `iteration-plan/01-target-architecture.md` 第二章的工作流定义。Phase 2.2 拆分工具、Phase 4 引入 AI 工具后,本文件需同步更新阶段 3 和阶段 4。
