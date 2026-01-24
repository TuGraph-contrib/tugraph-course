# Lab 2-1 Expand 与 Project 执行器实现

在 Lab 1 中,我们实现了面向 OLTP 的内存图存储引擎。本实验将深入**执行引擎层**,实现两个核心执行器:

- **Expand 执行器**: 实现图遍历,从起始顶点沿边扩展到邻居顶点
- **Project 执行器**: 实现投影操作,计算 RETURN 子句中的表达式

这两个执行器是图查询引擎的核心组件,理解它们的实现原理对掌握图数据库至关重要。

---

## 0. 背景知识

### 查询处理流程

一个完整的图查询处理流程包括:

```text
GQL 查询语句
    ↓
词法分析 (Lexer)
    ↓
语法分析 (Parser)
    ↓
语义绑定 (Binder)
    ↓
逻辑计划生成 (Logical Planner) ← Lab 2-2 重点
    ↓
物理计划优化 (Optimizer) ← Lab 2-3 重点
    ↓
执行器构建 (Executor Builder)
    ↓
执行引擎 (Execution Engine) ← Lab 2-1 重点
    ↓
结果返回
```

### 执行器模型

miniGU 采用 **迭代器模型 (Iterator Model)** / **火山模型 (Volcano Model)**:

```text
每个执行器实现 Iterator trait:
  - next() -> Option<Result<DataChunk>>
  
执行器之间形成树状结构:
  Parent Executor
      ↓ next()
  Child Executor
      ↓ next()
  Leaf Executor (Scan)
```

**优点**:

- 流式处理,内存占用小
- 代码结构清晰,易于组合
- 支持 pipeline 执行

### DataChunk: 列式数据批处理

miniGU 使用 Apache Arrow 的列式存储格式:

```rust
pub struct DataChunk {
    columns: Vec<ArrayRef>,      // 列数组
    filter: Option<BooleanArray>, // 过滤位图 (可选)
}
```

**关键操作**:

- `chunk.columns()`: 获取所有列
- `chunk.slice(offset, length)`: 切片
- `chunk.compact()`: 应用 filter,移除被过滤的行
- `chunk.append_columns(cols)`: 追加新列
- `chunk.with_filter(filter)`: 设置过滤位图

### Expand: 图遍历的核心

Expand 操作实现了图的邻接遍历:

```text
输入: DataChunk 包含顶点 ID
       [v1, v2, v3, ...]

处理: 对每个顶点,查询其邻居
       v1 -> [(e1, v4), (e2, v5)]
       v2 -> [(e3, v6)]
       v3 -> []

输出: DataChunk 包含 [原始列 + 边列 + 邻居列]
       [v1, e1, v4]
       [v1, e2, v5]
       [v2, e3, v6]
```

**关键点**:

- 一个输入顶点可能产生多行输出 (1-to-N 扩展)
- 需要过滤边标签和目标顶点标签
- 需要处理方向 (出边/入边)

### Project: 表达式计算

Project 操作计算投影表达式:

```text
输入: DataChunk
       [n.id, n.name, n.age]
       [1,    "Alice", 25   ]
       [2,    "Bob",   30   ]

表达式: [n.name, n.age + 1]

输出: DataChunk
       [n.name,  n.age + 1]
       ["Alice", 26       ]
       ["Bob",   31       ]
```

---

## 1. 模块设计与代码结构

### 相关文件

| 文件 | 作用 | 本实验关注点 |
|------|------|-------------|
| `execution/src/executor/expand.rs` | Expand 执行器实现 | **实现图扩展逻辑** |
| `execution/src/executor/project.rs` | Project 执行器实现 | **实现投影计算逻辑** |
| `execution/src/executor/mod.rs` | 执行器 trait 定义 | 了解 Executor trait |
| `execution/src/source/mod.rs` | 数据源接口 | 了解 ExpandSource trait |
| `execution/src/evaluator/mod.rs` | 表达式求值器 | 了解 Evaluator 接口 |

### 核心 Trait

```rust
// 执行器 trait
pub trait Executor: Iterator<Item = Result<DataChunk>> {}

// 执行器构建器 trait
pub trait IntoExecutor {
    type IntoExecutor: Executor;
    fn into_executor(self) -> Self::IntoExecutor;
}

// 图数据源 trait (用于 Expand)
pub trait ExpandSource {
    fn expand_from_vertex(
        &self,
        vid: VertexId,
        edge_labels: Option<&[Vec<LabelId>]>,
        target_labels: Option<&[Vec<LabelId>]>,
    ) -> Result<(VertexIdArray, EdgeIdArray)>;
}

// 表达式求值器 trait (用于 Project)
pub trait Evaluator {
    fn evaluate(&self, chunk: &DataChunk) -> Result<DataValue>;
}
```

---

## 2. 实验任务 1: 实现 Expand 执行器

### 任务描述

实现 `ExpandBuilder::into_executor()` 方法,完成图的邻接扩展逻辑。

**文件**: `labs/miniGU/minigu/gql/src/execution/src/executor/expand.rs`

**位置**: 第 91-123 行

### 执行流程

```text
1. 遍历子执行器产生的每个 DataChunk
2. compact() chunk,移除被过滤的行
3. 从 chunk 中提取顶点 ID 列
4. 对每个顶点调用 source.expand_from_vertex() 获取邻居
5. 将邻居信息 (边 ID, 目标顶点 ID) 追加到 chunk
6. yield 扩展后的 chunk
```

---

## 3. 实验任务 2: 实现 Project 执行器

### 任务描述

实现 `ProjectBuilder::into_executor()` 方法,完成投影表达式的计算。

**文件**: `labs/miniGU/minigu/gql/src/execution/src/executor/project.rs`

**位置**: 第 56-94 行

### 执行流程

```text
1. 遍历子执行器产生的每个 DataChunk
2. 对每个 chunk,使用 evaluators 计算新列
3. 创建包含新列的 DataChunk
4. 保留原始 filter (如果有)
5. yield 新 chunk
```

---

## 4. 测试验证

### 单元测试

```bash
# 运行 execution 相关测试
cargo test -p minigu-execution --no-fail-fast

# 运行特定测试
cargo test -p minigu-execution test_expand_executor
cargo test -p minigu-execution test_project_executor
```

### 集成测试

```bash
# 启动 miniGU
cd labs/miniGU
cargo run

# 测试 Expand
minigu> MATCH (a:Person)-[r:KNOWS]->(b:Person) RETURN a.name, b.name;

# 测试 Project
minigu> MATCH (n:Person) RETURN n.name, n.age + 1 AS next_age;
```

---

## 5. 一些思考

### 为什么 Expand 产生 ListArray 而不是展平?

ListArray 保留了原始行的对应关系,便于后续操作 (如 UNNEST)。实际执行时,会有专门的 Unnest 算子将 ListArray 展平。

### 为什么 Project 要保留 filter?
Filter 是延迟应用的 (lazy evaluation)。保留 filter 可以避免不必要的数据复制,只在真正需要时 (如 compact()) 才应用。

### 如何处理空结果?

- Expand: 如果顶点没有邻居,生成空的 ListArray (offsets 连续相等)
- Project: 即使输入为空,也要生成对应 schema 的空 DataChunk

---

## 6. 下一步

完成 Lab 2-1 后,你已经掌握了执行器的实现方法。

**Lab 2-2** 将实现 **Filter 逻辑计划节点**,支持 WHERE 子句的过滤功能。

**Lab 2-3** 将实现 **谓词下推优化**,通过优化器改写查询计划,提升执行效率。

---

## 7. FAQ

**Q: gen move 是什么语法?**

A: 这是 Rust 的 generator 语法,用于实现协程式的迭代器。`yield` 关键字会暂停执行并返回值。

**Q: 为什么需要 Arc::new()?**

A: ArrayRef 是 `Arc<dyn Array>` 的类型别名,需要用 Arc 包装以支持共享所有权。

**Q: 如何调试执行器?**

A: 可以在 generator 中添加 `println!` 或使用 `dbg!` 宏打印中间结果。
