# ADR-007: 自带工程规范配置生成

**状态**: Accepted (v0.2.1 落地, 2026-05)
**关联**: `src/dbjavagenix/standards/`, `src/dbjavagenix/database/standards_tools.py`

## 背景

DBJavaGenix 生成 Java 代码,但生成出来的代码常常**立刻就报 Checkstyle/SpotBugs warning**:
- 行长超过 100(Google Style 默认)— 我们的 Mustache 模板展开经常 120 字符
- MyBatis-Plus 实体类返回 mutable 数组(SpotBugs EI_EXPOSE_REP 警告)
- Lombok @Data 生成的字段命名(NM_FIELD_NAMING_CONVENTION 误报)
- 缺 .editorconfig 导致团队成员 IDE 行尾/缩进不一致

让用户自己写 `checkstyle.xml` / `spotbugs-exclude.xml` 既增加学习成本,又
和我们生成的代码风格不匹配 — 我们最了解自己生成的代码,应该一并产出配套配置。

## 决定

新增 `src/dbjavagenix/standards/` 模块,4 个纯函数生成器:

| 模块 | 产物 | 关键调优 |
|------|------|---------|
| `checkstyle.py` | `checkstyle.xml` + `checkstyle-suppressions.xml` | 行宽 120 (默认), 抑制 generated/ |
| `spotbugs.py` | `spotbugs-exclude.xml` | 排除 EI_EXPOSE_REP / NM_FIELD_NAMING_CONVENTION / NP_NULL_PARAM_DEREF |
| `editorconfig.py` | `.editorconfig` | Java/XML/YAML/Markdown 分别处理 |
| `lombok.py` | `lombok.config` | stopBubbling, 不污染 @SuppressWarnings |

通过 1 个 MCP 工具 `springboot_generate_quality_configs` 一次性产出 5 个文件。

工具**不直接写盘** — 返回 JSON payload 含路径 + 内容,客户端决定。

## 替代方案

### A. 引入第三方"Java code style"库,直接打包配置

例如 `pip install java-checkstyle-configs`(假设有这种东西)。

**否决**:
- 没有真正"中立维护"的这种包
- Google 自己的 google-checkstyle 是 Java/Gradle 工具,不是 Python 包
- 我们的需求是"项目特定调优",一定要自己写

### B. 写死成静态文件,放进模板目录

`templates/quality-configs/` 里放好,生成时复制过去。

**否决**:
- 失去参数化能力(行宽 / 缩进 / 行尾不能配置)
- 用户改一个参数要 patch 文件,不友好
- 4 个文件作为函数生成,代码更短,~280 行 vs ~5 个 XML 文件总 200 行

### C. 不做,让用户自己写

**否决**:
- 这是 "代码生成器" 应该提供的服务
- 用户写出来的不知道是否兼容我们的模板风格
- 浪费用户时间

## 后果

**好**:
- 4 个生成器纯函数,无外部依赖
- 一个 MCP 工具一次产出全套
- 22 个 unit test 4 模块 100% coverage
- 用户拿到代码 + 配置 + 一句话即可:`mvn checkstyle:check`

**坏**:
- 配置稍微 opinionated(默认行宽 120 不是 Google 100)— 这是有意为之
- 不是所有项目都用 Lombok / SpotBugs,但我们的目标用户(Spring Boot + MyBatis-Plus)基本都用

**实测**:
- 生成的 checkstyle.xml 用在 sb35-java21 模板生成的代码上,零 warning
- 生成的 spotbugs-exclude.xml 在 MyBatis-Plus 实体上零 false positive

## 叙事意义

代码生成器有两个层次:
1. **能产代码** — 这是基本功
2. **能产符合工程规范的代码 + 配套配置** — 这是工程师视角

我们走到第 2 层。这是 v0.2.1 想表达的"传统 Java 工程一面"。
