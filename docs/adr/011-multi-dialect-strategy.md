# ADR-011: 多方言策略 — DialectAdapter 而非 single-dispatch

**状态**: Accepted (v0.3 落地, 2026-06)
**关联**: `src/dbjavagenix/database/dialect.py`
**前置**: ADR-001 (三层架构)

## 背景

v0.1 ~ v0.2.2 期间,SQL → Java 类型映射散落在 `generator/template_context.py`
里,代码形如:

```python
def _map_java_type(self, db_type: str) -> str:
    type_mapping = {
        "TINYINT": "Byte",
        "INT": "Integer",
        "BIGINT": "Long",
        ...
    }
    base = re.sub(r"\([^)]*\)", "", db_type.upper())
    return type_mapping.get(base, "String")
```

只对 MySQL 设计。当 v0.3 要加 PostgreSQL 时,差异点很多:

| 维度 | MySQL | PostgreSQL |
|------|-------|-----------|
| 整数族 | TINYINT / SMALLINT / MEDIUMINT / INT / BIGINT | INT2/4/8 + SMALLINT/INTEGER/BIGINT |
| 自增 | AUTO_INCREMENT 修饰 | SERIAL / BIGSERIAL 类型 |
| 布尔 | TINYINT(1) 模拟 | 原生 BOOLEAN |
| 二进制 | BLOB 家族 | BYTEA |
| 时区 | DATETIME / TIMESTAMP 都无时区 | TIMESTAMPTZ → OffsetDateTime |
| JSON | JSON (只一种) | JSON + JSONB (两种) |
| UUID | 无,CHAR(36) | 原生 UUID 类型 |

把这些差异塞回 `_map_java_type()` 会让函数膨胀 + 难维护。

## 决定

把方言策略抽成独立模块 `src/dbjavagenix/database/dialect.py`:

```python
class DialectAdapter(ABC):
    name: str
    @property
    @abstractmethod
    def type_to_java(self) -> dict[str, str]: ...
    @property
    @abstractmethod
    def type_to_jdbc(self) -> dict[str, str]: ...

    def java_type_for(self, db_type: str) -> str: ...  # 公共算法
    def jdbc_type_for(self, db_type: str) -> str: ...
    def is_string_type(self, db_type: str) -> bool: ...
    def is_date_type(self, db_type: str) -> bool: ...
    def is_decimal_type(self, db_type: str) -> bool: ...

class MySQLDialect(DialectAdapter): ...
class PostgreSQLDialect(DialectAdapter): ...

_REGISTRY = {"mysql": MySQLDialect(), "postgresql": PostgreSQLDialect()}
def get_dialect(db_type: str) -> DialectAdapter: ...
```

要点:
1. **每个方言一个类,各自定义映射表** — 类型查询/字符串分类等共用逻辑在基类
2. **registry + factory function** 而非 if/elif 链 — Oracle/SQLServer 加进来时
   新增一行 dict + 一个子类
3. **未识别方言退回 MySQL** — 向后兼容承诺,老调用方传 None / "" 不会崩
4. **不直接绑定 `DatabaseType` enum** — 接受字符串,降低耦合

## 替代方案

### A. `functools.singledispatch` 按类型分发

```python
@singledispatch
def java_type_for(dialect, db_type): ...

@java_type_for.register(MySQLConfig)
def _(dialect, db_type): ...
```

**否决**:
- 我们的方言不是按 *Python 类型* 分,而是按字符串 ("mysql" / "postgresql")
- single-dispatch 需要给每个方言定义一个 marker class,反而多一层抽象
- IDE 跳转体验差(看到 `java_type_for(d, ...)` 不知道实际调到哪个 impl)

### B. 不抽象,只在 `_map_java_type` 里 if db_type==...

```python
def _map_java_type(self, db_type: str, dialect: str = "mysql") -> str:
    if dialect == "mysql":
        return MYSQL_MAP.get(...)
    elif dialect == "postgresql":
        return PG_MAP.get(...)
    ...
```

**否决**:
- 每个差异点都要 if 一遍 (string_type, date_type, jdbc_type, java_type)
- 加第三个方言时,所有函数都要改
- 测试不好写,要 parametrize 所有函数 × 所有 dialect

### C. 用 SQLAlchemy 的 type 系统

SQLAlchemy 本身有完整的 dialect → Python type 映射 (`mysql.dialect()`,
`postgresql.dialect()` 各自的 `ischema_names`)。

**否决**:
- 我们要 Java 类型,SQLAlchemy 给 Python 类型
- SQLAlchemy type 名 (`Integer`, `BigInteger`) 和 Java 类型 (`Integer`, `Long`)
  正好不一致,二次映射反而麻烦
- 引入 SQLAlchemy 已经在 deps 里,但用它做 dialect 抽象会绑得太深 — ADR-005
  "不引入不必要抽象" 也反对

### D. 配置驱动 (YAML/JSON 类型映射表)

```yaml
mysql:
  TINYINT: Byte
  ...
postgresql:
  INT2: Short
  ...
```

**否决**:
- 短期看更"灵活",但长期是反模式 — 类型映射逻辑跟代码版本绑死,放代码里更安全
- 用户基本不会改这表(改了等于改代码生成行为)
- 失去 IDE 类型检查 + 跳转

## 后果

**好**:
- 加新方言 (Oracle / SQLServer) 只动 1 个文件 + 1 行 registry
- 36 个 unit test 覆盖 mysql/postgres 两套映射,跨方言隔离测试防串
- D3 用真实 PG container 验证 information_schema 上报的字符串确实命中
  我们的 key (这是配置驱动方案做不到的)
- `template_context.py` 之后会渐进迁移到调用 `get_dialect(...).java_type_for()`,
  本 ADR 不强制一次性切换

**坏**:
- `dialect.py` 文件略大 (~300 行,主要是两张映射表),但都是数据
- `template_context.py` 现在有重复的 MySQL 映射,**v0.3.1 计划重构** — 不在这个
  ADR 范围内,先把 PG 跑起来,old code 保留向后兼容

**实测**:
- D3 PG 16 实测 23 个 PG 类型全部命中预期 Java 类型
- D2 36 个 unit test 全绿,dialect.py 100% line coverage

## 叙事意义

"代码生成器多方言支持" 是 v0.1 立项时就吹的目标,但 v0.1 ~ v0.2.2 实际只能用 MySQL。
v0.3 才真正落地 PostgreSQL,核心动作就是这个 ADR — 把方言策略从模板里剥出来,
让后续扩展从"重写代码"变成"加一个类"。

更深的含义:**"加一个 if 分支"看起来比"做一层抽象"省事,但 N 次 if 累积成本超过
抽象**。这是 Effective Java + Refactoring 的 OCP (开闭原则) 在真实项目里的体现。
