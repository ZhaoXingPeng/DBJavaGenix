你好！我需要测试DBJavaGenix MCP服务的Default模板功能，请按以下步骤进行：

## 🔍 第一步：验证MCP工具可用性
首先，请列出所有可用的MCP工具，确认DBJavaGenix服务已正确连接。

## 🌐 第二步：数据库连接测试
请帮我连接到测试数据库，参数如下：
- 主机: 115.190.155.106
- 端口: 3309
- 用户名: root
- 密码: .Dd5779496
- 数据库: test1
- 数据库类型: mysql

## 📊 第三步：分析数据库表结构
连接成功后，请分析test1数据库中的所有表结构，并为每张表生成Default模板的Java代码。

## 📦 第四步：依赖检查与分析
请检查当前项目（使用Default模板）的依赖状况，分析是否存在缺失或过时的依赖，并提供修复建议。

## 📝 第五步：生成代码和依赖报告
请生成以下内容：
1. 所有表的Default模板Java代码（Entity、DAO、Service、ServiceImpl、Controller）
2. 依赖分析报告，包括缺失依赖列表和版本建议

你好！我需要测试DBJavaGenix MCP服务的MyBatisPlus模板功能，请按以下步骤进行：

## 🔍 第一步：验证MCP工具可用性
首先，请列出所有可用的MCP工具，确认DBJavaGenix服务已正确连接。

## 🌐 第二步：数据库连接测试
请帮我连接到测试数据库，参数如下：
- 主机: 115.190.155.106
- 端口: 3309
- 用户名: root
- 密码: .Dd5779496
- 数据库: test1
- 数据库类型: mysql

## 📊 第三步：分析数据库表结构
连接成功后，请分析test1数据库中的所有表结构，并为每张表生成MyBatisPlus模板的Java代码。

## 📦 第四步：依赖检查与分析
请检查当前项目（使用MyBatisPlus模板）的依赖状况，分析是否存在缺失或过时的依赖，并提供修复建议。

## 📝 第五步：生成代码和依赖报告
请生成以下内容：
1. 所有表的MyBatisPlus模板Java代码（Entity、DAO、Service、ServiceImpl、Controller）
2. 依赖分析报告，包括缺失依赖列表和版本建议

你好！我需要测试DBJavaGenix MCP服务的MyBatisPlus-Mixed模板功能，请按以下步骤进行：

## 🔍 第一步：验证MCP工具可用性
首先，请列出所有可用的MCP工具，确认DBJavaGenix服务已正确连接。

## 🌐 第二步：数据库连接测试
请帮我连接到测试数据库，参数如下：
- 主机: 115.190.155.106
- 端口: 3309
- 用户名: root
- 密码: .Dd5779496
- 数据库: test1
- 数据库类型: mysql

## 📊 第三步：分析数据库表结构
连接成功后，请分析test1数据库中的所有表结构，并为每张表生成MyBatisPlus-Mixed模板的Java代码。

## 📦 第四步：依赖检查与分析
请检查当前项目（使用MyBatisPlus-Mixed模板）的依赖状况，分析是否存在缺失或过时的依赖，并提供修复建议。

## 📝 第五步：生成代码和依赖报告
请生成以下内容：
1. 所有表的MyBatisPlus-Mixed模板Java代码（Entity、DAO、Service、ServiceImpl、Controller）
2. 依赖分析报告，包括缺失依赖列表和版本建议
3. 依赖迁移指南（如果存在过时依赖需要迁移到新版本）


Default 模板

你好！我需要测试 DBJavaGenix MCP 服务的 Default 模板功能，请按以下步骤进行：
第一步：验证 MCP 工具可用性
请调用 list_tools，确认 DBJavaGenix 服务已正确连接。
第二步：建立数据库连接
调用工具 db_connect_test，参数：
{"host":"localhost","port":3306,"username":"root","password":".Dd5779496","database":"test1","database_type":"mysql","charset":"utf8mb4"}
记录返回的 connection_id 供后续使用。
第三步：验证数据库与表
调用 db_query_databases：{"connection_id":"<connection_id>"} 确认库列表包含 test1。
调用 db_query_tables：{"connection_id":"<connection_id>","database":"test1"}，确认存在待测表（如无指定表，请选择任意一张，如 sys_user）。
第四步：代码生成前分析（可读预览）
调用 db_codegen_analyze：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"Default","author":"ZXP","package_name":"com.zxp.test"}
第五步：执行生成写入文件
调用 db_codegen_generate：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"Default","author":"ZXP","package_name":"com.zxp.test","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第六步：项目校验与依赖检查
调用 springboot_validate_project：
{"template_category":"Default","check_dependencies":true,"create_missing_dirs":true}
调用 springboot_analyze_dependencies：
{"template_category":"Default","database_type":"mysql","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第七步：结果确认
输出生成文件清单（Java 与 XML 的实际路径），并简要说明依赖健康分与修复建议。
MyBatis‑Plus 模板

你好！我需要测试 DBJavaGenix MCP 服务的 MybatisPlus 模板功能，请按以下步骤进行：
第一步：验证 MCP 工具可用性
请调用 list_tools。
第二步：建立数据库连接
调用 db_connect_test：
{"host":"localhost","port":3306,"username":"root","password":".Dd5779496","database":"test1","database_type":"mysql","charset":"utf8mb4"}
记录 connection_id。
第三步：验证数据库与表
db_query_databases：{"connection_id":"<connection_id>"}；
db_query_tables：{"connection_id":"<connection_id>","database":"test1"}，选择一张表（如 sys_user）。
第四步：代码生成前分析（可读预览）
db_codegen_analyze：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"MybatisPlus","author":"ZXP","package_name":"com.zxp.test"}
第五步：执行生成写入文件
db_codegen_generate：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"MybatisPlus","author":"ZXP","package_name":"com.zxp.test","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第六步：项目校验与依赖检查
springboot_validate_project：
{"template_category":"MybatisPlus","check_dependencies":true,"create_missing_dirs":true}
springboot_analyze_dependencies：
{"template_category":"MybatisPlus","database_type":"mysql","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第七步：结果确认
输出生成文件清单，并确认 Controller/Entity 是否根据工程技术栈使用了正确的注解导入（Jakarta/Javax、Springdoc/Swagger2）。
MyBatis‑Plus‑Mixed 模板

你好！我需要测试 DBJavaGenix MCP 服务的 MybatisPlus‑Mixed 模板功能，请按以下步骤进行：
第一步：验证 MCP 工具可用性
请调用 list_tools。
第二步：建立数据库连接
调用 db_connect_test：
{"host":"localhost","port":3306,"username":"root","password":".Dd5779496","database":"test1","database_type":"mysql","charset":"utf8mb4"}
记录 connection_id。
第三步：验证数据库与表
db_query_databases：{"connection_id":"<connection_id>"}；
db_query_tables：{"connection_id":"<connection_id>","database":"test1"}，选择一张表。
第四步：代码生成前分析（可读预览）
db_codegen_analyze：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"MybatisPlus-Mixed","author":"ZXP","package_name":"com.zxp.test"}
第五步：执行生成写入文件
db_codegen_generate：
{"connection_id":"<connection_id>","table_name":"<表名>","database":"test1","template_category":"MybatisPlus-Mixed","author":"ZXP","package_name":"com.zxp.test","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第六步：项目校验与依赖检查
springboot_validate_project：
{"template_category":"MybatisPlus-Mixed","check_dependencies":true,"create_missing_dirs":true}
springboot_analyze_dependencies：
{"template_category":"MybatisPlus-Mixed","database_type":"mysql","include_swagger":true,"include_lombok":true,"include_mapstruct":false,"project_path":"C:\project\ai\task\coder_prompt\DBJavaGenix\test_project"}
第七步：结果确认
输出生成文件清单（包含 XML Mapper），并确认依赖健康报告与技术栈（Jakarta/Javax、Springdoc/Swagger2）一致性。


