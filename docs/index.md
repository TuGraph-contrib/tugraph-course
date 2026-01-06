# TuGraph 图计算课程

欢迎来到 TuGraph 图计算技术课程系列!

本课程由 [TuGraph](https://tugraph.tech) 团队联合多所高校共同打造，旨在为零基础的同学提供系统化的图计算技术相关技术的学习路径。

## 课程简介

本课程包含多个图计算技术方面的内容：

- MiniGU图数据库开发实战系列
    - 项目介绍与快速上手
    - 设计文档与 Rust 语言基础
    - 图数据库开发实践指南
- TuGraph-DB图查询与图算法实验系列
    - TuGraph-DB项目介绍
    - TuGraph-DB图算法与图查询实验指南
- Apache GeaFlow系列
    - GeaFlow 完整介绍
- Graph+AI技术系列介绍
    - Chat2Graph 图原生智能体系统介绍

## 课程内容

### MiniGU 系列

MiniGU 是一个使用 Rust 语言实现的轻量级嵌入式图数据库，专为图数据库入门学习设计。通过学习 MiniGU，你将掌握图数据库的核心概念与基本原理，学习使用 Rust 语言进行系统级开发、理解图数据存储，查询与计算的实现机制，通过动手实践深入了解图数据库的内部工作原理。

- **[项目介绍](minigu/introduction.md)** - 了解 MiniGU 的设计理念与学习目标
- **[快速上手](minigu/quick-start.md)** - 配置开发环境，编译运行 MiniGU
- **[设计文档](minigu/design.md)** - 深入理解 MiniGU 的架构设计
- **[Rust 语言基础](minigu/rust.md)** - 学习 Rust 编程必备知识
- **[实验指南](minigu/labs/lab0.md)** - 通过动手实验掌握核心概念
- **图存储实验**：**[Lab 1-1 OLTP图存储开发实验](labs/lab1-1.md)** 和 **[Lab 1-2 OLAP图存储开发实验](labs/lab1-2.md)**
- **图查询实验**：**[Lab 2-0 图查询系列实验概览](labs/lab2-0.md)**
- **[附录](minigu/appendix.md)** - 参考资料供扩展学习和阅读

### TuGraph-DB 系列

基于图数据库 TuGraph-DB 的实践课程，学习企业级图数据库的使用。TuGraph-DB 是由蚂蚁集团与清华大学联合研发的高性能图数据库，在金融风控、工业制造、智慧城市等领域有广泛应用。

- **[TuGraph-DB 完整介绍](tugraph/tugraph.md)** - 全面了解 TuGraph-DB 的架构、特性与应用场景
- **[图查询与图算法实验指南](tugraph/labs/lab0.md)** - 基于 TuGraph-DB 的图查询与图算法实践
- **[基于 TuGraph-DB 的社区检测实验](tugraph/labs/lab1.md)** - 使用 Louvain 算法实现社区检测
- **[基于 TuGraph-DB 的链路预测实验](tugraph/labs/lab2.md)** - 使用 Node2Vec 算法实现链路预测
- **[图查询Cypher实践：基于微服务监测数据的异常分析建模及应用](tugraph/labs/cypher.md)** - 基于微服务监测数据的异常分析建模及 Cypher 查询实践

<!-- 基于工业级图数据库 TuGraph 的实践项目，包含多个图数据挖掘任务：
- **Phase 1**: TuGraph 环境搭建与 Python API 使用
- **Phase 2**: 使用 Louvain 算法实现社区检测
- **Phase 3**: 使用 Node2Vec 算法实现链路预测
-->

### Apache Geaflow 系列

Apache GeaFlow 是蚂蚁集团开源的性能世界一流的 OLAP 图数据库，支持万亿级图存储、图表混合处理、实时图计算、交互式图分析等核心能力。通过学习 GeaFlow，你将理解流图计算的核心原理，掌握实时图计算的应用场景。

- **[GeaFlow 完整介绍](geaflow/geaflow.md)** - 全面了解 GeaFlow 的架构、特性与应用场景
- 其他内容敬请期待

### Graph+AI 技术系列

探索图计算与人工智能的深度融合，通过「图智互融」技术实现图数据库的智能化。

- **[Chat2Graph](graphai/chat2graph.md)** - 图原生智能体系统，实现与图对话
- 其他内容敬请期待

### 关于

- **[Contributing](about/contributing.md)** - 了解贡献者列表以及如何参与课程内容的贡献
- **[Roadmap](about/roadmap.md)** - 了解本课程后续的迭代计划

## 学习建议

1. **循序渐进**: 建议按照文档顺序学习，先掌握基础概念再进行实践
2. **动手实践**: 图数据库的学习重在实践，请务必完成每个实验
3. **理解原理**: 不仅要知道怎么用，更要理解背后的实现原理
4. **善用工具**: 充分利用现代开发工具和 AI 编程助手，但要确保理解代码逻辑

## 其他推荐资源

- 获取其他TuGraph社区相关资源：[TuGraph 官网](https://tugraph.tech)、[TuGraph GitHub](https://github.com/TuGraph-family/tugraph-db)
- 优秀数据库开发技术资源推荐：[MiniOB](https://oceanbase.github.io/miniob/)数据库入门学习项目
- 优秀图技术课程资源推荐：北京大学《大规模图数据管理与分析》公开课程，可**微信公众号**和**B站**搜索关注“图谱学苑”获取视频资源

---

开始你的图计算技术学习之旅吧！如有问题，欢迎在 GitHub 仓库提 Issue 讨论。
