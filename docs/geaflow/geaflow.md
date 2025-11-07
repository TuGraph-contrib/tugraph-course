# Apache GeaFlow 流图计算引擎

> Apache GeaFlow 是蚂蚁集团开源的性能世界一流的 OLAP 图数据库，支持万亿级图存储、图表混合处理、实时图计算、交互式图分析等核心能力。

**项目地址**：[https://github.com/apache/geaflow](https://github.com/apache/geaflow)

## 产品简介

### GeaFlow 起源

早期的大数据分析主要以离线处理为主，以 Hadoop 为代表的技术栈很好地解决了大规模数据的分析问题。然而数据处理的时效性不足，很难满足高实时需求的场景。

以 Storm 为代表的流式计算引擎的出现很好地解决了数据实时处理的问题，提高了数据处理的时效性。然而，Storm 本身不提供状态管理的能力，对于聚合等有状态的计算显得无能为力。

Flink 的出现很好地弥补了这一短板，通过引入状态管理以及 Checkpoint 机制，实现了高效的有状态流计算能力。

**面临的挑战**

随着数据实时处理场景的丰富，尤其是在实时数仓场景下，实时关系运算（即 Stream Join）越来越多地成为数据实时化的难点。

Flink 虽然具备优秀的状态管理能力和出色的性能，然而在处理 Join 运算，尤其是 3 度以上 Join 时，性能瓶颈越来越明显。由于需要在 Join 两端存放各个输入的数据状态，当 Join 变多时，状态的数据量急剧扩大，性能也变得难以接受。

产生这个问题的本质原因是 Flink 等流计算系统以**表**作为数据模型，而表模型本身是一个二维结构，不包含关系的定义和关系的存储，在处理关系运算时只能通过 Join 运算方式实现，成本很高。

**GeaFlow 的解决方案**

在蚂蚁的大数据应用场景中，尤其是金融风控、实时数仓等场景下，存在大量 Join 运算，如何提高 Join 的时效性和性能成为我们面临的重要挑战，为此我们引入了**图模型**。

图模型是一种以点边结构描述实体关系的数据模型，在图模型里面：

- **点**代表实体
- **边**代表关系
- 数据存储层面点边存放在一起

因此，图模型天然定义了数据的关系，同时存储层面物化了点边关系。基于图模型，我们实现了新一代实时计算引擎 GeaFlow，很好地解决了复杂关系运算实时化的问题。

目前 GeaFlow 已广泛应用于**数仓加速**、**金融风控**、**知识图谱**以及**社交网络**等场景。

### 性能优势

相比传统的流式计算引擎如 Flink、Storm 这些以表为模型的实时处理系统，GeaFlow 以图为数据模型，在处理 Join 关系运算，尤其是复杂多跳的关系运算（如 3 跳以上的 Join、复杂环路查找）上具备极大的性能优势。

GeaFlow 在 [LDBC SNB-BI 基准测试](https://ldbcouncil.org/benchmarks/snb-bi/)中取得了世界一流的性能表现。

## 技术架构

GeaFlow 整体架构自下而上包括以下几层：

### 1. DSL 层（语言层）

GeaFlow 设计了 **SQL+GQL** 的融合分析语言，支持对表模型和图模型统一处理。

**DSL 架构特点**：

- 典型的编译器技术架构：语法分析 → 语义分析 → 中间代码生成(IR) → 代码优化 → 目标代码生成
- 通过扩展 [Apache Calcite](https://calcite.apache.org/) 实现 SQL+GQL 的语法解析器
- 实现了大量优化规则（RBO），未来也会引入 CBO
- 提供丰富的内置系统函数，支持自定义函数
- 支持自定义 Connector 插件，对接不同数据源

**两级 DAG 物理执行计划**：

- **外层 DAG**：包含表处理算子和图处理迭代算子，是物理执行逻辑的主体
- **内层 DAG**：将图计算逻辑通过 DAG 方式展开，代表图迭代计算的具体执行方式

### 2. Framework 层（框架层）

GeaFlow 设计了面向 Graph 和 Stream 的两套 API，支持流、批、图融合计算，并实现了基于 Cycle 的统一分布式调度模型。

### 3. State 层（存储层）

GeaFlow 设计了面向 Graph 和 KV 的两套 API，支持表数据和图数据的混合存储：

- 整体采用 Sharing Nothing 的设计
- 支持将数据持久化到远程存储
- 支持多种存储后端（如 RocksDB）

### 4. Console 平台

GeaFlow 提供了一站式图研发平台，实现了：

- 图数据的建模能力
- 图数据的加工能力
- 图数据的分析能力
- 图作业的运维管控支持

### 5. 执行环境

GeaFlow 可以运行在多种异构执行环境：

- Kubernetes (K8S)
- Ray
- 本地模式

## 核心概念

### GraphView

**GraphView** 是 GeaFlow 中最核心的数据抽象，表示基于图结构的虚拟视图。它是图物理存储的一种抽象，可以表示和操作分布在多个节点上的图数据。

在 GeaFlow 中，GraphView 是一等公民，用户对图的所有操作都是基于 GraphView。

**主要功能**：

1. **图操作**：可以添加或删除点和边数据，也可以进行查询和基于某个时间点切片快照
2. **图介质**：可以存储到图数据库或其他存储介质（如文件系统、KV 存储、宽表存储、Native Graph 等）
3. **图切分**：支持不同的图切分方法
4. **图计算**：可以进行图的迭代遍历或者计算

**示例**：定义一个 Social Network 的 GraphView，描述人际关系

```sql
CREATE GRAPH social_network (
  Vertex person (
    id int ID,
    name varchar
  ),
  Edge knows (
    person1 int SOURCE ID,
    person2 int DESTINATION ID,
    weight int
  )
) WITH (
  storeType='rocksdb',
  shardCount = 128
);
```

## 应用场景

### 1. 实时数仓加速

**场景描述**：

数仓场景存在大量 Join 运算，在 DWD 层往往需要将多张表展开成一张大宽表，以加速后续查询。当 Join 的表数量变多时，传统的实时计算引擎很难保证 Join 的时效性和性能，这也成为目前实时数仓领域一个棘手的问题。

**GeaFlow 的解决方案**：

- 以图作为数据模型，替代 DWD 层的宽表
- 实现数据实时构图
- 在查询阶段利用图的点边物化特性，极大加速关系运算的查询

### 2. 实时归因分析

**场景描述**：

在信息化的大背景下，对用户行为进行渠道归因和路径分析是流量分析领域中的核心。通过实时计算用户的有效行为路径，构建出完整的转化路径，能够快速帮助业务看清楚产品的价值，帮助运营及时调整运营思路。

实时归因分析的核心要点：

- **准确性**：在成本可控下保证用户行为路径分析的准确性
- **实效性**：计算的实时性足够高，才能快速帮助业务决策

**GeaFlow 的实现方式**：

1. 通过实时构图将用户行为日志转换成用户行为拓扑图
   - 用户作为图中的点
   - 每个行为构建成从该用户指向埋点页面的一条边
2. 利用流图计算能力分析用户行为子图
3. 在子图上基于归因路径匹配规则进行匹配计算
4. 得出成交行为相应用户的归因路径，并输出到下游系统

### 3. 实时反套现

**场景描述**：

在信贷风控场景下，如何进行信用卡反套现是一个典型的风控诉求。基于现有的套现模式分析，可以看到套现是一个环路子图，如何快速、高效地在大图中判定套现，将极大地增加风险的识别效率。

**GeaFlow 的实现方式**：

1. 将实时交易流、转账流等输入数据源转换成实时交易图
2. 根据风控策略对用户交易行为做图特征分析（如环路检查等特征计算）
3. 实时提供给决策和监控平台进行反套现行为判定

通过 GeaFlow 实时构图和实时图计算能力，可以快速发现套现等异常交易行为，极大降低平台风险。

## 快速上手

### 环境准备

编译 GeaFlow 依赖以下环境：

- JDK 8
- Maven（推荐 3.6.3 及以上版本）
- Git
- Docker（可选，用于运行 Console）

### 编译源码

执行以下命令来编译 GeaFlow 源码：

```bash
# 下载源码
git clone https://github.com/apache/geaflow.git
cd geaflow/

# 构建项目
./build.sh --module=geaflow --output=package
```

### 运行示例任务

**方式一：命令行提交任务**

运行一个实时环路查找的图计算作业：

```bash
./bin/gql_submit.sh --gql geaflow/geaflow-examples/gql/loop_detection_file_demo.sql
```

这是一段实时查询图中所有四度环路的 DSL 计算作业。

**方式二：使用 Console 平台**

1. 构建 Console jar 和镜像（需启动 Docker）：

```bash
./build.sh --module=geaflow-console
```

2. 启动 Console：

```bash
docker run -d --name geaflow-console -p 8888:8888 geaflow-console:0.1
```

3. 在浏览器中访问 `http://localhost:8888`，体验白屏化的图作业提交

### 示例：环路检测

以下是一个完整的环路检测示例 SQL：

```sql
set geaflow.dsl.window.size = 1;
set geaflow.dsl.ignore.exception = true;

-- 创建图模型
CREATE GRAPH IF NOT EXISTS dy_modern (
  Vertex person (
    id bigint ID,
    name varchar
  ),
  Edge knows (
    srcId bigint SOURCE ID,
    targetId bigint DESTINATION ID,
    weight double
  )
) WITH (
  storeType='rocksdb',
  shardCount = 1
);

-- 创建数据源表
CREATE TABLE IF NOT EXISTS tbl_source (
  text varchar
) WITH (
  type='file',
  `geaflow.dsl.file.path` = 'resource:///demo/demo_job_data.txt',
  `geaflow.dsl.column.separator`='|'
);

-- 创建结果表
CREATE TABLE IF NOT EXISTS tbl_result (
  a_id bigint,
  b_id bigint,
  c_id bigint,
  d_id bigint,
  a1_id bigint
) WITH (
  type='file',
  `geaflow.dsl.file.path` = '/tmp/geaflow/demo_job_result'
);

-- 使用图
USE GRAPH dy_modern;

-- 插入点数据
INSERT INTO dy_modern.person(id, name)
  SELECT
    cast(trim(split_ex(t1, ',', 0)) as bigint),
    split_ex(trim(t1), ',', 1)
  FROM (
    Select trim(substr(text, 2)) as t1
    FROM tbl_source
    WHERE substr(text, 1, 1) = '.'
  );

-- 插入边数据
INSERT INTO dy_modern.knows
  SELECT
    cast(split_ex(t1, ',', 0) as bigint),
    cast(split_ex(t1, ',', 1) as bigint),
    cast(split_ex(t1, ',', 2) as double)
  FROM (
    Select trim(substr(text, 2)) as t1
    FROM tbl_source
    WHERE substr(text, 1, 1) = '-'
  );

-- 查询环路并输出结果
INSERT INTO tbl_result
  SELECT DISTINCT
    a_id,
    b_id,
    c_id,
    d_id,
    a1_id
  FROM (
    MATCH (a:person) -[:knows]->(b:person) -[:knows]-> (c:person)
           -[:knows]-> (d:person) -> (a)
    RETURN a.id as a_id, b.id as b_id, c.id as c_id, 
           d.id as d_id, a.id as a1_id
  );
```

## 开发手册

GeaFlow 支持 **DSL** 和 **API** 两套编程接口：

### DSL 开发

通过 GeaFlow 提供的类 SQL 扩展语言 SQL+ISO/GQL 进行流图计算作业的开发。

**特点**：

- 融合了 SQL 和 GQL（图查询语言）
- 支持图表一体化分析
- 声明式编程，简单易用

**适用场景**：

- 复杂的图查询和分析
- 图表混合处理
- 快速原型开发

### API 开发

通过 GeaFlow 的高阶 API 编程接口，使用 Java 语言进行应用开发。

**特点**：

- 面向 Graph 和 Stream 的两套 API
- 支持流、批、图融合计算
- 灵活的编程控制

**适用场景**：

- 需要精细控制计算逻辑
- 复杂的自定义算法实现
- 与其他系统深度集成

## 相关学习资源

- 设计论文：[GeaFlow: A Graph Extended and Accelerated Dataflow System](https://dl.acm.org/doi/abs/10.1145/3589771)
- 官方文档：https://geaflow.apache.org/
- LDBC SNB-BI 基准测试：https://ldbcouncil.org/benchmarks/snb-bi/

---

*本文档基于 Apache GeaFlow 官方文档整理，更多详细信息请访问 [GeaFlow 官方文档](https://geaflow.apache.org/)。*
