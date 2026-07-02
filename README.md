# 图片换装后台

上传模特图和服装图，一键生成换装效果。支持两个引擎，可并排对比：

- **火山引擎 图片换装 V2**（商业接口，按次收费，参数丰富，支持上衣+下衣）
- **快手 Kolors 虚拟试衣**（Hugging Face 免费公共 Space，单件服装）

提供 **Web 页面**和**命令行**两种用法，共用同一套核心调用逻辑。

## 目录结构

```
dress/
├── app/
│   ├── config.py          # 读取火山 AK/SK
│   ├── volc_client.py      # 火山换装：提交任务 + 轮询结果
│   ├── kolors_client.py    # 快手 Kolors 调用
│   ├── web.py              # FastAPI 服务（多引擎并发）
│   └── templates/          # 页面模板
├── cli.py                  # 命令行入口
├── docs/                   # 接口文档、项目对比表
├── data/                   # 测试用模特图/服装图
└── requirements.txt
```

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 配置密钥（火山引擎）

火山引擎需要 AccessKey。按以下任一方式提供（优先级从高到低）：

1. **环境变量**
   ```bash
   export VOLC_ACCESS_KEY=你的AccessKeyId
   export VOLC_SECRET_KEY=你的SecretAccessKey
   ```
2. **`.env` 文件**（参考 `.env.example`）
   ```
   VOLC_ACCESS_KEY=你的AccessKeyId
   VOLC_SECRET_KEY=你的SecretAccessKey
   ```
3. **`bin/AccessKey.txt`**（格式如下）
   ```
   AccessKeyId: 你的AccessKeyId
   SecretAccessKey: 你的SecretAccessKey
   ```

> 以上三种来源都已在 `.gitignore` 中排除，不会被提交。快手 Kolors 引擎无需密钥，但需要能访问 `*.hf.space`。

## Web 页面

```bash
.venv/bin/uvicorn app.web:app --host 0.0.0.0 --port 8077
```

浏览器打开 http://127.0.0.1:8077 （给同一网络的其他人访问时用 `--host 0.0.0.0` 并以本机 IP 访问）。

- 上传 1 张模特图 + 1~2 张服装图，每张选类型（上衣/下衣/整套）
- 勾选引擎（可同时勾选两个并排对比），各引擎参数独立设置
- 点「生成换装图」，结果按引擎分组展示
- 页面顶部「虚拟试衣开源项目对比」进入二级页面 `/list`

## 命令行

```bash
# 单件整套
.venv/bin/python cli.py --model data/man1.jpg --garment data/dress1.jpeg --type full --out outputs/result.png

# 上衣 + 下衣分开
.venv/bin/python cli.py --model 模特.jpg \
  --garment 上衣.jpg:upper --garment 裤子.jpg:bottom --out outputs/result.png

# 结果超分处理
.venv/bin/python cli.py --model data/man1.jpg --garment data/dress1.jpeg --do-sr --out outputs/result.png
```

CLI 目前只调用火山引擎。返回多张候选图时会自动加序号保存。

## 引擎说明

| | 火山引擎 图片换装 V2 | 快手 Kolors（HF） |
|---|---|---|
| 费用 | 按次收费 | 免费 |
| 稳定性 | 商业 SLA | 公共 Space，可能排队/限流/休眠 |
| 服装 | 支持上衣+下衣 2 件 | 仅单件、无类型区分 |
| 可控参数 | 保留头/手/脚、超分、上下装分离、遮挡范围等 | 仅随机种子 |
| 接入 | 官方 SDK | 直连 hf.space（非官方，仅供测试对比） |

## 相关链接

- [快手 Kolors 虚拟试衣（Hugging Face）](https://huggingface.co/spaces/Kwai-Kolors/Kolors-Virtual-Try-On)
- [火山引擎 图片换装文档](https://www.volcengine.com/docs/86081/1660170?lang=zh)
