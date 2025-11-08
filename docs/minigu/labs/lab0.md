# LAB 0 实验准备

## Rust基础入门

本系列实验使用Rust语言开发，建议具备基本的Rust编程能力。我们已经准备了相关的学习资源在[Rust语言基础](../rust.md)章节。在实验开始前，推荐从[Rustlings](https://github.com/rust-lang/rustlings/)项目练习。

本实验内容完成以下练习：

+ 05_vecs
+ 06_move_semantics
+ 15_traits
+ 16_lifetimes
+ 19_smart_pointers

## 了解项目

请阅读以下文档，了解本实验项目的整体设计与架构：

- [快速上手](../quick-start.md)
- [设计文档](../design.md)

实验项目的路径为`${PROJECT_ROOT}/miniGU`，请熟悉该目录结构。

## 编译与运行

请使用`cargo build`命令编译项目，并确保能够成功运行。可以参考[快速上手](../quick-start.md)章节中的指导。

实验过程中，你需要做的是对指定接口进行实现，然后通过`cargo test`运行单元测试，确保实现的正确性。

## 背景知识

在开始实验之前，我们需要了解一些数据库与图的基础概念，这将帮助你更好地理解 miniGU 存储系统的设计思路。

### 数据库系统的经典架构

一个完整的数据库系统通常分为两大核心组件：

- **查询引擎（Query Engine）**：负责解析用户查询、生成执行计划、优化查询路径。对于图数据库而言，查询引擎需要理解图查询语言（如 GQL、Cypher、Gremlin），将高层查询转换为底层的存储操作序列。
- **存储引擎（Storage Engine）**：负责数据的持久化存储、索引维护、事务管理、并发控制和崩溃恢复。它向查询引擎提供统一的数据访问接口（CRUD），屏蔽底层存储细节。


### 属性图（Label Property Graph）模型

图模型有多重种，包括RDF图、属性图等。其中，属性图是一种常用的图数据模型，主要由以下元素组成：

- **顶点（Vertex）**：图中的节点，表示实体（如用户、商品等）。每个顶点可以有多个标签（Label）和属性（Property）。
- **边（Edge）**：连接顶点的有向关系，表示实体之间的联系。每条边也可以有多个标签和属性。

### 图数据库的查询语言

由于历史发展的原因,图数据库的查询语言多种多样,主要包括:GQL、SQL/PGQ、Cypher、Gremlin等。GQL是图查询语言的国际标准,Cypher 是 Neo4j 图数据库的查询语言,Gremlin 则是 Apache TinkerPop 图计算框架的查询语言。GQL于2024年被ISO采纳为国际标准,未来是图数据库的统一查询语言标准。下面是一些GQL的示例:

#### 查询操作（Read）

```gql
// 查询单个顶点:根据ID查询用户的姓名和年龄
MATCH (u:User WHERE u.id = 12345)
RETURN u.name, u.age

// 查询关系:查找某用户关注的所有人
MATCH (u:User WHERE u.name = 'Alice')-[:FOLLOWS]->(friend:User)
RETURN friend.name, friend.age

// 多跳查询:查找朋友的朋友(2度关系)
MATCH (u:User WHERE u.name = 'Alice')-[:FOLLOWS*2]->(fof:User)
RETURN DISTINCT fof.name

// 复杂模式匹配:查找相互关注的用户对
MATCH (u1:User)-[:FOLLOWS]->(u2:User)-[:FOLLOWS]->(u1)
RETURN u1.name, u2.name

// 聚合查询:统计每个用户的关注者数量
MATCH (u:User)<-[:FOLLOWS]-(follower:User)
RETURN u.name, COUNT(follower) AS follower_count
ORDER BY follower_count DESC
```

#### 创建操作（Create）

```gql
// 创建单个顶点:创建一个新用户
CREATE (u:User {id: 67890, name: 'Bob', age: 28, city: 'Beijing'})

// 创建多个顶点:批量创建用户
CREATE (u1:User {id: 10001, name: 'Carol', age: 25}),
       (u2:User {id: 10002, name: 'Dave', age: 30})

// 创建顶点和边:创建用户并建立关注关系
CREATE (u1:User {id: 20001, name: 'Eve', age: 26}),
       (u2:User {id: 20002, name: 'Frank', age: 29}),
       (u1)-[:FOLLOWS {since: '2024-01-15'}]->(u2)

// 在已有顶点间创建边:为现有用户建立好友关系
MATCH (u1:User WHERE u1.name = 'Alice'),
      (u2:User WHERE u2.name = 'Bob')
CREATE (u1)-[:FRIENDS {since: '2024-03-20', strength: 'strong'}]->(u2)
```

#### 更新操作（Update）

```gql
// 更新顶点属性:修改用户年龄
MATCH (u:User WHERE u.id = 12345)
SET u.age = 31

// 批量更新:为所有北京用户添加标签
MATCH (u:User WHERE u.city = 'Beijing')
SET u.region = 'North'

// 更新边属性:更新关注关系的时间戳
MATCH (u1:User)-[f:FOLLOWS]->(u2:User WHERE u2.name = 'Bob')
SET f.last_interaction = '2024-11-08'

// 条件更新:只更新符合条件的属性
MATCH (u:User WHERE u.age < 30)
SET u.category = 'young_user', u.updated_at = timestamp()

// 删除属性:移除用户的某个属性
MATCH (u:User WHERE u.id = 12345)
REMOVE u.city
```

#### 删除操作（Delete）

```gql
// 删除单个顶点:删除用户(需先删除相关的边)
MATCH (u:User WHERE u.id = 67890)
DETACH DELETE u

// 删除边:删除特定的关注关系
MATCH (u1:User WHERE u1.name = 'Alice')-[f:FOLLOWS]->(u2:User WHERE u2.name = 'Bob')
DELETE f

// 批量删除:删除所有不活跃用户及其关系
MATCH (u:User WHERE u.last_login < '2023-01-01')
DETACH DELETE u

// 条件删除:删除年龄小于18的用户的敏感信息属性
MATCH (u:User WHERE u.age < 18)
REMOVE u.phone, u.email
```

#### 复合操作示例

```gql
// MERGE操作:创建或更新(如果存在则更新,不存在则创建)
MERGE (u:User {id: 12345})
ON CREATE SET u.name = 'NewUser', u.created_at = timestamp()
ON MATCH SET u.last_seen = timestamp()

// 路径查询与过滤:查找最短路径
MATCH p = shortestPath((u1:User WHERE u1.name = 'Alice')
                       -[:FOLLOWS*]->
                       (u2:User WHERE u2.name = 'Bob'))
RETURN p, length(p) AS path_length
```
