## LAB 2 图查询

PR进度：

+ Match Done
+ Filter &  WIP
+ Explain WIP

### 基础

+ 实验0（讲解or动手）：介绍链路（词法->语法->Plan->优化->执行）（Lex、winnow、planner、optimizor、executor），示例 `Match n Return n`如何运行（看到plan）

### Filter实现

+ 实验1（动手）：新增 `filter`词法支持、语法支持，可以生成 `match filter`plan
+ 实验2（动手）：`Expand`算子、`Project`算子(select和return)算子

- 往后放：`Varlen Expand`

+ 实验3（动手）：谓词下推，下推 `filter`的 `NodeScanById` <--> 图存储数据结构对应（TP计算vertex-centric），新增算法和优化规则
+ 实验4（讲解）：`pull-based`、`push-based`
