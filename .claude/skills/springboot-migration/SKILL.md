---
name: springboot-migration
description: Spring Boot 2.7 → 3.x 升级迁移工作流。读取现有项目配置 + 依赖,推断版本,生成 javax→jakarta、SpringDoc、Spring Security 6 等关键迁移步骤的检查清单与执行计划。当用户提到"升级 Spring Boot"、"javax 改 jakarta"、"Spring Boot 2 升 3"、"接口废弃了"等场景时使用。
when_to_use:
  - 用户提到"Spring Boot 升级"、"从 2.x 升到 3.x"、"javax 替换 jakarta"
  - 用户提到 swagger / springfox 报错,需要换 SpringDoc
  - 用户提到 Spring Security 5.x DSL 在 6.x 上不工作
  - pom.xml / build.gradle 还在用 2.7.x 但想用 Java 17/21 record/sealed
when_not_to_use:
  - 用户在做"从零搭建 Spring Boot 项目" → 不需要迁移,用 java-codegen-from-db skill
  - 用户在做 Spring Boot 3.0 → 3.5 的小版本升级 → 直接读 release notes,不必走完整流程
  - 用户在做 Spring Cloud 升级 → 单独问题,Spring Boot 版本只是连带变量
---

# springboot-migration

## 适用范围

本 skill 覆盖 **Spring Boot 2.7.x → 3.x** 的迁移。Spring Boot 3.0 把 baseline 从 Java 8/11 抬到 Java 17,并把 `javax.*` 全部换成 `jakarta.*`,是一次硬性破坏性变更。

**支持的 3.x 目标版本**: 3.0 / 3.1 / 3.2 / 3.3 / 3.5 (LTS 2026)

## 工作流总览

```
[1] 现状扫描   →  [2] 版本推断   →  [3] 生成迁移计划
                                              ↓
                  [5] 执行+验证  ←  [4] 用户确认 ★
```

每一步都通过 MCP 工具完成,不直接修改用户代码——而是输出"建议清单",让用户决定。

---

## 阶段 1: 现状扫描

### 1.1 读取配置

调用 **`springboot_read_config`**:
```json
{ "project_path": "<用户的 Spring Boot 项目根目录>" }
```

记录从返回值中提取的:
- Spring Boot 版本(从 parent pom 或 dependencyManagement)
- Java 版本(`maven.compiler.source` / `<java.version>`)
- 已声明的 profiles
- 已 inferred 的 base package

如果项目根目录推断失败 → 提示用户提供更具体的 `project_path`。

### 1.2 分析依赖

调用 **`springboot_analyze_dependencies`**:
```json
{
  "template_category": "MybatisPlus-Mixed",
  "database_type": "mysql",
  "include_swagger": true,
  "include_lombok": true,
  "include_mapstruct": true,
  "project_path": "<同上>"
}
```

从返回值收集:
- 当前 spring-boot-starter-* 系列的版本
- 是否在用 springfox-swagger(2.x 路径,3.x 必须改 SpringDoc)
- 是否在用 javax.* 注解(JPA/Servlet/Validation)
- mybatis-plus / mybatis 版本
- Lombok 版本(老版本与 Java 17 有 annotation processor 问题)

---

## 阶段 2: 版本推断与目标推荐

### 2.1 推断当前版本

读取 pom.xml 的 `<parent>` 或 `dependencyManagement` 段。判定规则:
- `spring-boot-starter-parent` 版本 `2.x.x` → 源版本 2.x
- 找不到 → 询问用户

### 2.2 推荐目标版本

| 当前版本 | 推荐目标 | 理由 |
|----------|---------|------|
| 2.5.x / 2.6.x | 先升 2.7.x 再 3.x | 2.7 是 2.x 终点,差距小;直接跳 3.x 风险大 |
| 2.7.x | 3.3.x (LTS) | LTS 稳定且与 3.5 兼容 |
| 2.7.x (要求最新) | 3.5.x | 当前最新 LTS,JDK 21 兼容 |
| 3.0.x ~ 3.2.x | 3.3.x 或 3.5.x | 小版本升级,本 skill 简化处理 |

**Java 版本要求**:
- Spring Boot 3.x → **Java 17 最低**
- Spring Boot 3.2+ → Java 17/21 都可
- 若用户当前是 Java 8/11 → 必须同时升 Java

---

## 阶段 3: 生成迁移计划

按以下顺序生成 **checklist**(不要直接改代码,让用户看清楚再执行):

### 3.1 顶层版本号

```diff
-    <java.version>11</java.version>
+    <java.version>17</java.version>

-        <relativePath/>
-        <artifactId>spring-boot-starter-parent</artifactId>
-        <version>2.7.18</version>
+        <relativePath/>
+        <artifactId>spring-boot-starter-parent</artifactId>
+        <version>3.3.6</version>
```

### 3.2 javax → jakarta 包替换

**所有 `import javax.*` 都要改 `import jakarta.*`**,核心模块对应表:

| 旧 (javax) | 新 (jakarta) |
|-----------|-------------|
| `javax.persistence.*` | `jakarta.persistence.*` |
| `javax.validation.*` | `jakarta.validation.*` |
| `javax.servlet.*` | `jakarta.servlet.*` |
| `javax.annotation.*` (Resource/PostConstruct) | `jakarta.annotation.*` |
| `javax.transaction.*` | `jakarta.transaction.*` |
| `javax.mail.*` | `jakarta.mail.*` |

**例外**: `javax.sql.DataSource` / `javax.crypto.*` / `javax.net.ssl.*` 等 JDK 自带的 `javax` 子包 **不要改**——它们属于 JDK 标准库。

LLM 应该:
- 提议用户执行 `git grep "import javax\."` 收集所有受影响文件
- 排除上面"例外"清单
- 给出每个文件的逐行替换建议

### 3.3 Swagger 迁移: springfox → SpringDoc

```diff
-<dependency>
-    <groupId>io.springfox</groupId>
-    <artifactId>springfox-swagger2</artifactId>
-    <version>3.0.0</version>
-</dependency>
+<dependency>
+    <groupId>org.springdoc</groupId>
+    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
+    <version>2.6.0</version>
+</dependency>
```

注解迁移:

| 旧 (springfox/javax) | 新 (SpringDoc/jakarta) |
|----------------------|-----------------------|
| `@Api` (Controller 类) | `@Tag(name="...")` |
| `@ApiOperation` (方法) | `@Operation(summary="...")` |
| `@ApiModelProperty` (字段) | `@Schema(description="...")` |
| `@ApiParam` (参数) | `@Parameter(description="...")` |
| `@ApiResponses` | `@ApiResponses` (路径变,从 io.swagger.annotations.* → io.swagger.v3.oas.annotations.*) |

### 3.4 Spring Security 6 DSL

Spring Security 6 把 `HttpSecurity` 配置改成 **lambda DSL**:

```diff
-http.authorizeRequests()
-    .antMatchers("/api/**").authenticated()
-    .and()
-    .csrf().disable();
+http.authorizeHttpRequests(auth -> auth
+        .requestMatchers("/api/**").authenticated()
+    )
+    .csrf(csrf -> csrf.disable());
```

要点:
- `authorizeRequests` → `authorizeHttpRequests`
- `antMatchers` → `requestMatchers`
- `.and()` 链式 → lambda 配置块
- WebSecurityConfigurerAdapter → 改用 `@Bean SecurityFilterChain`

### 3.5 application.properties / yml 配置变化

常见变化:
- `spring.profiles.active` 保留,行为不变
- `server.servlet.session.cookie.same-site` 写法不变,但 default 改为 Lax
- Hibernate 6 严格模式: 之前能跑的不规范 JPQL 会报错(如缺 alias)
- HikariCP 5 移除了若干 deprecated 配置项

### 3.6 测试代码

| 旧 | 新 |
|----|----|
| `@MockBean` (org.springframework.boot.test.mock.mockito) | `@MockitoBean` (Spring Boot 3.4+) |
| `Mockito-core 4.x` | `Mockito-core 5.x` |
| `JUnit Vintage` | 删除,统一 JUnit 5 |

### 3.7 Lombok / Annotation Processor

Java 17 下若 Lombok 版本 < 1.18.30,可能在 IntelliJ / Maven 中编译失败:
```xml
<dependency>
    <groupId>org.projectlombok</groupId>
    <artifactId>lombok</artifactId>
    <version>1.18.32</version>
    <scope>provided</scope>
</dependency>
```

### 3.8 MyBatis-Plus 兼容性

如果项目用 MyBatis-Plus:
- `mybatis-plus-boot-starter` 3.5.5+ 才支持 Spring Boot 3.x
- 旧版 (3.5.0-) 必须升级,**不要保留**

---

## 阶段 4: 用户确认 ★

LLM **必须**把阶段 3 的完整 checklist 输出给用户,**等用户确认**才进阶段 5。

呈现方式:
1. 按章节分组,数量统计("发现 32 处 import javax.*")
2. 高亮高风险点(Security DSL / Hibernate 6 行为变化)
3. 询问用户:
   - 是否一次性全做,还是分步?
   - 是否要建分支 (`feature/spring-boot-3-migration`)?
   - 是否要先在 `test_project/` 上演练?

**禁止跳过此步直接改代码**。

---

## 阶段 5: 执行 + 验证

### 5.1 执行顺序(推荐)

1. 新建分支 `feature/sb-3-migration`
2. 升 parent pom + Java version → `mvn compile` 看哪里炸
3. 修 javax → jakarta(批量 sed 或 IDE Refactor → Replace in Path)
4. 修 Swagger / Security DSL / 自定义 Filter
5. 修测试代码
6. `mvn clean verify` 全套验证
7. 跑端到端集成测试

### 5.2 验证 checklist

每步完成后让用户报:
- [ ] `mvn compile` 通过
- [ ] 启动应用 `spring-boot:run` 无异常
- [ ] 单元测试 `mvn test` 通过
- [ ] 集成测试(Testcontainers 等)通过
- [ ] Actuator `/health` 返回 UP
- [ ] Swagger UI / SpringDoc UI 可访问

### 5.3 回滚预案

如果 `mvn compile` 之后发现大量奇怪错误:
- 检查是否漏改某个模块的 pom
- 检查 IDE 是否还在用 cached classpath(`mvn clean idea:idea`)
- 极端情况: `git checkout feature/sb-3-migration` 切回原状

---

## 错误处理与边界

- **多模块项目**: 各模块独立 pom,**每个模块都要改**。先升 parent BOM,再各模块同步。
- **Spring Cloud 同时升级**: 检查 `spring-cloud.version` 与 Spring Boot 3.x 的兼容矩阵 — 必须用 Spring Cloud 2022.x+
- **Liquibase / Flyway**: 升 Spring Boot 3 时,Liquibase < 4.20 或 Flyway < 9.x 可能不兼容
- **Bootstrap class 自定义启动器**: javax.* 引用要全部替换
- **Reactive 路径 (WebFlux)**: 主要 API 不变,但底层 reactor-netty 升级,注意自定义 codec

## 工具调用清单速查

```
[扫描]   springboot_read_config              (1 次)
         springboot_analyze_dependencies     (1 次)

[规划]   (LLM 推断 + 生成 checklist,不调工具)

[确认]   ★ pause,等用户回应

[执行]   springboot_analyze_dependencies     (验证用,执行后多次调用)
         springboot_validate_project         (结构是否仍合法)
         (具体改 pom/java 文件由用户在编辑器内完成或用 file_write_to_project)
```

## 设计原则

1. **不直接改代码**: 输出 diff/checklist,让用户决定 — 这是大型重构,LLM 不能独走
2. **分步可中断**: 每个章节独立可执行,中途停下也不会留下半成品
3. **风险标注**: 高风险点(Security/Hibernate)在 checklist 中明确标红
4. **演练优先**: 鼓励先在 `test_project/` 上跑通,再动主项目

## 与 java-codegen-from-db 的关系

这两个 skill **互补**:
- `java-codegen-from-db`: 从零生成新代码(Spring Boot 3.x 模板)
- `springboot-migration`: 把存量 2.x 代码迁移到 3.x

迁移完成后,用户就可以用 `java-codegen-from-db` + `sb35-java21` 模板生成新模块的代码,与已升级到 3.x 的项目一致。

## 与 iteration-plan 的对应

本 skill 实现 `iteration-plan/03-phase-details.md` 第 245-258 行 (Phase 2.5) 的工作流。验收标准: 在 `test_project/` 上跑通一次 2.7 → 3.5 演练。
