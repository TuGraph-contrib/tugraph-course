# 贡献指南

感谢你对 TuGraph Course 项目的关注！我们欢迎任何形式的贡献，无论是报告问题、提出建议、完善文档，还是提交代码。

## 📋 贡献方式

### 提交Issue

如果你在使用过程中发现了问题或有改进建议：

1. 前往 [Issues 页面](https://github.com/TuGraph-contrib/tugraph-course/issues)
2. 点击 "New Issue" 创建新问题
3. 选择合适的问题模板（Bug Report 或 Feature Request）
4. 详细描述问题或建议

### 完善文档

文档是项目的重要组成部分，你可以通过以下方式改进文档：

- 修正错别字或格式问题
- 补充缺失的内容
- 改进示例代码
- 翻译文档
- 添加使用技巧和最佳实践

### 贡献代码

我们欢迎你提交代码来修复Bug、实现新功能或优化性能。

## 🔧 开发流程

### 第一步：Fork 仓库

1. 访问 [TuGraph Course 仓库](https://github.com/TuGraph-contrib/tugraph-course)
2. 点击右上角的 "Fork" 按钮，将仓库 Fork 到你的 GitHub 账号下
3. Clone 你 Fork 的仓库到本地：

```bash
git clone https://github.com/YOUR_USERNAME/tugraph-course.git
cd tugraph-course
```

### 第二步：创建分支

为你的修改创建一个新分支，分支命名建议：

- `feature/功能描述` - 新功能
- `fix/问题描述` - Bug 修复
- `docs/文档描述` - 文档改进
- `refactor/重构描述` - 代码重构

```bash
git checkout -b feature/your-feature-name
```

### 第三步：进行修改

#### 对于文档修改

1. 确保已安装 MkDocs：

   ```bash
   pip install mkdocs mkdocs-material
   ```
2. 修改 Markdown 文件
3. 本地预览：

   ```bash
   mkdocs serve
   ```

   访问 http://127.0.0.1:8000/ 查看效果
4. 提交修改：

   ```bash
   git add .
   git commit -m "描述你的修改"
   ```

## 📞 联系方式

如有任何问题，欢迎通过以下方式联系我们：

- **GitHub Issues**: [提交问题](https://github.com/TuGraph-contrib/tugraph-course/issues)
- **Pull Requests**: [提交代码](https://github.com/TuGraph-contrib/tugraph-course/pulls)
- **TuGraph 社区**: 访问 [TuGraph 官网](https://tugraph.tech)

## 🙏 致谢

感谢所有为本项目做出贡献的开发者、文档编写者和问题报告者！你们的每一份贡献都让这个项目变得更好。以下是部分贡献者名单（按字母顺序排列）：

TODO: 添加贡献者名单

---

让我们一起构建更好的图数据库学习平台！🚀
