# Lab 2-1 Filter 逻辑计划实现

在 Lab 1 中,我们实现了面向 OLTP 的内存图存储引擎。本实验将进入查询处理层,学习如何将 GQL 查询语句转换为可执行的查询计划。

Lab 2-1 聚焦于 **Filter 逻辑计划节点的生成**,这是支持 `WHERE` 子句的基础。

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
逻辑计划生成 (Logical Planner) ← Lab 2-1 重点
    ↓
物理计划优化 (Optimizer) ← Lab 2-3 重点
    ↓
执行器构建 (Executor Builder)
    ↓
执行引擎 (Execution Engine) ← Lab 2-2 重点
    ↓
结果返回
```

### 逻辑计划 vs 物理计划

- **逻辑计划 (Logical Plan)**: 描述"做什么",与具体执行方式无关
  - 例: `LogicalFilter(n.age > 18) -> LogicalMatch(n)`
  
- **物理计划 (Physical Plan)**: 描述"怎么做",包含具体算法和数据访问方式
  - 例: `PhysicalFilter(n.age > 18) -> PhysicalNodeScan(n)`

### Filter 节点的作用

Filter 节点用于过滤数据,对应 GQL 中的 `WHERE` 子句:

```gql
MATCH (n:Person) 
WHERE n.age > 18 
RETURN n.name
```

对应的逻辑计划树:

```text
LogicalProject(n.name)
    ↓
LogicalFilter(n.age > 18)
    ↓
LogicalMatch(n:Person)
```

---

## 1. 模块设计与代码结构

### 相关文件

| 文件 | 作用 | 本实验关注点 |
|------|------|-------------|
| `planner/src/logical_planner/query.rs` | 查询语句的逻辑计划生成 | **实现 Filter 节点插入逻辑** |
| `planner/src/plan/filter.rs` | Filter 计划节点定义 | 了解 Filter 结构 |
| `planner/src/plan/mod.rs` | 计划节点枚举 | 了解 PlanNode 类型 |
| `planner/src/bound/mod.rs` | 绑定后的语法树结构 | 了解 predicate 来源 |

### 核心数据结构

```rust
// 计划节点枚举
pub enum PlanNode {
    LogicalMatch(Arc<LogicalMatch>),
    LogicalFilter(Arc<Filter>),
    LogicalProject(Arc<Project>),
    // ... 其他节点类型
}

// Filter 节点定义
pub struct Filter {
    pub child: PlanNode,           // 子节点
    pub predicate: BoundExpression, // 过滤条件表达式
}

// MATCH 语句绑定结果
pub struct BoundMatchStatement {
    Simple(PatternBinding),
    Optional,
}

pub struct PatternBinding {
    pub pattern: BoundGraphPattern,  // 图模式
    pub yield_clause: Option<...>,
    pub output_schema: Schema,
}

// 图模式包含 predicate (WHERE 条件)
pub struct BoundGraphPattern {
    pub paths: Vec<BoundPath>,
    pub predicate: Option<BoundExpression>, // ← WHERE 子句
}
```

---

## 2. 实验任务

### 任务描述

在 `plan_match_statement` 函数中,当 MATCH 语句包含 WHERE 子句时,需要在逻辑计划中添加 Filter 节点。

**文件**: `labs/miniGU/minigu/gql/src/planner/src/logical_planner/query.rs`

**位置**: 第 93-127 行,`plan_match_statement` 函数

### 实现要求

1. 检查 `binding.pattern.predicate` 是否为 `Some`
2. 如果存在 predicate,创建 Filter 节点包装当前 plan
3. 更新 plan 为包装后的节点

### 代码框架

```rust
pub fn plan_match_statement(&self, statement: BoundMatchStatement) -> PlanResult<PlanNode> {
    match statement {
        BoundMatchStatement::Simple(binding) => {
            let match_node = LogicalMatch::new(
                MatchKind::Simple,
                binding.pattern.clone(),
                binding.yield_clause,
                binding.output_schema,
            );
            #[allow(unused_mut)]
            let mut plan = PlanNode::LogicalMatch(Arc::new(match_node));

            // ============================================================
            // LAB 2-1 TODO: Add Filter node support
            // ============================================================
            //
            // 如果 binding.pattern 包含 predicate (WHERE 条件),需要:
            // 1. 检查 binding.pattern.predicate 是否为 Some
            // 2. 如果存在 predicate,创建 Filter 节点包装当前 plan
            // 3. 更新 plan 为包装后的节点
            //
            // 请在下方实现:
            // ============================================================

            // YOUR CODE HERE

            // ============================================================
            // END LAB 2-1 TODO
            // ============================================================

            Ok(plan)
        }
        BoundMatchStatement::Optional => not_implemented("match statement optional", None),
    }
}
```

---

## 3. 测试验证

### 手动测试

完成实现后,可以通过 miniGU 的 EXPLAIN 命令查看生成的逻辑计划:

```bash
# 启动 miniGU
cd labs/miniGU
cargo run

# 在 miniGU shell 中执行
minigu> EXPLAIN MATCH (n:Person) WHERE n.age > 18 RETURN n;
```

**预期输出** (逻辑计划):

```text
LogicalProject
  output: [n]
  ↓
LogicalFilter
  predicate: n.age > 18
  ↓
LogicalMatch
  pattern: (n:Person)
```

### 单元测试

```bash
# 运行 planner 相关测试
cargo test -p minigu-planner --no-fail-fast

# 运行特定测试
cargo test -p minigu-planner test_plan_match_with_filter
```

---

## 4. 一些思考

### 为什么 Filter 在 Match 之上?

计划树是自底向上执行的:

1. Match 节点扫描图数据,产生候选结果
2. Filter 节点过滤不满足条件的数据
3. Project 节点投影需要的列

这样的顺序符合数据流的自然方向。

### Filter 节点何时转换为物理计划?

在优化器 (Optimizer) 阶段,`LogicalFilter` 会被转换为 `PhysicalFilter`,并可能进行优化(如谓词下推,详见 Lab 2-3)。

### 如果有多个 WHERE 条件怎么办?

多个条件会在语义绑定阶段被组合成一个复合表达式 (如 `AND` / `OR`),传递给 Filter 节点的 predicate 是单个 `BoundExpression`,但其内部可能是复合表达式树。

---

## 5. 下一步

完成 Lab 2-1 后,你已经掌握了逻辑计划的基本生成方法。

**Lab 2-2** 将实现 **Expand 和 Project 执行器**,将逻辑计划转换为实际可执行的代码。

**Lab 2-3** 将实现 **谓词下推优化**,提升查询性能。

---

## 6. FAQ

**Q: Filter::new() 的参数顺序是什么?**

A: `Filter::new(child: PlanNode, predicate: BoundExpression)`,先传入子节点,再传入过滤条件。

**Q: 如何调试生成的计划树?**

A: 可以在代码中添加 `println!("{:#?}", plan);` 打印计划树结构,或使用 `EXPLAIN` 命令。
