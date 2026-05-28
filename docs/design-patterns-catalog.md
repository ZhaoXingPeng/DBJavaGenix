# 设计模式 Catalog — DBJavaGenix 模板系统中的应用

> 生成器项目本身用了哪些设计模式?生成出来的 Java 代码又体现哪些?
> 这份 catalog 把"我们使用 / 我们生成"的设计模式一并列清楚,作为面试时讲述
> "我懂传统 Java 工程"的具体素材。

## 一、生成器自身使用的模式

### 1.1 Strategy 模式 — 模板分类

`src/dbjavagenix/templates/java/` 下有 4 套模板:
- `Default/` — 传统 MyBatis (XML mapper)
- `MybatisPlus/` — 纯注解 MyBatis-Plus
- `MybatisPlus-Mixed/` — 混合架构(推荐)
- `sb35-java21/` — Spring Boot 3.5 + Java 21 + jakarta.* 包

每套模板是一个 **Strategy** — 都符合相同接口(都有 entity/dao/service/controller/mapper
六个 Mustache 文件),但实现不同。

调用方(`codegen_render_*` 工具)通过 `template_category` 参数选择策略。
新增一套模板不影响其他模板,符合 OCP(开闭原则)。

### 1.2 Template Method 模式 — 代码生成流水线

```python
class CodegenPipeline:
    def generate(self, table):
        ctx = self.build_context(table)        # 1. 子类可重写,默认建上下文
        self.validate_context(ctx)              # 2. 抽象方法,模板自定义校验
        rendered = self.render(ctx)             # 3. 抽象方法,具体渲染逻辑
        return self.post_process(rendered)      # 4. 子类可重写,默认 noop
```

虽然代码里没有显式写成这个类(我们用函数式风格),但 `codegen_build_context` →
各 `codegen_render_*` 的调用顺序就是 Template Method 的展开形式。

### 1.3 Builder 模式 — 复杂上下文构建

`codegen_build_context` 接收 ~10 个参数(连接信息 + 表名 + 模板类 + 包名 + Lombok
开关 + Swagger 开关 + ...),内部一步步组装 context dict,最后返回。

这是 **Builder** 的展开形式 — 调用方通过命名参数声明意图,我们在内部组装。

### 1.4 Factory 模式 — 数据库连接

`connection_manager.py` 里 `_create_engine(host, port, ...)` 根据 DSN 前缀
(`mysql+pymysql://` / `postgresql+psycopg2://`)产出不同 SQLAlchemy 引擎。

### 1.5 Adapter 模式 — 数据类型映射

`config/data_types/mysql.yaml` / `postgresql.yaml` 等把不同数据库的类型映射到
Java 类型。每个 yaml 是一个 **Adapter**,把数据库类型适配到统一接口。

### 1.6 Command 模式 — MCP Tool 本身

每个 MCP tool 就是一个 **Command**:封装一组参数 + 一次操作 + 返回结果。
LLM/客户端是 Invoker,Server 是 Receiver。这是 MCP 协议本身的设计。

---

## 二、生成的 Java 代码中体现的模式

### 2.1 Repository 模式 — DAO 层

```java
@Mapper
public interface UserMapper extends BaseMapper<User> { ... }
```

`BaseMapper` 接口抽象了 CRUD,具体实现交给 MyBatis-Plus。这是经典的
**Repository** 模式 —— domain code 不直接接触 SQL。

### 2.2 DTO 模式 — 接口契约分离

生成的 `UserDTO.java` (`sb35-java21` 模板) 与 `User.java` 分离:
- `User` 是 ORM entity,绑表结构
- `UserDTO` 是 API 输出契约,不暴露内部字段

避免 entity 反序列化时把 password 字段泄露给前端。

### 2.3 Singleton — Spring Bean

Service / Mapper 都是 `@Service` / `@Mapper` 标注,Spring 容器管理为单例。

### 2.4 Decorator — Lombok 注解

`@Data` `@Builder` `@Slf4j` `@RequiredArgsConstructor` 等 Lombok 注解
是编译期 **Decorator**,在原类上加 getter/setter/builder/log 字段。

我们的 lombok.config 通过 ADR-007 标准化了这些 decorator 的行为
(addSuppressWarnings=false / stopBubbling=true)。

### 2.5 Template Method — Service Abstract Pattern

```java
public abstract class BaseService<T> {
    public final T save(T entity) {
        beforeSave(entity);                // hook
        T saved = doSave(entity);          // abstract
        afterSave(saved);                  // hook
        return saved;
    }
    protected abstract T doSave(T entity);
    protected void beforeSave(T entity) {}
    protected void afterSave(T entity) {}
}
```

我们的 `service.mustache` 模板生成的就是这种 Template Method 骨架。
子类只需要实现 `doSave`,通用流程(校验 / 审计日志 / 事件发布)在 base
里固定。

### 2.6 Iterator — JPA / MyBatis-Plus 分页

`Page<User> page = userMapper.selectPage(new Page<>(1, 10), wrapper);`
本质是封装了 **Iterator** + cursor state。

### 2.7 Specification 模式 — MyBatis-Plus Wrapper

`new LambdaQueryWrapper<User>().eq(User::getStatus, 1).like(User::getName, "Joe")`
是 **Specification** 模式的链式构建,用 lambda 引用表达谓词。

---

## 三、模式之外的"原则"

我们的 ADR 体系本身也是工程原则的体现:

| ADR | 对应原则 |
|-----|---------|
| ADR-001 三层架构 | 关注点分离 (SoC) |
| ADR-002 原子工具 | 单一职责 (SRP) |
| ADR-003 渐进发现 | 最小惊讶 / 性能优先 |
| ADR-004 规则优先 LLM 可选 | 优雅降级 |
| ADR-005 不引依赖 | YAGNI |
| ADR-006 schema 算法 | DRY (复用算法不引大库) |
| ADR-007 标准配置生成 | 开箱即用 (Convention over Configuration) |

---

## 四、何时讲这份 catalog

- 面试时被问"你用过哪些设计模式" — 用具体的项目代码举例
- 代码 review 时引用模式名 — 让讨论更精炼
- 新人 onboarding — 一份地图

不是为了讲模式而讲。模式是 **post-hoc 的描述工具**,不是 prescriptive 的指导工具。
