### MyBatis 与 MyBatis-Plus 在 Spring Boot 中的版本演化及相关工具

- **MyBatis 和 MyBatis-Plus 概述**：MyBatis 是一个轻量级持久层框架，支持灵活的 SQL 编写；MyBatis-Plus 是其增强版，提供通用 CRUD、代码生成器等功能，简化开发。两者在 Spring Boot 中的版本需与 Spring Boot 版本保持兼容，以避免配置错误（如 `sqlSessionFactory` 未找到）。
- **最新版本（2025年9月）**：
  - MyBatis：3.5.16，推荐与 Spring Boot 3.x 搭配使用，支持 Java 17 和 Jakarta EE。
  - MyBatis-Plus：3.5.7，适配 Spring Boot 3.x，优化了性能和代码生成。
  - MySQL Connector/J：8.4.0，推荐用于 Spring Boot 3.x 项目，支持最新的 MySQL 8.x 特性。
- **常用版本**：
  - Spring Boot 2.7.x：MyBatis 3.4.x/3.5.x，MyBatis-Plus 3.4.x/3.5.2，MySQL Connector/J 8.0.x。
  - Spring Boot 3.4.x/3.5.x：MyBatis 3.5.x，MyBatis-Plus 3.5.3+，MySQL Connector/J 8.3.x/8.4.x。
- **主要变化**：
  - MyBatis：从 3.4.x 到 3.5.x，增强了对 Java 17 和模块化系统的支持，优化了性能和配置。
  - MyBatis-Plus：3.5.x 引入了对 Jakarta EE 的适配，新增 Lambda 增强、分页插件改进。
  - MySQL Connector/J：8.x 系列支持 MySQL 8.0+，改进了时区处理和性能。
- **迁移建议**：Spring Boot 3.x 项目需使用 MyBatis-Plus 3.5.3+，并确保 MySQL Connector/J 版本为 8.3.0 或更高，以兼容 Jakarta EE 和 Java 17。

#### 依赖配置示例
以下为 Spring Boot 3.5.x 环境的推荐 Maven 依赖：

| 工具 | 依赖 | 版本 | 说明 |
|------|------|------|------|
| MyBatis | `org.mybatis:mybatis` | 3.5.16 | 核心持久层框架，推荐与 Spring Boot 3.x 搭配。 |[](https://blog.csdn.net/qq_46263813/article/details/146404932)
| MyBatis-Plus | `com.baomidou:mybatis-plus-boot-starter` | 3.5.7 | 增强版，包含 MyBatis，提供便捷 CRUD 和分页。 |[](https://blog.csdn.net/longyongyyds/article/details/143836152)
| MySQL Connector/J | `com.mysql:mysql-connector-j` | 8.4.0 | MySQL 数据库驱动，支持 MySQL 8.x。 |[](https://springdoc.cn/spring-boot-and-mybatis-plus/)
| Spring Boot Web | `org.springframework.boot:spring-boot-starter-web` | 3.5.5 | 提供 RESTful API 支持，内置 Tomcat 10.1.x。 |[](https://blog.csdn.net/qq_46263813/article/details/146404932)

#### 配置注意事项
- 在 `application.yml` 中配置数据源和 MyBatis-Plus：
  ```yaml
  spring:
    datasource:
      driver-class-name: com.mysql.cj.jdbc.Driver
      url: jdbc:mysql://localhost:3306/your_db?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai
      username: your_username
      password: your_password
  mybatis-plus:
    mapper-locations: classpath:/mapper/*.xml
    type-aliases-package: com.example.entity
    configuration:
      map-underscore-to-camel-case: true
  ```
- 确保使用 `@MapperScan` 注解指定 Mapper 路径，避免手动配置 `sqlSessionFactory`。

---

### 详细分析

MyBatis 和 MyBatis-Plus 是 Java 生态中流行的持久层框架，广泛用于 Spring Boot 项目中。MyBatis 提供灵活的 SQL 映射，而 MyBatis-Plus 扩展了通用 CRUD、分页插件和代码生成器，显著提升开发效率。以下从版本演化、Spring Boot 集成、相关工具（如 MySQL Connector/J）版本匹配、历史背景和最佳实践等方面进行全面分析，基于 2025 年 9 月的最新信息，引用官方文档和社区资源，确保准确性。

#### MyBatis 版本演化
MyBatis 是一个开源的持久层框架，最初发布于 2010 年，其版本演化与 Spring Boot 和 Java 的发展密切相关。以下是关键版本和变化：

| 版本 | 发布日期 | 主要变化 | Spring Boot 兼容性 |
|------|----------|----------|--------------------|
| 3.4.x | 2016-2020 | 支持 Java 8，优化动态 SQL 和缓存，引入注解驱动的 Mapper 配置。 | Spring Boot 2.x（2.0.x - 2.7.x） |
| 3.5.x | 2020-2025 | 支持 Java 17，适配模块化系统（JPMS），改进性能和日志，兼容 Jakarta EE。最新版本 3.5.16（2025年7月）。 | Spring Boot 3.x（3.0.x - 3.5.x） |

- **3.4.x**：为 Spring Boot 2.x 提供了稳定支持，广泛用于 Java 8 项目，依赖 `javax.*` 包。
- **3.5.x**：适配 Spring Boot 3.x，解决 `javax.*` 到 `jakarta.*` 的迁移问题，支持新特性如 Record 类和虚拟线程。社区推荐升级到 3.5.16 以获取最新修复。[](https://blog.csdn.net/qq_46263813/article/details/146404932)

#### MyBatis-Plus 版本演化
MyBatis-Plus（简称 MP）是 MyBatis 的增强版，2016 年由 Baomidou 团队推出，提供通用 Mapper、Service 和代码生成器。以下为其版本演化：

| 版本 | 发布日期 | 主要变化 | Spring Boot 兼容性 |
|------|----------|----------|--------------------|
| 3.4.x | 2020-2022 | 优化 LambdaQueryWrapper，增强分页插件，支持 Java 8 和 Spring Boot 2.x 的 `javax.*` 生态。 | Spring Boot 2.x（2.5.x - 2.7.x） |
| 3.5.x | 2022-2025 | 支持 Java 17 和 Jakarta EE，改进代码生成器和分页拦截器，优化性能。最新版本 3.5.7（2025年3月）。 | Spring Boot 3.x（3.0.x - 3.5.x） |

- **3.4.x**：适合 Spring Boot 2.7.x，提供稳定的企业级支持，推荐版本如 3.4.3.1。[](https://blog.csdn.net/m0_56353506/article/details/142777714)[](https://www.wanmait.com/note/qingsoft/javaee/6dc9f7d2d6cf479e83d8ac8b3a68dcee.html)
- **3.5.x**：适配 Spring Boot 3.x，强制要求 MyBatis 3.5.x，确保与 Jakarta EE 和 Java 17 兼容。推荐 3.5.7 以支持最新特性，如增强的 `MybatisPlusInterceptor`。[](https://blog.csdn.net/longyongyyds/article/details/143836152)[](https://developer.aliyun.com/article/1201668)

#### MySQL Connector/J 版本演化
MySQL Connector/J 是 MySQL 数据库的官方 JDBC 驱动，与 Spring Boot 和 MyBatis/MyBatis-Plus 配合使用。以下为其关键版本：

| 版本 | 发布日期 | 主要变化 | Spring Boot 兼容性 |
|------|----------|----------|--------------------|
| 8.0.x | 2018-2023 | 支持 MySQL 8.0，改进时区处理、JSON 数据类型和安全性。 | Spring Boot 2.x（2.5.x - 2.7.x） |
| 8.3.x - 8.4.x | 2023-2025 | 优化性能，支持 MySQL 8.1+，兼容 Java 17 和 Jakarta EE。最新版本 8.4.0（2025年4月）。 | Spring Boot 3.x（3.0.x - 3.5.x） |

- **8.0.x**：广泛用于 Spring Boot 2.x 项目，推荐 8.0.33 以获取安全补丁。[](https://springdoc.cn/spring-boot-and-mybatis-plus/)
- **8.3.x/8.4.x**：适配 Spring Boot 3.x，支持新数据库特性和高性能连接池。推荐 8.4.0 以确保兼容性。[](https://blog.csdn.net/longyongyyds/article/details/143836152)

#### Spring Boot 集成与版本对应关系
Spring Boot 通过 `spring-boot-starter` 机制简化依赖管理，`mybatis-spring-boot-starter` 和 `mybatis-plus-boot-starter` 是集成 MyBatis 和 MyBatis-Plus 的首选方式。以下为版本对应关系：

| Spring Boot 版本 | MyBatis 版本 | MyBatis-Plus 版本 | MySQL Connector/J 版本 | 备注 |
|------------------|--------------|------------------|------------------------|------|
| 2.7.x | 3.4.x - 3.5.x | 3.4.x - 3.5.2 | 8.0.x | 稳定组合，适合 Java 8 项目。 |[](https://blog.csdn.net/m0_56353506/article/details/142777714)[](https://www.wanmait.com/note/qingsoft/javaee/6dc9f7d2d6cf479e83d8ac8b3a68dcee.html)
| 3.0.x - 3.5.x | 3.5.x | 3.5.3+ | 8.3.x - 8.4.x | 适配 Java 17 和 Jakarta EE，推荐新项目。 |[](https://blog.csdn.net/qq_46263813/article/details/146404932)[](https://blog.csdn.net/longyongyyds/article/details/143836152)

- **Spring Boot 2.7.x**：最后支持 Java 8，推荐 MyBatis 3.5.2 和 MyBatis-Plus 3.5.2，搭配 MySQL Connector/J 8.0.33。支持结束时间为 2025 年初，建议升级。[](https://developer.aliyun.com/article/1583296)[](https://www.wanmait.com/note/qingsoft/javaee/6dc9f7d2d6cf479e83d8ac8b3a68dcee.html)
- **Spring Boot 3.5.x**：要求 Java 17，推荐 MyBatis 3.5.16、MyBatis-Plus 3.5.7 和 MySQL Connector/J 8.4.0，以确保兼容性和性能。[](https://blog.csdn.net/longyongyyds/article/details/143836152)
