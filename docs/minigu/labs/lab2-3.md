# Lab 2-3 谓词下推优化

在 Lab 2-1 和 Lab 2-2 中,我们实现了 Filter 逻辑计划节点和 Expand/Project 执行器。本实验将进入**查询优化器**层,实现一个经典的优化技术:**谓词下推 (Predicate Pushdown)**。

谓词下推是数据库查询优化的核心技术之一,通过将过滤条件尽可能靠近数据源,可以显著减少中间数据量,提升查询性能。

---

## 0. 背景知识

### 查询优化器的作用

查询优化器负责将逻辑计划转换为高效的物理计划:

```text
逻辑计划 (Logical Plan)
    ↓
优化器 (Optimizer)
  - 规则优化 (Rule-based)
  - 代价优化 (Cost-based)
    ↓
物理计划 (Physical Plan)
```

**优化目标**:

- 减少数据扫描量
- 减少中间结果大小
- 选择高效的算法和数据结构
- 合理安排执行顺序

### 谓词下推 (Predicate Pushdown)

**核心思想**: 将 Filter 条件尽可能推到数据源附近,在数据产生时就进行过滤。

**优化前**:
```text
Filter(n.id = 1)
    ↓
NodeScan(n)  // 扫描所有顶点,返回 1000 个
    ↓
Filter 过滤,只保留 1 个
```

**优化后**:
```text
NodeScanById(n, id=1)  // 直接定位,只返回 1 个
```

**性能提升**:

- 减少 I/O: 只读取需要的数据
- 减少内存: 中间结果更小
- 减少 CPU: 避免无效计算

### 适用场景

并非所有 Filter 都能下推,需要满足条件:

1. **等值条件**: `n.id = 1` (可下推为索引查找)
2. **范围条件**: `n.age > 18` (可下推为索引范围扫描)
3. **单表条件**: 只涉及一个表/节点 (多表条件需在 Join 后)
4. **索引支持**: 数据源需要支持相应的索引访问

### miniGU 中的优化器架构

```rust
pub struct Optimizer {}

impl Optimizer {
    pub fn create_physical_plan(
        self,
        logical_plan: &PlanNode
    ) -> PlanResult<PlanNode> {
        create_physical_plan_impl(logical_plan)
    }
}

fn create_physical_plan_impl(
    logical_plan: &PlanNode
) -> PlanResult<PlanNode> {
    // 递归转换子节点
    let children = logical_plan.children()
        .iter()
        .map(create_physical_plan_impl)
        .try_collect()?;
    
    // 根据节点类型进行转换和优化
    match logical_plan {
        PlanNode::LogicalMatch(m) => { /* ... */ }
        PlanNode::LogicalFilter(f) => { /* 谓词下推优化 */ }
        PlanNode::LogicalProject(p) => { /* ... */ }
        // ...
    }
}
```

---

## 1. 模块设计与代码结构

### 相关文件

| 文件 | 作用 | 本实验关注点 |
|------|------|-------------|
| `planner/src/optimizer/mod.rs` | 优化器主逻辑 | **实现谓词下推** |
| `planner/src/plan/scan.rs` | Scan 节点定义 | 了解 NodeScanById |
| `planner/src/plan/filter.rs` | Filter 节点定义 | 了解 predicate 结构 |
| `planner/src/bound/expression.rs` | 表达式定义 | 分析 predicate |

### 核心数据结构

```rust
// Scan 节点类型
pub struct NodeIdScan {
    pub var: String,
    pub labels: Vec<Vec<LabelId>>,
}

pub struct NodeScanById {
    pub var: String,
    pub labels: Vec<Vec<LabelId>>,
    pub id: VertexId,  // 指定的顶点 ID
}

// Filter 节点
pub struct Filter {
    pub child: PlanNode,
    pub predicate: BoundExpression,
}

// 表达式类型
pub enum BoundExpression {
    BinaryOp {
        op: BinaryOperator,
        left: Box<BoundExpression>,
        right: Box<BoundExpression>,
    },
    Property {
        var: String,
        property: String,
    },
    Literal(Value),
    // ...
}
```

---

## 2. 实验任务

### 任务描述

在 `create_physical_plan_impl` 函数的 `LogicalFilter` 分支中,实现谓词下推优化。

**文件**: `labs/miniGU/minigu/gql/src/planner/src/optimizer/mod.rs`

**位置**: 第 149-206 行

### 优化目标

将以下模式:

```text
LogicalFilter(n.id = 1)
    ↓
PhysicalNodeScan(n)
```

优化为:

```text
PhysicalNodeScanById(n, id=1)
```

### 实现步骤

1. **检查子节点类型**: 判断 child 是否为 `PhysicalNodeScan`
2. **分析 predicate**: 判断是否为 ID 等值条件 (如 `n.id = 1`)
3. **提取 ID 值**: 从 predicate 中提取顶点 ID
4. **创建优化节点**: 用 `NodeScanById` 替代 `Filter + NodeScan`

### 代码框架

```rust
PlanNode::LogicalFilter(filter) => {
    let [child] = children
        .try_into()
        .expect("filter should have exactly one child");

    // ============================================================
    // LAB 2-3 TODO: 实现谓词下推优化
    // ============================================================
    //
    // 谓词下推是数据库查询优化的重要技术。
    // 将 Filter 条件推到数据源附近可以减少中间数据量。
    //
    // ## 优化目标
    // 优化前:
    // Filter(n.id = 1)
    // └── NodeScan(n)
    //
    // 优化后:
    // NodeScanById(n, id=1)
    //
    // ## 任务描述
    // 1. 检查子节点是否为 PhysicalNodeScan
    // 2. 分析 predicate 是否为 ID 等值比较 (如 n.id = 1)
    // 3. 如果满足条件,创建 NodeScanById 节点替代 Filter + NodeScan
    //
    // 请在下方实现:
    // ============================================================

    // YOUR CODE HERE (可选的高级实验)
    // 如果下推成功,直接返回优化后的节点
    // 否则,继续使用默认的 Filter 处理

    // ============================================================
    // END LAB 2-3 TODO
    // ============================================================

    // 默认行为: 创建 PhysicalFilter (不优化)
    let predicate = filter.predicate.clone();
    let filter = Filter::new(child, predicate);
    Ok(PlanNode::PhysicalFilter(Arc::new(filter)))
}
```

---

## 3. 测试验证

### 单元测试

```bash
# 运行优化器测试
cargo test -p minigu-planner test_optimizer --no-fail-fast

# 运行谓词下推测试
cargo test -p minigu-planner test_predicate_pushdown
```

### 手动验证

```bash
# 启动 miniGU
cd labs/miniGU
cargo run

# 查看优化前的计划
minigu> EXPLAIN LOGICAL MATCH (n:Person) WHERE n.id = 1 RETURN n;

# 输出应该包含 LogicalFilter
LogicalProject
  ↓
LogicalFilter(n.id = 1)
  ↓
LogicalMatch(n:Person)

# 查看优化后的计划
minigu> EXPLAIN PHYSICAL MATCH (n:Person) WHERE n.id = 1 RETURN n;

# 输出应该优化为 NodeScanById
PhysicalProject
  ↓
PhysicalNodeScanById(n, id=1)  ← 优化成功!
```

---

## 4. 一些思考

### 为什么不是所有 Filter 都能下推?

- **依赖关系**: 如果 Filter 依赖 Join 的结果,必须在 Join 之后
- **计算成本**: 有些复杂表达式在数据源层计算成本更高
- **数据源能力**: 不是所有数据源都支持复杂过滤

### 谓词下推会影响结果正确性吗?

不会。谓词下推是**等价变换**,只改变执行方式,不改变语义。优化器必须保证:
- 结果集相同
- 行顺序可能不同 (除非有 ORDER BY)

### 如何处理多个 Filter?

可以合并或分别下推:

```text
Filter(n.age > 18)
  ↓
Filter(n.id = 1)
  ↓
NodeScan(n)

→ 合并为: Filter(n.id = 1 AND n.age > 18)
→ 下推 ID: NodeScanById(n, 1) + Filter(n.age > 18)
```

---

## 5. FAQ

**Q: NodeScanById 需要自己实现吗?**

A: 需要。你需要在 `planner/src/plan/scan.rs` 中定义 `NodeScanById` 结构体,并在执行层实现对应的执行器。

**Q: 如何确保优化是正确的?**

A: 通过测试对比优化前后的结果集,确保完全一致。可以使用 `EXPLAIN` 查看计划,`PROFILE` 查看性能。

**Q: 优化器在什么时候运行?**

A: 在逻辑计划生成后、执行前运行:

```text
Parser → Binder → Logical Planner → Optimizer → Executor
```

**Q: 可以关闭优化吗?**

A: 可以添加配置选项:

```rust
pub struct OptimizerConfig {
    pub enable_predicate_pushdown: bool,
    pub enable_join_reorder: bool,
    // ...
}
```

**Q: 如何调试优化器?**

A: 
1. 使用 `EXPLAIN` 查看计划树
2. 添加日志: `println!("Before: {:#?}", plan);`
3. 单元测试验证每个优化规则
