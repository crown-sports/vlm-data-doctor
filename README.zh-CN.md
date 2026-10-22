# VLM Data Doctor

训练前定位图文数据问题，生成能追溯来源、复核重叠的训练／评测划分。

[![CI](https://github.com/crown-sports/vlm-data-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/crown-sports/vlm-data-doctor/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3670a0)](pyproject.toml)
[![MIT](https://img.shields.io/badge/License-MIT-196c57)](LICENSE)
[![公开预览](https://img.shields.io/badge/Release-v0.3.0%20preview-196c57)](https://github.com/crown-sports/vlm-data-doctor/releases/tag/v0.3.0)

[English](README.md) · [快速开始](#快速开始) · [价值与实现证据](docs/product.md) · [使用场景](docs/impact.zh-CN.md) · [规则](docs/checks.md) · [LlamaFactory 接入](docs/integrations/llamafactory.md)

JSON 能解析，不代表数据能直接用于训练。图片可能没拷全，`<image>` 可能与图片数量不匹配，
随机拆分也可能把同一份文档的不同页面分进训练集和评测集。

适合负责图文 SFT 数据的标注负责人和算法工程师。放在标注导出之后、训练任务提交之前：
拿到带行号、字段和处理建议的离线报告，或一对 train/eval 文件与说明相关样本为何分在一起的划分清单。

## 什么时候用

| 遇到的问题 | 检查什么 | 拿到结果后做什么 |
| --- | --- | --- |
| 图文数据导出后，需要逐条排查缺图、坏图和格式错误 | 对话结构、图片占位符、本地图片解码 | 按报告中的行号和字段修复，再提交训练 |
| 文档问答实验按行拆分，训练和评测可能共享原文档 | 精确样本／图片重叠；指定 `document_id` 时检查来源组交叉 | 按实验要求重新分组拆分，复查重叠 |
| 修改数据后重跑实验，只记了文件名和样本数 | 数据文件哈希、有效图片清单哈希、规则版本和配置 | 随实验保存报告，确认两次检查的输入是否相同 |

它检查结构和精确重叠，不能判断答案是否正确。重新压缩、裁剪和语义近重复也不在当前检测范围。

![故障样例生成的 HTML 报告：规则、行号、字段和处理建议](docs/assets/report-desktop.png)

报告可搜索、按严重程度筛选。[下载离线示例](https://github.com/crown-sports/vlm-data-doctor/releases/download/v0.2.0/report.html) · [手机端截图](docs/assets/report-mobile.png)

## 快速开始

需要 Python 3.10+，从仓库安装：

```bash
git clone --branch v0.3.0 https://github.com/crown-sports/vlm-data-doctor.git
cd vlm-data-doctor
python -m venv .venv
```

macOS/Linux 执行 `source .venv/bin/activate`；Windows PowerShell 执行 `.venv\Scripts\Activate.ps1`。

安装已固定到 v0.3.0 的源码，示例就在当前目录；不依赖 PyPI 发布：

```bash
python -m pip install .
vlm-data-doctor check examples/clean/train.jsonl --eval examples/clean/validation.jsonl --strict
```

预期：2 条训练样本、1 条评测样本，0 错误、0 警告。运行依赖只有 Pillow，CPU 即可；不加载模型，不调用外部 API，不修改数据。

生成故障报告：

```bash
vlm-data-doctor check examples/broken/train.jsonl --eval examples/broken/validation.jsonl --image-root examples/clean --format html --output report.html
```

用浏览器打开 `report.html`。样例含 3 个错误和 1 个警告，命令返回 `1`，报告仍会生成。
再次运行请换一个输出文件名；已有文件不会被覆盖。

## 复现：没有重复图片，为什么还要查文档来源？

仓库中的[文档拆分样例](examples/document-split/README.zh-CN.md)用两份自行生成的手册演示这个问题。
训练集用了手册 A 的第 1 页，评测集用了 A 的第 2 页。图片、问题和答案都不同，精确去重不会报错。
如果实验要衡量对**未见过的文档**的泛化，这种拆分就不符合要求。

```bash
vlm-data-doctor check examples/document-split/train.jsonl --eval examples/document-split/validation.jsonl --group-key document_id
```

```text
ERROR split_group_overlap eval:1 document_id: The selected group also appears at train:1; use a group-disjoint split.
```

完整样例包含不启用分组检查、启用检查、改用独立文档评测三个步骤。
分组 ID 由数据提供者指定；工具不会从图片中识别文档来源。

## 自动生成防泄漏划分

```bash
vlm-data-doctor split examples/document-split/all.jsonl --group-key document_id --eval-fraction 0.2 --seed 42 --output manual-split
vlm-data-doctor check manual-split/train.jsonl --eval manual-split/eval.jsonl --image-root examples/document-split --group-key document_id --strict
```

预期：3 条来源记录全部分配，手册 A 两页留在同一侧，最后检查无错误和警告。打开 `manual-split/manifest.json` 看原始行号、分组和复核结果。接入自己的数据时替换输入文件和图片根目录。

按文档、相同图片字节、规范化输入建立传递连通分量，保持相关样本在同一侧，输出 train/eval JSONL 和含原始行号、SHA-256、复核结果的 manifest。目标目录必须不存在，缺失的父目录会自动创建。比例按连通分量计算，不保证精确行数比例；数据全连通或有错误时拒绝输出。保留所有原始记录与图片路径，图片不复制，后续检查请用原始 `--image-root`。manifest 记录本机图片根目录，公开分享前注意这一字段。当前需将数据行载入内存，不检测重压缩或语义相似图片。

## 接入自己的数据

支持 JSON 数组或 JSONL，格式为 `messages` 或 ShareGPT `conversations`：

```json
{
  "document_id": "manual-a",
  "messages": [
    {"role": "user", "content": "<image>这个方块是什么颜色？"},
    {"role": "assistant", "content": "红色。"}
  ],
  "images": ["images/red.png"]
}
```

图片默认相对于数据文件目录；`--image-root` 指定公共根目录，`--eval-image-root` 可单独指定评测图片根目录。
`document_id` 仅在使用 `--group-key document_id` 时必填，值为非空字符串或整数。

```bash
vlm-data-doctor check data/train.jsonl --eval data/test.jsonl --image-root data --group-key document_id --format json --output audit.json
```

退出码：`0` = 无错误；`1` = 有数据错误；`2` = 参数或读写失败。`--strict` 会把警告也作为失败条件。
`check` 报告的输出父目录需已存在。相同图片跨集合出现通常需要复核，不应一律删除。

[LlamaFactory 数据映射与训练前检查](docs/integrations/llamafactory.md) · [Python API、完整规则与边界](docs/checks.md)

## 检查原理与验证

格式检查使用固定规则；图片通过 Pillow 完整解码；重复检查使用规范化对话和图片文件字节的 SHA-256 指纹。
按来源拆分则比较用户指定的组 ID。没有学习模型或语义质量评分。

现有价值是把检查、按关联证据划分和复核清单接成一个流程，并覆盖传递关联、导出后图片路径等边界。
[实现证据、当前局限与未来需要积累的验证](docs/product.md)。

| 已运行的验证 | 结果与范围 |
| --- | --- |
| 合成故障回归 | 128 / 128 个目标规则命中；32 个正常对照无告警。样例按已知规则构造 |
| CPU 检查 | 5 万行中位耗时 1.87 秒，峰值 RSS 49.5 MiB；Apple M5，复用 256 张小图片 |
| 固定版本 LlamaFactory 示例 | 6 条记录、3 张图片通过静态检查；未运行训练器 |

这些结果不代表真实数据检测准确率或模型效果提升。[测量方法、原始记录与复现命令](docs/benchmarks.md)。

## 下一步

优先验证真实数据上的漏检与误报，再研究重新压缩图片的近重复识别。
语义质量评估和清洗后的模型效果，需要独立标注与受控训练实验。[具体问题和验收标准](docs/roadmap.md)。

训练可接 [LlamaFactory](https://github.com/hiyouga/LlamaFactory)。需要更广泛的数据处理可看
[Data-Juicer](https://github.com/datajuicer/data-juicer)，数据与标签质量可看 [Cleanlab](https://github.com/cleanlab/cleanlab)。

[贡献指南](CONTRIBUTING.md) · [版本变化](CHANGELOG.md) · [软件引用](CITATION.cff)

代码和自行生成的示例使用 MIT 许可证。
