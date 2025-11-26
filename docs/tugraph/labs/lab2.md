# Lab 2 Node2Vec实验

> **实验相关的代码和数据在`${PROJECT_ROOT}/labs/tugraph/lab2`中**

本实验将实现 **Node2Vec** 算法来进行节点嵌入（node embedding），并使用该嵌入进行 **链路预测（Link Prediction）** 任务。驱动代码和算法框架已提供，你需要补全一些关键部分。

## 简介

### 数据集

给定一个 **无向图**，包含 **16,863 个节点** 和 **46,116 条边**。本实验使用 Node2Vec 算法学习该图的节点嵌入，并使用这些嵌入在给定测试集上进行链路预测。测试集包含 **10,246** 个 (`src`, `dst`) 节点对（从原始图中采样得到）。你需要预测每一对节点之间存在一条边的概率。

数据文件（位于 `p3_data/` 目录）包括：

1. `p3.conf`、`p3_vertices.csv`、`p3_edges.csv`：数据集，你需要将其导入 TuGraph 数据库。
2. `p3_test.csv`： 测试数据，格式为 `id, src, dst`。要求对每一对 (`src`, `dst`) 输出边存在的概率。
3. `label_reference.csv`： 含 300 条标签的验证集，可用于调优算法并自查。

### 环境

TuGraph-DB Docker 设置方法参考[lab0](./lab0.md)文档。

**注意**：需要 Python 3.6，且版本必须 **完全匹配 3.6.x**。

提供的 Docker 镜像自带 Miniconda，你可以用 `conda` 创建环境。

本项目还需要安装 `torch`、`scikit-learn` 和 `tqdm`，由于 Python 3.6 不支持新版 PyTorch，我们使用 `PyTorch 1.10`（CPU 版）：  

```sh
conda install pytorch==1.10.1 cpuonly -c pytorch
conda install scikit-learn
conda install tqdm
```

- 注意：使用 **CPU 版 PyTorch**（Docker 环境无 CUDA 支持）。数据和模型较小，CPU 即可运行。
- 你可以安装其他包，但**禁止使用现成的 Node2Vec 实现**（如 `gensim` 的 `Word2Vec`、`pytorch-geometric` 的 `Node2Vec`）。

### 文件说明

- `data_utils.py`： 链路预测的 PyTorch `Dataset` 和对应的 `collator`。
- `loss.py`： 负采样损失（Negative Sampling Loss），需要你补全实现。
- `walker.py`： 偏置随机游走器（biased random walker），需要你补全实现。
- `metrics.py`： 计算 AUC 的函数。
- `model.py`： 简单 Node2Vec 模型与 Sigmoid 分类器。
- `node2vec_trainer.py`： Node2Vec 训练过程（已完成，可自行调整）。
- `p3_main.py`： 主程序入口：加载数据、训练 Node2Vec、做链路预测并存储结果。


## 任务

### 任务一：将数据导入 TuGraph 数据库

> 相关文件：`import_data.sh`

1. 将提供的图数据转换为 TuGraph 数据库。  
   - 数据已按 `lgraph_import` 格式准备好，位于 `p3_data/` 目录。
   - 用 `lgraph_import` 在 `/root/tugraph-db/build/outputs/` 下创建数据库，路径为 `/root/tugraph-db/build/outputs/p3_db`，图名为 `default`。
   - 可参考 `import_data.sh` 脚本。

### 任务二：实现偏置随机游走算法

> 相关文件：`walker.py`

完成 **Biased Random Walker**：

1. **完成 `walker.py` 中 `BiasedRandomWalker` 的 `get_probs_biased()` 方法**  
   - 计算偏置随机游走的转移概率。
   - 代码内有详细注释和提示。
2. **完成 `BiasedRandomWalker` 的 `walk()` 方法**  
   - 执行一次随机游走并返回轨迹。

此任务需要用到 TuGraph Python API，可参考[lab0](./lab0.md)中相关文档。

### 任务三：实现负采样损失

> 相关文件：`loss.py`

1. **完成 `NegativeSamplingLoss` 类的 `forward()` 方法**  
   - 计算负采样损失。

**注意**：在实践中，即使严格按公式实现，损失有时也可能变成 `NaN` 或导致模型退化，你需要自行考虑如何避免。


### 任务四：超参数调优

> 相关文件：`p3_main.py`、`node2vec_trainer.py`、`run.sh`

我们提供了默认超参数（优化器、学习率、随机游走长度、参数 $p, q$ 等），以及一个非常简单的分类器（点积 + Sigmoid）用于链路预测。默认参数在验证集上的 AUC 约为 0.85。

默认参数不是最优的，你需要调参来提升性能。建议尝试：

1. **调整随机游走参数**：包括游走长度、窗口大小、$p$、$q$。
2. **调整负采样数量**（默认 1）。
3. **尝试不同优化器和学习率**（默认 RMSProp + 1e-2）。
4. **尝试更好的分类器**（如 `sklearn` LogisticRegression，或 `torch` MLP）。

> 提示：合理调参，即使用简单分类器，AUC 也可达到 >0.95。

建议在 `run.sh` 中将参数通过命令行传入，确保可复现。

### 运行程序

与[lab1](./lab1.md)类似，在 `/root/tugraph-db/build/output/` 下为 `p3_main.py` 创建符号链接，并在此运行。提供的 `run.sh` 可一键运行：

```sh
source run.sh
# 或
bash run.sh
```

### 任务要求

1. **禁止使用现成 Node2Vec/链路预测 API**。
2. **禁止使用图神经网络（GNN）**。
3. **必须使用 TuGraph API**，不能直接从 CSV 读数据，也不能用 `networkx` 或自行构建的图结构。
4. **禁止修改标注为 `XXX: Do NOT change...` 的函数**。
5. 其他函数可随意修改、增加或删除，但需保证自包含。
6. **禁止抄袭**，引用需注明来源。
7. 确保代码可运行且结果可复现。

## 参考文献

1. Grover, Aditya, and Jure Leskovec. "Node2vec: Scalable feature learning for networks." KDD 2016.
2. Perozzi, Bryan, et al. "DeepWalk: Online learning of social representations." KDD 2014.
3. [PyTorch Geometric | Node2Vec](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.nn.models.Node2Vec.html)