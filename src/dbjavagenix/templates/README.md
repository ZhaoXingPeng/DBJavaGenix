# DBJavaGenix 模板分类说明

## 模板分类

### 1. Default 分类
- **用途**: 传统的 MyBatis 开发模式
- **特点**: 
  - 使用原生 MyBatis
  - 手写 SQL 映射
  - 完整的 CRUD 操作
  - 支持分页查询
  - 集成 MapStruct + Lombok 优化
  - 可选择启用 Swagger 注解

#### 包含文件：
- `entity.mustache` - 实体类模板（支持 Lombok + 可选 Swagger）
- `dao.mustache` - DAO 接口模板（MyBatis 标准接口）
- `service.mustache` - Service 接口模板
- `serviceImpl.mustache` - Service 实现类模板
- `controller.mustache` - Controller 模板（RESTful API + 可选 Swagger）
- `mapper.xml.mustache` - MyBatis XML 映射文件模板

### 2. MybatisPlus 分类
- **用途**: MyBatis-Plus 纯注解开发模式
- **特点**:
  - 继承 MyBatis-Plus BaseMapper
  - 无需手写基础 CRUD SQL
  - 使用 ActiveRecord 模式
  - 集成 MapStruct + Lombok 优化
  - 可选择启用 Swagger 注解

#### 包含文件：
- `entity.mustache` - 实体类模板（继承 Model + 支持 Lombok + 可选 Swagger）
- `dao.mustache` - DAO 接口模板（继承 BaseMapper）
- `service.mustache` - Service 接口模板（继承 IService）
- `serviceImpl.mustache` - Service 实现类模板（继承 ServiceImpl）
- `controller.mustache` - Controller 模板（继承 ApiController + 可选 Swagger）

### 3. MybatisPlus-Mixed 分类
- **用途**: MyBatis-Plus 混合开发模式
- **特点**:
  - 继承 MyBatis-Plus BaseMapper
  - 基础操作使用 MyBatis-Plus
  - 复杂操作手写 XML SQL
  - 支持批量操作
  - 集成 MapStruct + Lombok 优化
  - 可选择启用 Swagger 注解

#### 包含文件：
- `entity.mustache` - 实体类模板（继承 Model + 支持 Lombok + 可选 Swagger）
- `dao.mustache` - DAO 接口模板（继承 BaseMapper + 自定义批量方法）
- `service.mustache` - Service 接口模板（继承 IService + 批量操作）
- `serviceImpl.mustache` - Service 实现类模板（继承 ServiceImpl + 批量操作实现）
- `controller.mustache` - Controller 模板（继承 ApiController + 批量 API + 可选 Swagger）
- `mapper.mustache` - MyBatis XML 映射文件模板（批量操作 SQL）

## 配置选项

### Swagger 注解控制
所有模板均支持 Swagger 注解的开关控制：

```yaml
# 启用 Swagger 注解（生成 API 文档）
useSwagger: true

# 禁用 Swagger 注解（纯净代码）
useSwagger: false  # 默认值
```

**启用 Swagger 时**，生成的代码包含：
- `@Api(tags = "用户管理")` - Controller 类注解
- `@ApiOperation("查询用户")` - 方法注解  
- `@ApiParam("用户ID")` - 参数注解
- `@ApiModel(description = "用户")` - 实体类注解
- `@ApiModelProperty(value = "姓名")` - 字段注解

**禁用 Swagger 时**，生成纯净的 Spring Boot 代码，无任何 Swagger 相关内容。

### Lombok 注解控制
```yaml
# 启用 Lombok 注解（减少样板代码）
useLombok: true

# 禁用 Lombok 注解（手动 getter/setter）  
useLombok: false
```

## 技术栈集成

### Lombok 注解优化
- `@Data` - 自动生成 getter/setter/toString/equals/hashCode
- `@EqualsAndHashCode(callSuper = false)` - 排除父类字段的 equals/hashCode
- `@Accessors(chain = true)` - 支持链式调用（MyBatis-Plus）
- `@NoArgsConstructor` + `@AllArgsConstructor` - 构造函数（Default）

### MapStruct 映射（预留接口）
- Entity ↔ DTO 双向转换
- Entity → VO 单向转换
- 批量列表转换
- 更新实体（忽略空值）

### Spring Boot 集成
- `@RestController` - RESTful API 控制器
- `@RequestMapping` - 路径映射
- `@Valid` - 参数校验
- `@Transactional` - 事务管理（Service 层）

## 模板变量说明

### 基础变量
- `{{className}}` - 实体类名（PascalCase）
- `{{entityNameLowerCase}}` - 实体类名（camelCase）
- `{{comment}}` - 表注释
- `{{tableName}}` - 数据库表名
- `{{package}}` - 包名
- `{{author}}` - 作者
- `{{date}}` - 生成日期

### 字段变量
- `{{columns}}` - 字段列表
- `{{columns.javaName}}` - Java 字段名
- `{{columns.javaType}}` - Java 类型
- `{{columns.comment}}` - 字段注释
- `{{columns.name}}` - 数据库字段名
- `{{columns.jdbcType}}` - JDBC 类型
- `{{columns.nullable}}` - 是否可空

### 主键变量
- `{{primaryKeyName}}` - 主键字段名（Java）
- `{{primaryKeyType}}` - 主键 Java 类型
- `{{primaryKeyColumn}}` - 主键数据库字段名
- `{{capitalizedPrimaryKeyName}}` - 主键字段名（首字母大写）

### 其他字段集合
- `{{otherColumns}}` - 非主键字段列表
- `{{imports}}` - 需要导入的类列表

### 条件变量
- `{{useSwagger}}` - 是否启用 Swagger 注解
- `{{useLombok}}` - 是否启用 Lombok 注解
- `{{generateDto}}` - 是否生成 DTO（预留）
- `{{generateVo}}` - 是否生成 VO（预留）
- `{{generateMappers}}` - 是否使用 MapStruct（预留）

## 使用建议

### 选择模板分类的原则：

1. **Default 分类**：
   - 项目需要完全控制 SQL
   - 复杂的多表关联查询
   - 性能要求极高的场景
   - 需要使用存储过程
   - 传统企业级项目

2. **MybatisPlus 分类**：
   - 快速开发原型
   - 简单的单表操作为主
   - 团队对 MyBatis-Plus 熟悉
   - 减少样板代码
   - 敏捷开发项目

3. **MybatisPlus-Mixed 分类**：
   - 平衡开发效率和灵活性
   - 基础操作使用 MyBatis-Plus
   - 复杂操作手写 SQL
   - 需要批量操作
   - **推荐用于大多数企业项目**

### 配置建议

#### 开发阶段推荐配置：
```yaml
useSwagger: true   # 启用 API 文档
useLombok: true    # 减少样板代码
```

#### 生产环境推荐配置：
```yaml
useSwagger: false  # 禁用 API 文档（安全考虑）
useLombok: true    # 保持代码简洁
```

### MapStruct + Lombok 优化优势：
- 减少 80% 的样板代码
- 编译时生成映射代码，性能优秀
- 类型安全的对象转换
- 支持复杂的映射规则
- 与 IDE 完美集成，支持重构

## 版本说明

当前版本基于 EasyCode 模板迁移和优化：
- ✅ 从 Velocity 模板引擎迁移到 Mustache
- ✅ 集成现代化 Java 开发最佳实践
- ✅ 支持 Swagger 注解可选配置
- ✅ 支持 Lombok 代码简化
- ✅ 预留 MapStruct 对象映射接口
- ✅ 统一模板变量命名规范