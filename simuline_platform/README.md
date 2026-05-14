# SimuLine 仿真实验与策略评估平台

这是 SimuLine 的轻量 Web 包装层，用于把已有仿真输出展示成可试用的实验评估界面。第一版只读取 `Out/Result/**/**/*_output.csv`，不改动核心仿真流程。

## 启动

在 `SimuLine_code` 目录下安装平台依赖：

```bash
pip install -r requirements-platform.txt
```

启动服务：

```bash
uvicorn simuline_platform.app:app --host 0.0.0.0 --port 8000 --reload
```

也可以使用项目内置启动脚本：

```bash
python run_platform.py
```

如果当前 PowerShell 没有初始化 conda，可以直接使用：

```bash
conda run -n jzy python run_platform.py
```

浏览器访问：

```text
http://localhost:8000
```

## 已实现

- 自动扫描 `Out/Result/{experiment}/{variant}/{run}_output.csv`
- 提供实验列表 API
- 提供实验指标 API
- 提供预置实验模板 API
- 提供实验创建 API：`POST /api/experiments`
- 提供任务状态 API：`GET /api/jobs`、`GET /api/jobs/{job_id}`
- 提供任务日志 API：`GET /api/jobs/{job_id}/log`
- 支持删除和批量删除运行任务：`DELETE /api/jobs/{job_id}`、`POST /api/jobs/batch-delete`
- 支持删除和批量删除实验结果：`DELETE /api/experiments/{id}`、`POST /api/experiments/batch-delete`
- 将核心指标分为总览、用户侧、创作者侧、内容侧、推荐系统五类
- 提供轻量前端仪表盘
- 支持从前端启动小规模仿真实验
- 前端创建实验时必须填写实验名称，任务列表和实验列表会优先展示该名称
- 自动生成基础业务解读

## 创建实验 API 示例

```bash
curl -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "baseline",
    "name": "baseline-demo",
    "num_round": 2,
    "num_user": 500,
    "num_creator": 100,
    "epochs": 1,
    "auto_start": true
  }'
```

任务会写入：

```text
workspace/platform_jobs/{job_id}/config.json
workspace/platform_jobs/{job_id}/status.json
workspace/platform_jobs/{job_id}/run.log
```

仿真结果仍然写入 SimuLine 原有目录：

```text
Out/Result/Platform/{template_id}/job-{job_id}_output.csv
```

平台创建的小规模实验默认使用 `click` 作为推荐模型训练正反馈，以避免小样本下 `like` 过于稀疏导致模型无数据可训；`like` 仍会作为生态指标记录和展示。

## 下一步

- 增加账号登录
- 增加多实验对比报告
- 将当前子进程执行升级为 Redis/Celery 队列
- 增加任务取消和资源占用限制
