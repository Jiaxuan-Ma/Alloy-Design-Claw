# Alloy Design Claw

Alloy Design Claw 是一个面向高温合金智能设计的 Agent 工具原型。项目提供网页对话界面，并通过本地 Skills 工作流串联数据检查、热力学计算、机器学习建模、SHAP 特征筛选、NSGA-III 多目标优化以及可选的力学性能筛选。



## 主要功能

- 上传和检查合金成分数据表。
- 调用 Thermo-Calc/TC-Python 工作流计算热物性结果。
- 训练并比较多种回归模型，自动选择最佳模型。
- 使用 SHAP 分析筛选关键合金元素。
- 基于 NSGA-III 进行多目标成分优化。
- 可选地根据 UTS 和延伸率预测结果过滤优化成分。

## 项目结构

```text
.
├── app.py                  # Web 服务入口和 Agent UI 后端
├── base_agent.py           # LangChain Agent 与 Skills 调用逻辑
├── main.ipynb              # Notebook 实验入口
├── dataset.xlsx            # 示例数据集
├── web/                    # 前端页面、样式和交互脚本
└── Skills/                 # 合金设计相关技能与脚本
```

## 环境配置

建议使用 Python 3.10 及以上版本，并安装项目所需依赖：

```bash
pip install python-dotenv pyyaml requests html2text pandas openpyxl scikit-learn joblib langchain langchain-core langchain-deepseek
```

如需运行完整优化和解释分析流程，还需要安装：

```bash
pip install shap pymoo
```

Thermo-Calc 相关功能需要本机已配置可用的 Thermo-Calc/TC-Python 环境和有效许可证。

## 配置文件

在项目根目录创建或修改 `.env`，填入模型服务配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

如果需要指定 Agent 使用的 Python 环境，可额外设置：

```env
AGENT_PYTHON=D:\anaconda3\envs\pytorch_gpu\python.exe
```

## 启动方式

在项目根目录运行：

```bash
python app.py 8000
```

然后在浏览器打开：

```text
http://127.0.0.1:8000
```

## 基本使用流程

1. 打开网页界面并上传合金数据表。
2. 让 Agent 检查成分列并生成 composition-only 工作文件。
3. 执行热力学计算，得到带热物性标签的数据表。
4. 训练模型并选择最佳热物性预测模型。
5. 运行 SHAP 分析，筛选优化元素。
6. 设置元素范围和优化参数，执行 NSGA-III 优化。
7. 如有力学性能数据，可继续训练 UTS/EL 模型并过滤候选合金。

## 说明

当前项目为本地原型工具，部分脚本依赖用户机器上的 Python 环境、模型服务密钥以及 Thermo-Calc 安装情况。运行前请确认 `.env`、依赖包和数据文件均已准备好。
