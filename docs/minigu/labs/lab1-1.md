# Lab 1-1 面向 OLTP 内存图存储

在[实验准备](./lab0.md)中我们介绍了数据库系统的经典架构与图数据库的基本概念。存储引擎应具备的核心功能：

- **数据组织与访问**：高效的数据结构组织（B+树、LSM树、邻接表等），支持快速点查和范围扫描。
- **事务管理（ACID）**：原子性、一致性、隔离性、持久性保证，通过锁、MVCC、日志等机制实现。
- **并发控制**：允许多个事务并发执行而不破坏数据一致性，常见策略有锁协议、乐观并发控制、MVCC。
- **持久化与恢复**：通过 WAL（Write-Ahead Logging）保证数据持久性，通过 Checkpoint 加速恢复。
- **索引支持**：加速按属性查找、邻接遍历等操作。

本实验聚焦于一个面向OLTP场景的内存图存储子系统，目标是让你从零到一理解并实现：

- 图数据的组织方式
- 点边访问迭代器
- MVCC基础多版本并发控制
- WAL（Write Ahead Log）与检查点（Checkpoint）

仓库已为本实验“挖空”了若干实现（用 TODO 标记），你需要补齐它们并通过现有测试。完成后，你将具备实现一个支持事务的图内存引擎的初步能力。
与 MVCC 基础实现

---

## 0. 背景知识

本实验聚焦于 **面向OLTP场景的存储引擎**（`minigu/storage/src/tp/`），它为图数据提供**事务性内存存储**能力。

### OLTP 图查询计算模式

OLTP（Online Transaction Processing，在线事务处理）场景强调**低延迟、高并发、小规模事务**。图数据库在 OLTP 场景下的典型查询模式包括：

#### 点查为主的计算模式

这种计算模式以点查为中心(Vertex-centric)，一般根据唯一 ID 快速定位某个顶点或边，获取其属性。例如：

```gql
MATCH (u:User WHERE u.id = 12345)
RETURN u.name, u.age
```

#### 邻接遍历

从某个顶点出发，遍历其直接连接的邻居（1-hop），获取邻边与目标顶点信息。例如：

```gql
MATCH (u:User WHERE u.id = 12345)-[r:FRIEND]->(friend)
RETURN friend.name
```

#### 属性过滤

在遍历过程中，根据边或顶点的属性进行过滤，例如：

```gql
MATCH (u:User WHERE u.id = 12345)-[r:FRIEND WHERE r.since > '2020-01-01']->(friend)
RETURN friend.name
```

#### 多跳遍历与路径查询

从起点沿着边多次跳转，查找 k-hop 邻居或最短路径。例如：

```gql
MATCH (u:User WHERE u.id = 12345)-[:FRIEND*1..3]->(friend)
RETURN friend
```

### 图数据的组织与访问

针对 OLTP 场景的图查询模式，我们可以分析得到：

- 需要高效的点查数据结构，如哈希表（HashMap）或并发哈希表（DashMap）。
- 需要高效的邻接关系存储结构，如邻接表（Adjacency List），并支持按方向（入边/出边）过滤
- 需要支持迭代器模式，避免一次性加载过多数据，属性索引可加速特定条件筛选。

故采用以下存储结构存储内存图

```rust
/// 顶点与边的存储
pub struct MemoryGraph {
    // ---- 支持多版本的图存储 ----
    pub(super) vertices: DashMap<VertexId, VersionedVertex>, // 顶点存储：DashMap<VertexId, VersionedVertex>
    pub(super) edges: DashMap<EdgeId, VersionedEdge>,        // 边存储：DashMap<EdgeId, VersionedEdge>
    // ---- 邻接表 ----
    pub(super) adjacency_list: DashMap<VertexId, AdjacencyContainer>,
    // ---- 事务管理 ----
    pub(super) txn_manager: MemTxnManager,
    // ---- Write-ahead-log为崩溃恢复设计 ----
    pub(super) wal_manager: WalManager,
    // ---- Checkpoint管理 ----
    pub(super) checkpoint_manager: Option<CheckpointManager>,
}
```

其中`AdjacencyContainer`每个顶点维护两个方向的邻接关系：
```rust
pub struct AdjacencyContainer {
    pub incoming: Arc<SkipSet<Neighbor>>,  // 入边邻居
    pub outgoing: Arc<SkipSet<Neighbor>>,  // 出边邻居
}

pub struct Neighbor {
    label_id: LabelId,     // 边标签
    neighbor_id: VertexId, // 对端顶点 ID
    eid: EdgeId,           // 边 ID
}
```

- **DashMap**：高性能并发哈希表，支持无锁读写，适合点查场景。
- **VersionedVertex / VersionedEdge**：封装版本链（VersionChain），每个实体维护当前版本 + Undo 日志，支持 MVCC。

为什么使用 SkipSet？

- **有序性**：按键（label_id, neighbor_id, eid）有序存储，支持范围查询与按标签过滤。
- **高效插入/删除**：平均 O(log n) 复杂度，适合动态图场景。
- **无锁并发**：支持多线程同时读写邻接表。

但注意使用SkipSet的时候，需要考虑重边的场景（即同一对顶点间存在多条边）。我们通过在`Neighbor`结构中加入`eid`字段来区分不同的边，从而允许重边的存在。

### 点边迭代器访问

为了屏蔽底层数据结构细节，图存储引擎通常提供统一的迭代器接口，支持按条件遍历顶点、边及邻接关系。如下是邻接迭代器的核心结构：

```rust
pub struct AdjacencyIterator {
    adj_list: Arc<SkipSet<Neighbor>>,  // 邻接表引用
    current_entries: Vec<Neighbor>,    // 当前批次（最多 BATCH_SIZE 个）
    current_index: usize,              // 批内索引
    filters: Vec<Box<dyn Fn(&Neighbor) -> bool>>, // 过滤条件
}
```

迭代流程：

1. 初始化时调用 `load_next_batch()` 预加载第一批邻居。
2. `next()` 逐个返回当前批次中符合过滤条件的邻居；批次耗尽时自动加载下一批。
3. 支持按 label、方向等条件链式过滤。

**本实验的核心任务之一**：补齐 `adjacency_iterator.rs` 中的批处理逻辑（详见任务 1）。

### MVCC 基础：多版本并发控制

**MVCC（Multi-Version Concurrency Control）** 是现代数据库实现高并发的核心技术，允许读写操作不互相阻塞。

**基本原理**：每个数据对象（顶点/边）维护多个版本，每个版本对应一个事务的修改。读事务根据自己的 **快照时间戳**（start_ts）选择可见的版本，写操作创建新版本。

在 miniGU 中，采用 **Delta-based Undo Versioning**：

```text
VersionChain<D>
  ├── current: CurrentVersion<D>       // 最新版本（可能未提交）
  │     ├── data: D
  │     └── commit_ts: Timestamp       // 提交时间戳（或 txn_id）
  └── undo_ptr: Weak<UndoEntry>        // 指向 Undo 日志链
```

**版本可见性判断**：

- 若 `current.commit_ts <= txn.start_ts`，当前版本对事务可见，直接返回。
- 否则，沿 `undo_ptr` 回溯，应用 Undo Delta 恢复到事务开始前的状态。

#### 读写集与冲突检测

- **读集（Read Set）**：事务读取的所有顶点/边 ID（仅 Serializable 隔离级别跟踪）。
- **写集（Write Set）**：事务修改的对象（通过 Undo Buffer 隐式记录）。

**冲突检测**：

- **读-写冲突**：事务 T1 读取 X，T2 在 T1 提交前修改并提交了 X → T1 提交时验证读集失败。
- **写-写冲突**：T1 和 T2 同时尝试修改 X → 先提交者成功，后者检测到 `commit_ts` 已更新而回滚。

#### 隔离级别

- **Serializable（可串行化）**：最严格，记录读集并在提交时验证，确保等价于串行执行。
- **Snapshot Isolation（快照隔离）**：事务读取开始时的快照，写操作检测写-写冲突。性能更高但可能出现写偏序异常。

**本实验关注点**：理解 `MemTransaction` 的可见性重建（`apply_deltas_for_read`）与提交阶段的读集验证（`validate_read_sets`）。

---

### 0.5 WAL + Checkpoint：日志与检查点机制

为保证数据持久性和崩溃恢复能力，miniGU 实现了经典的 **WAL + Checkpoint** 机制。

#### Write-Ahead Logging (WAL)

**核心思想**：在修改数据前，先将操作写入日志；数据可以延迟刷盘，只要日志持久化即可保证不丢数据。

miniGU 的 WAL 记录格式：

```rust
pub struct RedoEntry {
    lsn: u64,                    // 日志序列号（Log Sequence Number）
    txn_id: Timestamp,           // 事务 ID
    iso_level: IsolationLevel,   // 隔离级别
    op: Operation,               // 操作类型
}

pub enum Operation {
    BeginTransaction(Timestamp),      // 事务开始
    Delta(DeltaOp),                   // 数据修改（正向操作）
    CommitTransaction(Timestamp),     // 事务提交
    AbortTransaction,                 // 事务回滚
}
```

**日志回放（Redo）**：系统重启后，从 WAL 读取 RedoEntry，重放所有已提交事务的操作，恢复到崩溃前的状态。

#### Checkpoint（检查点）

**问题**：随着运行时间增长，WAL 越来越长，回放耗时线性增加。

**解决方案**：定期创建 Checkpoint，将当前内存状态快照化到磁盘，并截断 WAL。

```rust
pub struct GraphCheckpoint {
    metadata: CheckpointMetadata,      // 包含 LSN、commit_ts
    vertices: HashMap<VertexId, SerializedVertex>,
    edges: HashMap<EdgeId, SerializedEdge>,
    adjacency_list: HashMap<VertexId, SerializedAdjacency>,
}
```

#### 崩溃恢复流程

```text
1. 加载最近的 Checkpoint（如果存在）
   ├── 恢复 vertices、edges、adjacency_list
   └── 设置 next_lsn = checkpoint.lsn

2. 回放 WAL 中 lsn >= checkpoint.lsn 的条目
   ├── BeginTransaction: 创建事务对象
   ├── Delta: 调用 create_vertex/delete_edge 等
   ├── CommitTransaction: 提交事务
   └── AbortTransaction: 回滚事务

3. 恢复完成，系统可接受新请求
```

**本实验关注点**：

- `checkpoint.rs` 中 `GraphCheckpoint::new()` 如何快照当前状态。
- `memory_graph.rs` 中 `apply_wal_entries()` 如何回放 RedoEntry。
- 测试 `test_wal_replay` 和 `test_checkpoint_and_wal_recovery` 验证恢复正确性。

---

通过以上背景知识，你应该对 miniGU 存储系统的设计思路有了全面认识。接下来，让我们进入具体的模块设计与实验任务！

---

## 1. 模块总体设计与目录结构说明

TP 存储相关源码位于：`miniGU/minigu/storage/src/tp/`

目录与文件功能速览：

| 文件 | 作用 | 你需要关注的点 |
|------|------|----------------|
| `mod.rs` | 模块入口及类型 re-export | 便于上层统一使用 `MemoryGraph` / `MemTransaction` |
| `memory_graph.rs` | 图的主体：版本化顶点/边、邻接表、增删改查、WAL/Checkpoint 集成 | TODO: 改进 MVCC、冲突检测；理解 `VersionChain`、`UndoEntry` 使用 |
| `transaction.rs` | 事务对象实现：读写集、撤销日志、提交/回滚、可见性重建 | TODO: 扩展 AddLabel/RemoveLabel（选做）、读写冲突处理 |
| `txn_manager.rs` | 事务管理：启动/结束、watermark、GC、垃圾回收策略 | 了解 GC 触发条件，检查你的实现是否影响可见性 |
| `iterators/vertex_iterator.rs` | 顶点迭代器（支持 filter/seek） | 已实现，可作为风格参考 |
| `iterators/edge_iterator.rs` | 边迭代器（支持 filter/seek） | 已实现，可作为风格参考 |
| `iterators/adjacency_iterator.rs` | 邻接迭代器（单顶点 in/out/both 邻居批次遍历） | TODO: 补齐 `next()` 和 `load_next_batch()` 批处理逻辑 |
| `checkpoint.rs` | 检查点的创建/保存/恢复（快照 + 截断 WAL） | 理解恢复流程，便于扩展一致性保证 |

辅助公共模型在 `miniGU/minigu/common/model/` 下：`vertex.rs`, `edge.rs`, `properties` 等定义基础结构；事务时间戳与通用 Undo 在 `minigu_transaction` crate 中。

---

## 2. 核心数据结构与概念解析

### 2.1 Vertex / Edge / Neighbor

顶点与边封装了：ID、标签（LabelId）、属性集合（`PropertyRecord`）以及 tombstone 标记（逻辑删除）。`Neighbor` 结构用于邻接表中存储 (label_id, 对端顶点 id, edge id) 三元信息，支持快速方向遍历。

### 2.2 VersionChain / CurrentVersion

```text
VersionChain<D>
  current: RwLock<CurrentVersion<D>>   // 最新版本（可能还未提交）
  undo_ptr: RwLock<UndoPtr>            // 指向事务撤销日志链首（上一已提交版本的增量）

CurrentVersion<D>
  data: D
  commit_ts: Timestamp  // 若是未提交新写入则为 txn_id；已提交则为 commit_ts
```

这里采用“向后链接”+撤销日志（undo delta）方式，只保留当前版本数据 + 一串可逆 delta。读事务根据自身 `start_ts` 回溯应用必要的 delta 以重建可见版本（见 `MemTransaction::apply_deltas_for_read`）。

### 2.3 UndoEntry / DeltaOp

`UndoEntry` 封装：发生的逻辑反向操作（如 `CreateVertex` 的撤销是 `DelVertex`）、原先时间戳、下一节点指针。`DeltaOp` 枚举定义所有图结构修改：创建/删除点边、属性修改、标签增删（后两者存在 TODO 选做）。WAL 中的 `Operation::Delta(DeltaOp)` 是正向重做条目（RedoEntry）。

### 2.4 Timestamp / IsolationLevel

时间戳生成器保证单调性。两种隔离级别：

- Serializable：记录读集并在提交阶段验证是否被其它事务更新（`validate_read_sets`）。
- Snapshot：不跟踪读集，允许更高并发，靠版本可见性保证一致读。

### 2.5 AdjacencyContainer & SkipSet

每个顶点维护两个 `SkipSet<Neighbor>`：`incoming` 与 `outgoing`。SkipSet 提供近似 O(log n) 插入与有序遍历能力。邻接迭代器需在其上进行批次抓取与过滤。

### 2.6 MemTransaction

保存：读集、undo/redo buffer、`start_ts`、`txn_id`、`commit_ts`。提交时：

1. 验证读集（Serializable）。
2. 将当前版本的 `commit_ts` 更新为真正提交时间戳。
3. 写出 WAL：Undo 不落盘，Redo 正向操作 + Commit/Abort。
4. 更新 TxnManager 的 `latest_commit_ts` 与 watermark，触发自动检查点与 GC 条件。

 
### 2.7 MemTxnManager / GC / Watermark

Watermark = 活跃事务最小 start_ts；无活跃事务则为最新提交时间戳。GC 遍历已提交事务的 undo buffer，挑选在 watermark 之前且不再被任何活动事务可见的对象执行物理清理（边、顶点、邻接关系）。

 
### 2.8 WAL + Checkpoint 协同恢复

恢复两阶段：

1. 加载最近检查点（若存在），恢复快照状态；
2. 回放 WAL 中 checkpoint LSN 之后的 redo 条目，保证最终一致性。若无检查点，则直接从空图 + 全量 WAL 重建。

---
 
## 3. 挖空位置与需补齐的接口列表

必须完成：

1. `iterators/adjacency_iterator.rs`：实现 `Iterator for AdjacencyIterator::next()` 与 `load_next_batch()` 批处理逻辑，使相关测试（`test_adjacency_versioning`, `test_adj_iterator`, 以及涉及 adjacency 可见性统计的测试）通过。
2. `memory_graph.rs` 中 MVCC TODO：为 `VersionedVertex::with_txn_id` / `VersionedEdge::with_modified_ts` 对象的版本链完善后续扩展接口（若需要，可新增辅助方法保证可读性）。
3. `memory_graph.rs` 顶部的 `check_write_conflict`（当前空实现）——在属性更新等写操作前检测与其它事务的写冲突（可在 `set_vertex_property` / `set_edge_property` 调用之前插入）。

 
选做扩展：
4. 支持 `DeltaOp::AddLabel` 与 `DeltaOp::RemoveLabel`（完善枚举分支、WAL 写入、Undo 语义、提交/回滚分支）。
5. 引入批量迭代的统计信息（预估下一批大小 / hint）以优化交互（加入简单的 metrics 结构）。
6. 为 GC 引入分阶段清理：先标记后压缩，避免长事务阻塞大量物理删除。

---
 
## 4. 实验任务分解与实现指导

 
### 任务 1：实现邻接迭代器批处理

文件：`iterators/adjacency_iterator.rs`

需求：

1. `next()` 能遍历全部邻居，并结合 `filters`。当当前批次耗尽自动加载下一批。
2. `load_next_batch()` 将 `adj_list` 中剩余元素抓取至 `current_entries`，最多 `BATCH_SIZE` 个；重置 `current_index=0`；返回是否抓取成功。
3. 需保持遍历有序（SkipSet 本身按键有序）；过滤后仍需正确推进。
4. 记录当前条目于 `current_adj` 以支持上层接口 (`current_entry()`).

 
伪代码参考：

```rust
fn next(&mut self) -> Option<Result<Neighbor, StorageError>> {
  loop {
    if self.current_index >= self.current_entries.len() {
      if self.load_next_batch().is_none() { self.current_adj=None; return None; }
    }
    let cand = self.current_entries[self.current_index].clone();
    self.current_index += 1;
    if self.filters.iter().all(|f| f(&cand)) {
      self.current_adj = Some(cand.clone());
      return Some(Ok(cand));
    }
  }
}
```
 
注意：逻辑删除（tombstone）不在邻接级别直接体现，需依赖 edge 可见性；若要增强，可在迭代时读取对应 edge 并跳过 tombstone（扩展）。

 
### 任务 2：补全 MVCC 改进（可见性与版本链帮助函数）

建议新增（示例，不强制）：

```rust
impl VersionedVertex { pub fn commit_ts(&self)->Timestamp { self.chain.current.read().unwrap().commit_ts } }
impl VersionedEdge { pub fn commit_ts(&self)->Timestamp { ... } }
```
 
并在读取/写入路径中调用统一的可见性判断函数，减少重复条件逻辑，便于未来扩展 Snapshot 隔离下的优化。

 
### 任务 3：实现写冲突检测 `check_write_conflict`

触发时机：在写操作（创建、删除、属性更新）前调用。
 
冲突判定示例：

```text
若目标实体 current.commit_ts 是其他活跃事务的 txn_id（未提交）且 != 当前事务 txn_id，则写冲突。
若 current.commit_ts 为已提交时间戳且 > 当前事务 start_ts，表示该事务开始后被其他事务提交更新，也视为冲突（Serializable 下）。
```
 
处理策略：返回 `StorageError::Transaction(TransactionError::WriteWriteConflict(...))` 或复用 `ReadWriteConflict`（自行在错误枚举中扩展更准确的名称是加分项）。

 
### 任务 4（选做）：标签增删操作语义

1. 在 `DeltaOp` 中完整支持 Add/RemoveLabel（已经占位）。
2. WAL 与 Undo：AddLabel 的撤销是 RemoveLabel；RemoveLabel 的撤销是 AddLabel（需保存必要属性/旧标签集合）。
3. 修改提交/回滚分支匹配：`transaction.rs` 与 `memory_graph.rs` 中 `match undo_entry.delta()` / WAL replay。

### 任务 5（选做）：GC 改进与性能观察

添加简单计数或时间统计：记录 GC 耗时、每次清理对象数量（在 `garbage_collect` 开头/结尾打印或存指标）。

---

## 5. 测试、验证与评估标准

仓库已提供大量单元测试（主要在 `memory_graph.rs` / `transaction.rs` / `checkpoint.rs` 的 `#[cfg(test)]` 模块内）。补齐实现后需全部通过以下关键测试：

必过：

- `test_adjacency_versioning`
- `test_adj_iterator`
- `test_delete_with_tombstone`
- `test_garbage_collection_after_delete_edge`
- `test_garbage_collection_after_delete_vertex`
- `test_wal_replay` / `test_checkpoint_and_wal_recovery`

建议自写附加测试：

1. 并发两个事务对同一顶点属性写入（模拟冲突）应返回错误。
2. Snapshot 隔离下读旧版本 + 另一事务更新并提交，不应看到新值。
3. 邻接迭代过滤：只遍历指定 label 的邻居。

评估维度：

| 维度 | 要求 |
|------|------|
| 正确性 | 通过所有必需测试；无 panic；并发场景行为符合描述 |
| 可维护性 | 代码注释清晰；关键函数有简洁文档注释；无重复逻辑 |
| 性能基础 | 邻接迭代无明显退化（批处理生效），不频繁分配大向量 |
| 扩展性 | 结构设计便于加入更多 Delta 操作与索引 |

---

## 6. 提交与验收要求

1. 补齐所有 TODO；新增方法需保持命名语义清晰（英文）。
2. 不随意更改已有已通过测试的公共接口签名（避免破坏后续 Lab）。
3. 新增的错误类型或枚举分支需给出简短注释。
4. 所有测试通过（`cargo test -p minigu_storage` 或项目根 `cargo test`）。
5. 在 PR 描述中列出：实现点、遇到的问题、扩展项（若有）。

---

## 7. 常见坑与提示

| 问题 | 提示 |
|------|------|
| 邻接迭代始终空 | 检查 `load_next_batch` 是否真正填充 `current_entries`；是否忘记预加载第一批 |
| 读写冲突未触发 | 是否在写路径调用了 `check_write_conflict`；commit_ts 与 txn_id 语义区分是否正确 |
| GC 不清理 tombstone | Watermark 是否提升；是否有长事务未结束；是否正确把 undo entries 收集到 expired 列表 |
| Snapshot 隔离读到新值 | 回溯逻辑是否对 `commit_ts > start_ts` 情况应用了 delta 恢复旧版本 |
| WAL 重放失败 | 确认 WAL replay 中的 delta 顺序与写入时一致；“挖空”分支是否全部补齐 |

调试技巧：

1. 为关键路径加 `trace!` 日志（确保启用 `RUST_LOG=trace`）。
2. 使用 `cargo test -- --nocapture` 观察事务提交/回滚顺序。
3. 对迭代器先写一个最小实现跑测试定位断点，再逐步优化。

---

## 8. 扩展挑战（可选加分）

1. 实现边 / 顶点的“轻量索引”以加速按属性过滤（维护一个 `DashMap<PropValue, Vec<VertexId>>`）。
2. 引入读版本缓存：对高频访问顶点维护最近可见版本，减少多次回溯。
3. 支持批量写入事务（导入模式），并在 WAL 中做压缩（合并连续属性修改）。
4. 设计简单性能基准：随机生成 N 个顶点和 M 条边，比较批处理前后迭代耗时。

---

## 9. 里程碑与建议时间安排

| 天数 | 目标 |
|------|------|
| Day 1 | 通读源码，完成邻接迭代器基本逻辑 |
| Day 2 | 写冲突检测 & MVCC 可见性梳理；通过基础 CRUD 测试 |
| Day 3 | GC 行为验证；通过恢复相关测试 |
| Day 4 | 扩展任务（标签操作 / 性能优化）|
| Day 5 | 自写补充测试与文档完善，提交 PR |

---

## 10. 参考与进一步学习

推荐阅读：

1. “An Empirical Evaluation of In-Memory Multi-Version Concurrency Control” 了解不同 MVCC 设计取舍。
2. PostgreSQL Heap + Undo 机制概览（与本实验的 version chain 思路类比）。
3. SkipList 数据结构原理（理解跨层搜索与有序性保证）。

完成本 Lab 后，你应能：

- 解释基于撤销日志的 MVCC 读可见性流程。
- 手写一个批处理迭代器并在并发容器上保持正确性。
- 描述 WAL + Checkpoint 恢复的两个阶段与边界条件。

祝你实验顺利，写代码前先理清数据结构之间的“时间”与“引用”关系，能让你少踩很多坑！
