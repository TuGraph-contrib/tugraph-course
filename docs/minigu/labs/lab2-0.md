# Lab 2 图查询处理完整教程

## 概览

本教程将带你完整理解 miniGU 图数据库的查询处理流程，从查询语句到最终执行结果的全链路实现。

Lab 2 分为三个递进的实验：

- Lab 2-1：Expand/Project 执行器，实现图遍历和投影计算
- Lab 2-2：Filter 逻辑计划，在逻辑计划中添加 Filter 节点
- Lab 2-3：谓词下推优化，实现查询优化器

**学习目标**：

- 理解查询处理的完整流程
- 掌握逻辑计划与物理计划的区别
- 实现核心执行器算子
- 学习查询优化技术

---

## 1. 查询处理全流程

让我们通过一个完整的例子理解查询处理流程：

```gql
MATCH (n:Person) 
WHERE n.age > 18 
RETURN n.name
```

**完整流程**:


### 词法分析 (Lexer)
- 输入: "MATCH (n:Person) WHERE n.age > 18 RETURN n.name"
- 输出: [MATCH, LPAREN, IDENT("n"), COLON, ...]

### 语法分析 (Parser)
- 输入: Token 流
- 输出: 抽象语法树 (AST)
```
    MatchStatement {
    pattern: (n:Person),
    where: BinaryOp(n.age > 18),
    return: [n.name]
    }
```

### 语义绑定 (Binder)
   - 输入: AST
   - 输出: 绑定后的语法树 (Bound AST)
     - 变量解析: n → Variable(0)
     - 类型推导: n.age → Int64
     - Schema 构建: [name: String]

### 逻辑计划生成 (Logical Planner)
   - 输入: Bound AST
   - 输出: 逻辑计划树
     ```
     LogicalProject(n.name)
         ↓
     LogicalFilter(n.age > 18)
         ↓
     LogicalMatch(n:Person)
     ```

### 查询优化 (Optimizer)
   - 输入: 逻辑计划
   - 输出: 优化后的物理计划
     ```
     PhysicalProject(n.name)
         ↓
     PhysicalFilter(n.age > 18)
         ↓
     PhysicalNodeScan(n:Person)
     ```
   - 优化技术:
     - 谓词下推
     - 投影下推
     - Join 重排序

### 执行器构建 (Executor Builder)
   - 输入: 物理计划
   - 输出: 执行器树
     ```
     ProjectExecutor
         ↓
     FilterExecutor
         ↓
     NodeScanExecutor
     ```

### 执行引擎 (Execution Engine)
   - 输入: 执行器树
   - 输出: 结果集 (DataChunk 流)
   
   执行过程 (Pull-based):
   - 1. ProjectExecutor.next() → 调用子执行器
   - 2. FilterExecutor.next() → 调用子执行器
   - 3. NodeScanExecutor.next() → 从存储引擎读取数据 → 返回 DataChunk
   - 4. 应用过滤条件 → FilterExecutor 过滤 → 返回过滤后的 DataChunk
   - 5. 计算投影表达式 → ProjectExecutor 投影 → 返回最终结果

### 结果返回
   - 输出: 格式化的结果
     ```
     name
     ------
     Alice
     Bob
     Carol
     ```

## 2. 核心概念详解

### 2.1 火山模型 (Volcano Model)

miniGU 采用经典的火山模型 (也称迭代器模型):

```rust
trait Executor: Iterator<Item = Result<DataChunk>> {
    fn next(&mut self) -> Option<Result<DataChunk>>;
}
```

**特点**:

- **拉取式 (Pull-based)**: 父节点主动向子节点请求数据
- **流式处理**: 数据以批次 (DataChunk) 流动
- **内存友好**: 不需要一次性加载所有数据
- **易于组合**: 执行器可以任意组合成树

### 2.2 DataChunk: 列式批处理

DataChunk 是 miniGU 的数据传输单元,基于 Apache Arrow:

```rust
pub struct DataChunk {
    columns: Vec<ArrayRef>,      // 列数组 (Arrow Array)
    filter: Option<BooleanArray>, // 过滤位图 (延迟应用)
}
```

**列式存储优势**:

- **缓存友好**: 连续内存访问
- **向量化计算**: 便于使用 SIMD 加速
- **压缩高效**: 同类型数据压缩率高
- **零拷贝**: 共享内存,避免复制

### 2.3 表达式求值

表达式求值器负责计算各种表达式:

```rust
trait Evaluator {
    fn evaluate(&self, chunk: &DataChunk) -> Result<DataValue>;
}
```

**表达式类型**:

- **列引用**: `n.name` → 从 chunk 中提取列
- **字面量**: `42`, `"hello"` → 常量
- **二元运算**: `a + b`, `a > b` → 向量化计算
- **函数调用**: `length(s)`, `abs(x)` → 内置函数

---

## 3. Lab 2-1: Expand 与 Project 执行器实现

### 3.1 任务目标

实现两个核心执行器:

1. **Expand**: 图遍历，从顶点扩展到邻居
2. **Project**: 投影计算，计算 RETURN 表达式

### 3.2 Expand 执行器

**功能**: 实现 `MATCH (a)-[r]->(b)` 中的边遍历

**输入**: DataChunk 包含起始顶点 ID
```text
[v1, v2, v3]
```

**输出**: DataChunk 包含 [原始列 + 边列 + 邻居列]
```text
[v1, [e1, e2], [v4, v5]]
[v2, [e3],     [v6]    ]
[v3, [],       []      ]
```

**实现位置**:

- 文件: `execution/src/executor/expand.rs`
- 函数: `ExpandBuilder::into_executor`
- 行数: 91-123

**核心逻辑**:
```rust
// 1. compact chunk
chunk = chunk.compact();

// 2. 提取顶点 ID
let vertex_ids = chunk.columns().get(input_column_index)?
    .as_primitive::<VertexIdType>().values();

// 3. 扩展每个顶点
for &vid in vertex_ids.iter() {
    let (targets, edges) = source.expand_from_vertex(
        vid, edge_labels, target_labels
    )?;
    // 累积结果...
}

// 4. 构建 ListArray 并追加列
chunk = chunk.append_columns(vec![edge_list, target_list]);
yield Ok(chunk);
```

### 3.3 Project 执行器

**功能**: 实现 `RETURN n.name, n.age + 1` 中的表达式计算

**输入**: DataChunk
```text
[id: [1,2,3], name: [A,B,C], age: [20,25,30]]
```

**输出**: DataChunk (计算后的列)
```text
[name: [A,B,C], age+1: [21,26,31]]
```

**实现位置**:
- 文件: `execution/src/executor/project.rs`
- 函数: `ProjectBuilder::into_executor`
- 行数: 56-94

**核心逻辑**:
```rust
// 1. 计算新列
let mut new_columns = Vec::new();
for evaluator in evaluators.iter() {
    let data_value = evaluator.evaluate(&chunk)?;
    new_columns.push(data_value.into_array());
}

// 2. 创建新 chunk
let mut new_chunk = DataChunk::new(new_columns);

// 3. 保留 filter
if let Some(filter) = chunk.filter() {
    new_chunk = new_chunk.with_filter(filter.clone());
}

yield Ok(new_chunk);
```

### 3.4 测试验证

```bash
cargo test -p minigu-execution test_expand_executor
cargo test -p minigu-execution test_project_executor
```

**详细文档**: [Lab 2-1 详细说明](./lab2-1.md)

---

## 4. Lab 2-2: Filter 逻辑计划实现

### 4.1 任务目标

在 MATCH 语句包含 WHERE 子句时，生成 Filter 逻辑计划节点。

**输入**:
```gql
MATCH (n:Person) WHERE n.age > 18 RETURN n
```

**输出** (逻辑计划):
```text
LogicalProject(n)
    ↓
LogicalFilter(n.age > 18)
    ↓
LogicalMatch(n:Person)
```

### 4.2 实现位置

文件: `planner/src/logical_planner/query.rs`
函数: `plan_match_statement`
行数: 93-127

### 4.3 实现要点

```rust
// 1. 检查是否有 WHERE 条件
if let Some(predicate) = binding.pattern.predicate {
    // 2. 创建 Filter 节点包装当前 plan
    let filter = Filter::new(plan, predicate);
    // 3. 更新 plan
    plan = PlanNode::LogicalFilter(Arc::new(filter));
}
```

### 4.4 测试验证

```bash
cargo test -p minigu-planner test_plan_match_with_filter
```

**详细文档**: [Lab 2-2 详细说明](./lab2-2.md)

---

## 5. Lab 2-3: 谓词下推优化

### 5.1 任务目标

实现谓词下推优化,将 Filter 条件推到数据源附近。

**优化前**:
```text
Filter(n.id = 1)
    ↓
NodeScan(n)  // 扫描所有顶点
```

**优化后**:
```text
NodeScanById(n, id=1)  // 直接定位
```

**性能提升**: 从 O(n) 全表扫描优化为 O(1) 索引查找

### 5.2 实现位置

文件: `planner/src/optimizer/mod.rs`
函数: `create_physical_plan_impl`
分支: `PlanNode::LogicalFilter`
行数: 149-206

### 5.3 实现步骤

```rust
// 1. 检查子节点是否为 NodeScan
if let PlanNode::PhysicalNodeScan(node_scan) = &child {
    // 2. 分析 predicate 是否为 ID 等值条件
    if let Some(id) = try_extract_id_predicate(&filter.predicate, &node_scan.var) {
        // 3. 创建优化节点
        let scan_by_id = NodeScanById::new(
            node_scan.var.clone(),
            node_scan.labels.clone(),
            id,
        );
        return Ok(PlanNode::PhysicalNodeScanById(Arc::new(scan_by_id)));
    }
}

// 4. 默认: 创建 PhysicalFilter (不优化)
let filter = Filter::new(child, filter.predicate.clone());
Ok(PlanNode::PhysicalFilter(Arc::new(filter)))
```

### 5.4 辅助函数

需要实现 `try_extract_id_predicate` 函数:

```rust
fn try_extract_id_predicate(
    predicate: &BoundExpression,
    var: &str,
) -> Option<VertexId> {
    // 检查是否为 n.id = 1 或 1 = n.id
    if let BoundExpression::BinaryOp { op, left, right } = predicate {
        if *op == BinaryOperator::Eq {
            // 检查 n.id = 1
            if matches_property(left, var, "id") {
                return extract_literal(right);
            }
            // 检查 1 = n.id
            if matches_property(right, var, "id") {
                return extract_literal(left);
            }
        }
    }
    None
}
```

### 5.5 测试验证

```bash
cargo test -p minigu-planner test_predicate_pushdown

# 手动验证
minigu> EXPLAIN PHYSICAL MATCH (n) WHERE n.id = 1 RETURN n;
# 应该看到 PhysicalNodeScanById
```

**详细文档**: [Lab 2-3 详细说明](./lab2-3.md)

---

## 6. 完整示例: 端到端查询

让我们通过一个完整的例子, 串联所有知识点:

### 6.1 查询语句

```gql
MATCH (a:Person WHERE a.id = 1)-[r:KNOWS]->(b:Person)
WHERE b.age > 18
RETURN a.name, b.name, r.since
```

### 6.2 逻辑计划 (Lab 2-2)

```text
LogicalProject(a.name, b.name, r.since)
    ↓
LogicalFilter(b.age > 18)
    ↓
LogicalExpand(r:KNOWS, b:Person)
    ↓
LogicalFilter(a.id = 1)
    ↓
LogicalMatch(a:Person)
```

### 6.3 物理计划 (Lab 2-3 优化后)

```text
PhysicalProject(a.name, b.name, r.since)
    ↓
PhysicalFilter(b.age > 18)
    ↓
PhysicalExpand(r:KNOWS, b:Person)
    ↓
PhysicalNodeScanById(a, id=1)  ← 优化: 直接定位
```

### 6.4 执行过程 (Lab 2-1)

```text
1. NodeScanById 执行:
   → 从存储引擎查找 id=1 的顶点
   → 返回 DataChunk: [a: {id:1, name:"Alice"}]

2. Expand 执行:
   → 调用 source.expand_from_vertex(1, [KNOWS], [Person])
   → 返回 DataChunk: [a, r, b]
      [1, 101, 2]  // Alice KNOWS Bob
      [1, 102, 3]  // Alice KNOWS Carol

3. Filter 执行:
   → 计算 b.age > 18
   → 应用过滤位图
   → 返回 DataChunk (过滤后)

4. Project 执行:
   → 计算 a.name, b.name, r.since
   → 返回最终结果:
      ["Alice", "Bob",   "2020-01-01"]
      ["Alice", "Carol", "2021-06-15"]
```

### 6.5 性能分析

**优化前**:
- NodeScan: 扫描 10000 个顶点
- Filter: 过滤出 1 个顶点
- Expand: 扩展 1 个顶点的邻居
- **总扫描**: 10000 个顶点

**优化后**:
- NodeScanById: 直接定位 1 个顶点
- Expand: 扩展 1 个顶点的邻居
- **总扫描**: 1 个顶点

---

## 7. 调试技巧

查看计划树：
```bash
# 查看逻辑计划
minigu> EXPLAIN <query>;
```

添加日志进行调试：
```rust
// 在代码中添加调试输出
println!("Plan: {:#?}", plan);
println!("Chunk: rows={}, cols={}", chunk.num_rows(), chunk.num_columns());
```

单元测试：
```bash
# 运行特定测试
cargo test -p minigu-planner test_plan_match_with_filter -- --nocapture

# 显示输出
cargo test -- --nocapture --test-threads=1
```

---

## 8. 常见问题FAQ

### Q1: 为什么使用 Arc?

`Arc<T>` 提供共享所有权,允许多个执行器共享同一个子节点,避免深拷贝。

### Q2: gen move 是什么?

Rust 的 generator 语法,用于实现协程式迭代器。`yield` 暂停执行并返回值。

### Q3: 为什么 Filter 使用位图而不是直接删除行?

延迟求值 (lazy evaluation)。位图避免数据复制,只在必要时 (compact) 才真正删除。

### Q4: 如何处理 NULL 值?

Arrow 数组内置 NULL 支持,通过 validity bitmap 标记。

### Q5: 如何优化内存使用?

- 使用 Arrow 的零拷贝机制
- 及时 compact 释放过滤行
- 控制 DataChunk 批次大小
- 使用流式处理避免全量加载