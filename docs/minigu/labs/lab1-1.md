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

## 0. 背景知识与设计原理

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

### 点边迭代器接口设计

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

基本原理：每个数据对象（顶点/边）基于时间戳(timestamp)维护多个版本，每个版本对应一个事务的修改。读事务根据自己的 **快照时间戳**（start_ts）选择可见的版本，写操作创建新版本。

```text
VersionChain<D>
  ├── current: CurrentVersion<D>       // 最新版本（可能未提交）
  │     ├── data: D
  │     └── commit_ts: Timestamp       // 提交时间戳（或 txn_id）
  └── undo_ptr: Weak<UndoEntry>        // 指向 Undo 日志链
```

版本可见性判断：

- 若 `current.commit_ts <= txn.start_ts`，当前版本对事务可见，直接返回。
- 否则，沿 `undo_ptr` 回溯，应用 Undo Delta 恢复到事务开始前的状态。

冲突检测：

- **读-写冲突**：事务 T1 读取 X，T2 在 T1 提交前修改并提交了 X → T1 提交时验证读集失败。
- **写-写冲突**：T1 和 T2 同时尝试修改 X → 先提交者成功，后者检测到 `commit_ts` 已更新而回滚。

### WAL + Checkpoint：日志与检查点机制

为保证数据持久性和崩溃恢复能力，miniGU 实现了经典的 **WAL + Checkpoint** 机制。

**Write-Ahead Logging (WAL)核心思想**：在修改数据前，先将操作写入日志；数据可以延迟刷盘，只要日志持久化即可保证不丢数据。

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

但存在的问题：随着运行时间增长，WAL 越来越长，回放耗时线性增加。解决方案是：定期创建 Checkpoint，将当前内存状态快照化到磁盘，并截断 WAL。

```rust
pub struct GraphCheckpoint {
    metadata: CheckpointMetadata,      // 包含 LSN、commit_ts
    vertices: HashMap<VertexId, SerializedVertex>,
    edges: HashMap<EdgeId, SerializedEdge>,
    adjacency_list: HashMap<VertexId, SerializedAdjacency>,
}
```

**崩溃恢复流程**：

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

---

通过以上背景知识，你应该对 miniGU 存储系统的设计思路有了全面认识。接下来，让我们进入具体的模块设计与实验任务！

---

## 1. 模块设计与目录结构说明

OLTP 图存储相关源码位于：`miniGU/minigu/storage/src/tp/`，目录与文件功能如下：

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

数据模型在 `miniGU/minigu/common/model/` 下：`vertex.rs`, `edge.rs`, `properties` 等定义基础结构；事务时间戳与通用 Undo 在 `minigu_transaction` crate 中。

---

## 2. 核心数据结构与概念解析

### 2.1 Vertex / Edge / Neighbor

顶点与边封装了：ID、标签（LabelId）、属性集合（`PropertyRecord`）以及 tombstone 标记（逻辑删除）。`Neighbor` 结构用于邻接表中存储 (label_id, 对端顶点 id, edge id) 三元信息，支持快速方向遍历。

### 2.2 VersionChain 与 CurrentVersion

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

### 2.4 AdjacencyContainer & SkipSet

每个顶点维护两个 `SkipSet<Neighbor>`：`incoming` 与 `outgoing`。SkipSet 提供近似 O(log n) 插入与有序遍历能力。邻接迭代器需在其上进行批次抓取与过滤。

### 2.5 MemTransaction

保存：读集、undo/redo buffer、`start_ts`、`txn_id`、`commit_ts`。提交时：

1. 验证读集（Serializable）。
2. 将当前版本的 `commit_ts` 更新为真正提交时间戳。
3. 写出 WAL：Undo 不落盘，Redo 正向操作 + Commit/Abort。
4. 更新 TxnManager 的 `latest_commit_ts` 与 watermark，触发自动检查点与 GC 条件。

 
### 2.6 MemTxnManager / GC / Watermark

Watermark = 活跃事务最小 start_ts；无活跃事务则为最新提交时间戳。GC 遍历已提交事务的 undo buffer，挑选在 watermark 之前且不再被任何活动事务可见的对象执行物理清理（边、顶点、邻接关系）。

 
### 2.7 WAL + Checkpoint 协同恢复

恢复两阶段：

1. 加载最近检查点（若存在），恢复快照状态；
2. 回放 WAL 中 checkpoint LSN 之后的 redo 条目，保证最终一致性。若无检查点，则直接从空图 + 全量 WAL 重建。

---
 
## 3. 需实现的接口列表

- `iterators/adjacency_iterator.rs`：实现 `Iterator for AdjacencyIterator::next()` 与 `load_next_batch()` 批处理逻辑，使相关测试（`test_adjacency_versioning`, `test_adj_iterator`, 以及涉及 adjacency 可见性统计的测试）通过。
- `memory_graph.rs` 中 MVCC TODO：为 `VersionedVertex::with_txn_id` / `VersionedEdge::with_modified_ts` 对象的版本链完善后续扩展接口（若需要，可新增辅助方法保证可读性）。
- `memory_graph.rs` 顶部的 `check_write_conflict`（当前空实现）——在属性更新等写操作前检测与其它事务的写冲突（可在 `set_vertex_property` / `set_edge_property` 调用之前插入）。

---
 
## 4. 实验任务分解与实现指导
 
### 任务 1：实现邻接迭代器批处理

文件：`iterators/adjacency_iterator.rs`，需求：

1. `next()` 能遍历全部邻居，并结合 `filters`。当当前批次耗尽自动加载下一批。
2. `load_next_batch()` 将 `adj_list` 中剩余元素抓取至 `current_entries`，最多 `BATCH_SIZE` 个；重置 `current_index=0`；返回是否抓取成功。
3. 需保持遍历有序（SkipSet 本身按键有序）；过滤后仍需正确推进。
4. 记录当前条目于 `current_adj` 以支持上层接口 (`current_entry()`).

 
### 任务 2： MVCC 补全

建议新增（示例，不强制）：

```rust
impl VersionedVertex { pub fn commit_ts(&self)->Timestamp { self.chain.current.read().unwrap().commit_ts } }
impl VersionedEdge { pub fn commit_ts(&self)->Timestamp { ... } }
```
 
并在读取/写入路径中调用统一的可见性判断函数，减少重复条件逻辑，便于未来扩展 Snapshot 隔离下的优化。

实现写冲突检测 `check_write_conflict`

触发时机：在写操作（创建、删除、属性更新）前调用。
 
冲突判定示例：

```text
若目标实体 current.commit_ts 是其他活跃事务的 txn_id（未提交）且 != 当前事务 txn_id，则写冲突。
若 current.commit_ts 为已提交时间戳且 > 当前事务 start_ts，表示该事务开始后被其他事务提交更新，也视为冲突（Serializable 下）。
```
 
处理策略：返回 `StorageError::Transaction(TransactionError::WriteWriteConflict(...))` 或复用 `ReadWriteConflict`（自行在错误枚举中扩展更准确的名称是加分项）。

---

## 5. 测试、验证与评估标准

仓库已提供大量单元测试（主要在 `memory_graph.rs` / `transaction.rs` / `checkpoint.rs` 的 `#[cfg(test)]` 模块内，以及
`storage/test/`目录下）。

补齐实现后需全部通过测试，可以通过以下命令运行：

```bash
cargo test
# 或通过以下命令
cargo test -p minigu_storage --no-fail-fast
```

**若全部测试通过，则说明实现效果符合预期**

---

## 6. 提交与验收要求

敬请期待

---

## 7. FAQ

敬请期待
