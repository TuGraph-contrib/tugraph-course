# TuGraph Course

本仓库中包含学习TuGraph技术栈相关的课程资源，访问[网页](https://tugraph-contrib.github.io/tugraph-course)获取更多信息。

# 资料列表

## docs

Docs目录下包含课程的主要文档资源，对应[网页](https://tugraph-contrib.github.io/tugraph-course)上展示的内容

## misc

misc文件下包含一些零散的资源，包括配置 TuGraph Docker 容器的操作指南，以及 2 份图数据挖掘相关的作业（使用 Louvain 算法的
社区检测，以及使用 Node2Vec 算法的链路预测）。仓库中的模板代码原用于上海交通大学 AI3602 数据挖掘课程的编程作业。

- `assignment_releases/` 包括编程作业的模板代码。图数据的编程作业分为三个阶段。详细说明请参考各个阶段目录下的 `README` 文件
  - `phase1_tugraph_setup/`. 编程任务的第 1 阶段主要是配置 TuGraph 开发环境，了解调用 TuGraph 内置算子的方法，以及使用 TuGraph 的 Python API 进行开发的流程
  - `phase2_louvain_community_detection/`. 编程任务的第 2 阶段是基于 TuGraph 用 Python 实现 Louvain 社区检测算法
  - `phase3_node2vec_link_prediction/`. 编程任务的第 3 阶段是基于 TuGraph 用 Python 实现 Node2Vec 算法，并将其用于链路预测
- `autograding/` 包括自动评分脚本和自动代码查重脚本
- `zips/` 包括三次作业的压缩包和自动评分脚本的压缩包，便于下载和发布