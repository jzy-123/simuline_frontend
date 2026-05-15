# SimuLine

[English](README.md) | [简体中文](README.zh-CN.md)

这是论文 [Simulating News Recommendation Ecosystems for Insights and Implications](https://ieeexplore.ieee.org/abstract/document/10504866) 的官方代码仓库。

## 摘要

研究在线新闻社区的演化过程，对于提升新闻推荐系统的效果具有重要意义。传统上，这类研究主要依赖静态数据分析的实证方法。虽然这种方式已经为推荐系统优化带来了很多有价值的结论，但它也受到合适数据集缺乏、缺少开放可控社会实验平台等限制。这一空白使得研究者难以系统理解推荐系统对生态演化过程及其底层机制的影响，也可能导致长期效用不佳的系统设计。

在这项工作中，我们提出了 SimuLine，一个用于剖析新闻推荐生态演化过程的仿真平台。SimuLine 首先构建能够较好反映人类行为的潜在空间，然后基于 Agent-based Modeling 对新闻推荐生态进行模拟。结合定量指标、可视化与文本解释构成的综合分析框架，我们分析了生态在不同演化阶段的特征，并从生命周期视角总结关键因素及其作用机制。同时，我们进一步研究了多种推荐系统设计策略对演化过程的影响，包括冷启动内容、突发内容和推广策略等，这些结果能够为推荐系统设计提供新的启发。

***数据处理流程***

<img src="Figures/data.png" alt="data" style="zoom:100%;" />

***仿真流程***

<img src="Figures/simulation.png" alt="simulation" style="zoom:50%;" />

***生态主题演化***

<img src="Figures/evolution.png" alt="evolution" style="zoom:50%;" />

***新闻推荐生态演化关系图***

<img src="Figures/factors.png" alt="factors" style="zoom:67%;" />

## BibTex

@article{zhang2024simulating,
    title={Simulating News Recommendation Ecosystems for Insights and Implications},
    author={Zhang, Guangping and Li, Dongsheng and Gu, Hansu and Lu, Tun and Shang, Li and Gu, Ning},
    journal={IEEE Transactions on Computational Social Systems},
    year={2024},
    publisher={IEEE}
}

## 快速开始

### Step.1 配置 Python 环境

```bash
bash setup_env.sh
```

部分主要模块版本如下：

```bash
Ubuntu == 20.04 LTS
Python == 3.10
CUDA == 11.8
Torch == 2.0.1+cu118
DGL == 2.1.0+cu118
```

### Step.2 配置仿真实验参数

在 `Config/Batch.xlsx` 中填写实验配置即可。

你可以一次性在这个 Excel 文件中配置多个实验，SimuLine 会按顺序逐个运行。

```
description@str: 实验说明
experiment@str: 实验 ID，作为第一级目录名
var@str: 变体 ID，作为第二级目录名
run@str: 运行 ID，作为第三级目录名
num_round@int: 仿真轮数，经验上多数实验 50 轮已足够
n_round@int: 新闻内容的活跃窗口大小
model@str: 使用的推荐算法，大多数通用推荐算法都支持
epochs@int: 每轮仿真中的训练轮数
positive_inter_type@str: 作为正反馈的交互类型，例如 like 或 click
negative_inter_type@str: 作为负反馈的交互类型，可选；若无则填 "-"
num_from_match@int: 通过相似向量匹配产生的推荐数量
num_from_cold_start@int: 通过冷启动策略产生的推荐数量
num_from_hot@int: 通过热门策略产生的推荐数量
num_from_promote@int: 通过推广策略产生的推荐数量
cold_start_inter_type@str: 冷启动策略使用的交互类型，例如 random、like 或 click
hot_inter_type@str: 用于计算热门度的交互类型
promote_type@str: 推广策略类型，例如 content 或 author
promote_round@int: 推广目标重置的轮数间隔
init_quality_mean@float: 初始内容质量均值
init_quality_var@float: 初始内容质量方差
best_stable_quality@float: 理论上的内容质量上界，不建议修改
init_threshold_mean@float: 用户阈值均值
init_threshold_var@float: 用户阈值方差
init_like_quality_weight_mean@float: 用户对内容质量偏好权重的均值
init_like_quality_weight_var@float: 用户对内容质量偏好权重的方差
init_user_concentration_mean@float: 用户兴趣集中度均值
init_user_concentration_var@float: 用户兴趣集中度方差
init_creator_concentration_mean@float: 创作者兴趣集中度均值
init_creator_concentration_var@float: 创作者兴趣集中度方差
uam_delta@float: 用户兴趣漂移步长
cam_delta@float: 创作者兴趣漂移步长
```

### Step.3 预处理

```bash
conda activate UnbiasedEmbedding
python preprocess_1.py

conda activate SimuLineDev
python preprocess_2.py
python preprocess_3.py
```

### Step.4 启动仿真

```bash
conda activate SimuLineDev
python main.py
```

### Step.5 使用 Web 平台

如果你希望在浏览器中创建小规模实验并查看结果，可以在项目根目录启动平台服务：

```bash
conda run -n jzy python run_platform.py
```

然后访问：

```text
http://localhost:8000
```

默认登录账号：

```text
username: admin
password: simuline123
```

如果需要，也可以通过环境变量 `SIMULINE_PLATFORM_USER` 和 `SIMULINE_PLATFORM_PASSWORD` 覆盖默认账号。

## 前端使用说明

前端页面面向业务试用、仿真实验和结果查看，不需要修改代码即可使用。

### 1. 登录

- 打开 `http://localhost:8000`
- 输入平台用户名和密码
- 登录后进入实验总览界面

### 2. 创建小规模实验

- 在左侧控制面板中选择策略模板
- 填写实验名称，这一项必填
- 设置仿真轮次、训练轮数、用户数和创作者数
- 点击启动按钮提交任务

你输入的实验名称会同步显示在运行任务列表和实验列表中，方便按业务目的识别实验，而不是只看系统生成的任务 ID。

### 3. 理解左侧控制面板

- 策略模板区域：选择预设推荐策略，点击标题可以查看模板说明
- 运行任务区域：展示排队中、运行中、已完成或已终止的任务
- 实验列表区域：展示已经生成结果的实验，点击后可进入分析

你还可以直接在界面里完成一些日常管理动作：

- 删除单个任务或实验
- 批量删除已勾选的任务或实验
- 在试跑过程中提前终止某个正在运行的任务

### 4. 查看实验结果

选择某个实验后，右侧结果区域会展示：

- 实验总览：当前实验的核心宏观指标
- 指标曲线：按轮次展示用户、创作者、内容与推荐系统相关指标的变化趋势
- 自动解读：根据当前结果生成的简要业务分析
- 微观过程面板：展示用户活跃情况、创作者曝光分布、内容曝光分布以及头部创作者或内容等过程性结果
- 个体详情入口：进入单个用户、创作者或内容的独立详情页面，查看其逐轮变化

如果实验仍在运行中，页面会持续刷新当前实验状态和结果，因此总览卡片、曲线和微观过程快照会随着轮次推进而更新。

当鼠标悬停在指标曲线的某个点上时，前端会显示对应轮次和指标数值。

### 5. 推荐使用流程

对于第一次使用，建议按下面的方式试跑：

1. 先用较小规模启动实验，例如 `2` 轮、`500` 用户、`100` 创作者。
2. 先跑一组基线策略，建立参考。
3. 再创建几组不同模板的实验，做横向比较。
4. 先看实验总览指标，再结合趋势曲线和微观过程理解变化原因。
5. 如果只是验证思路，可以提前终止试验任务，节省等待时间。
