# HW2 自动查重与评分脚本

## 批量解包

请使用 `batch_unzip.py` 批量解压 Canvas 下载的编程作业

## 代码查重

使用查重脚本前，请先编译 tree-sitter-python parser

```sh
cd codebleu/cb_parser
git clone https://github.com/tree-sitter/tree-sitter-python.git
python build.py
```

- 使用 `codebleu_plagiarism.py` 可进行代码查重
  - 请配置 `codebleu_plagiarism.py` 中的 `FUNCS_TO_CHECK` 和 `WHITE_LIST` 变量
  - `FUNCS_TO_CHECK` 用于指定某个文件的某个函数进行查重
  - `WHILTE_LIST` 用于指定仅对特定学生进行查重，如果为 `None` 则检查所有学生

```py
    # 解压后的同学作业需要在 WORKDIR 下
    WORKDIR = "./student_files"
    # 扫描时会跳过以下文件夹
    IGNORE_DIRS = [
        "logs",
        "zips",
        "data",
        "parser",
        "grader",
        "codebleu",
        "sandbox",
        "__pycache__",
    ]
    # 检查如下三个文件中的三个函数
    FUNCS_TO_CHECK = [
        ("loss.py", "forward"),
        ("model.py", "code_features"),
        ("method_invocation_visitor.py", "_dfs_method_invocation"),
    ]
    # CodeBLEU 分数大于 THRESHOLD 时会认为重复率较高。但是一般建议多次作业重复率都很高（接近 1.0）的时候，再考虑列为代码雷同，同时建议配合人工复查。
    THRESHOLD = 0.85
    # 如果 WHITE_LIST 不为 None，则只检查给定的同学。一般设置为 None，但是如果个别同学迟交了，则可以通过 WHITE_LIST 只检查迟交的同学
    WHILE_LIST = ["张三", "李四"]
```

## 自动评阅

### 静态检测

- `hw*_static.py` 是静态自动评分脚本，脚本会遍历每位同学，扫描同学们提供的 prediction 或代码运行结果，并根据 ground truth 给出评分，结果将记录在 log 文件中
- 仅部分任务（Community Detection 和 Link Prediction 的最终输出）支持静态检测
- 静态检测速度更快，但是请注意，由于静态检测不会实际执行同学们的代码，其评分结果可能不完全可靠；因此建议动态和静态都跑一遍，对比结果
  - 例如，部分同学提交的作业中可能没有包括 prediction 文件，这会导致评分时找不到目标文件
  - 再例如，同学 A 可以直接从同学 B 处复制黏贴一份 prediction，静态检测不会发现这类异常

### 动态运行

- `hw*_dynamic.py` 是自动评分脚本，脚本会遍历每位同学，将其代码（和助教提供的数据集、测试用例等）复制到指定目录下，运行程序，检查结果，并将评分记录在 log 文件中
- 使用前请将对应的数据集（HW2P2的 `p2_data`，HW2P3的 `p3_data`）置于工作目录下，评分脚本会使用助教提供的数据集覆盖同学们原有的数据集
  - 一方面，同学们提交的作业文件里可能不包括数据集，另一方面，也是为了防止数据集被篡改

- 然后请配置对应的评阅脚本，以 HW2P2 Louvain 为例

```py
    # META_NAME 是一个自定义的名字，用于区分不同作业/不同运行
    META_NAME = "hw2p2-louvain-dynamic"
    # NOTE: this is the path in the docker container
    # 动态运行时，我们会把同学的代码复制到 SANDBOX_DIR 中执行
    # 由于 HW2 涉及 Docker，部分 SANDBOX 路径是 Docker Container 内的绝对路径
    SANDBOX_DIR = "/root/ai3602/p2_CommunityDetection"
    # BLACK_LIST 中的文件夹不会被检查（例如部分同学的神奇代码可能导致脚本卡死，则建议将这些同学先列入 BLACK_LIST，回头单独跑）
    BLACK_LIST = None
    # WHITE_LIST 如果不为 None，则只运行 WHITE_LIST 的目录，例如少数同学晚交时，可以指定 WHITE_LIST，只运行晚交的同学的代码
    WHITE_LIST = None
```