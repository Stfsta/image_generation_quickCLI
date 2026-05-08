# 速创API 图像生成工具（e.g. GPT-image-2）v2.0

基于速创API中转站的便捷图像生成脚本，支持对话上下文记忆，方便连续调整生成结果。模型使用 `gpt-image-2`，兼容 OpenAI 接口调用方式。

[English](../README.md)
[简体中文](README.zh-CN.md)

## 功能特点

- 直接调用速创中转站图像生成接口，免去复杂配置
- 支持**对话历史记忆**，可在多轮对话中基于之前的描述逐步修改图像
- 命令行交互，输入中文/英文提示词即可生成
- 自动将生成的图片保存到本地 `generated_images/` 目录
- 密钥本地配置文件管理，不污染系统环境变量
- **模块化架构**：配置、历史、API 客户端、业务逻辑、CLI 分层解耦
- **连接池与自动重试**：HTTP 会话复用，支持指数退避重试
- **原子写历史文件**：防止数据损坏
- **更安全的历史持久化**：历史更新带锁并采用原子写入
- 轻量、易读的代码结构，方便二次开发

## 环境要求

- Python 3.10 或更高版本
- 已安装依赖库：`requests`

安装依赖（推荐）：

```bash
pip install -r requirements.txt
```

或使用最小手动安装：

```bash
pip install requests
```

可选：按包方式安装后使用 `image-generator` 命令启动：

```bash
pip install .
```

## 获取速创API密钥

1. 前往 [速创API 中转站](https://api.suchuang.vip) 注册并登录。
2. 在控制台中进入 **API 密钥** 页面，点击 **添加令牌** 创建新令牌。
3. 复制生成的密钥（形如 `sk-xxxxxxxxxxxxxxxx`）。

> **注意**：确保您的账户有足够余额，否则图像生成会因额度不足而失败。

## 模型与端点说明

- 默认模型为 `gpt-image-2`（速创平台命名）。  
若当前线路/账号不支持，请在 `config.json` 中改为 `gpt-image-1`、`dall-e-3` 或 `dall-e-2`。
- 推荐主机配置为：
  ```json
  "api_base": "https://api.suchuang.vip"
  ```
  客户端会自动拼接端点：
  - `POST /v1/images/generations`：文生图与参考图回退路径
  - `POST /v1/images/edits`：本地 PNG 图像编辑路径
- 旧版 `base_url`（完整端点 URL）仍兼容，但新配置建议优先使用 `api_base`。

## 快速开始

### 1. 首次运行与配置

运行脚本：

```bash
python image_generator.py
```

首次运行会自动在当前工作目录生成 `config.json` 文件，并提示编辑密钥。用文本编辑器打开该文件，将 `api_key` 字段的值替换为您的真实密钥（示例）：

```json
{
  "api_key": "sk-你的真实密钥",
  "api_base": "https://api.suchuang.vip",
  "base_url": "https://api.suchuang.vip/v1/images/generations",
  "model": "gpt-image-2",
  "image_dir": "./generated_images",
  "history_file": "chat_memory.json",
  "max_history": 10,
  "timeout": 90,
  "max_retries": 3,
  "retry_delay": 1.0,
  "default_size": "1024x1024"
}
```

保存后再次运行即可。

### 2. 输入提示词生成图像

成功启动后，命令行提示符如下：

```
Prompt/Command | 提示词/命令 >
```

直接输入英文或中文描述，按回车即可生成图像。例如：

```
Prompt/Command | 提示词/命令 > A cute cat wearing a wizard hat
```

生成完成后，图片会保存在 `generated_images/` 文件夹中，文件名包含时间戳。

### 3. 连续对话调整图像

该脚本会记住之前的对话内容，你可以连续输入新的要求，AI 会结合历史描述生成新的图像。例如：

```
Prompt/Command | 提示词/命令 > 把猫换成金色的毛发
```

脚本会自动将上一轮的生成结果（简化描述）与新要求拼接，形成完整的提示词再次提交生成。

### 4. 图生图功能

`gpt-image-2` 模型支持图生图（Image-to-Image）功能。你可以提供参考图像，配合文本提示词来引导生成过程。脚本支持**三种语法风格**：

#### 方式一：内联语法（推荐）

直接在提示词中包含图片引用：

```
Prompt/Command | 提示词/命令 > [image:/path/to/reference_image.jpg] 把背景改成日落场景
```

#### 方式二：命令行参数语法

在提示词前使用 `--ref` 参数：

```
Prompt/Command | 提示词/命令 > --ref /path/to/reference_image.jpg 把背景改成日落场景
```

#### 方式三：会话级参考图片

设置一张参考图片，在当前会话中后续所有生成都使用该图片，直到执行 `ref clear` 或切换会话：

```
Prompt/Command | 提示词/命令 > ref /path/to/reference_image.jpg
Prompt/Command | 提示词/命令 > 把背景改成日落场景
Prompt/Command | 提示词/命令 > 多加一些云
Prompt/Command | 提示词/命令 > ref clear
```

你也可以使用 URL 作为参考图片：

```
Prompt/Command | 提示词/命令 > --ref https://example.com/reference.png 给这张图加上雪景效果
```

**图生图注意事项：**

- 本地 PNG 参考图（`.png` 且 <= 4MB）会走 `/v1/images/edits` 的 `multipart/form-data` 请求。
- URL 参考图与非 PNG 本地参考图会回退到 `/v1/images/generations` 的私有 `image_url` 扩展路径。
- edits 接口支持可选 `mask`，但当前 CLI 暂未提供专用 `--mask` 参数。
- 每次请求仅支持一张参考图。

### 5. 输出尺寸设置

你可以通过以下方式控制输出图像的尺寸：

#### 方式A：在提示词中指定尺寸

直接在提示词中使用支持的尺寸格式：

```
Prompt/Command | 提示词/命令 > [size:1792x1024] 一幅全景山水画
```

也可使用临时 CLI 参数语法：

```
Prompt/Command | 提示词/命令 > --size 1024x1792 一位竖版构图的幻想角色
```

支持的尺寸取值（官方模型能力并集）：


| 尺寸          | 宽高比  | 说明                 |
| ----------- | ---- | ------------------ |
| `256x256`   | 1:1  | `dall-e-2` 小图      |
| `512x512`   | 1:1  | `dall-e-2` 中图      |
| `1024x1024` | 1:1  | 通用/默认              |
| `1536x1024` | 3:2  | `gpt-image-1` 横图   |
| `1024x1536` | 2:3  | `gpt-image-1` 竖图   |
| `1792x1024` | 16:9 | `dall-e-3` 横图      |
| `1024x1792` | 9:16 | `dall-e-3` 竖图      |
| `auto`      | 自动   | `gpt-image-1` 自动尺寸 |


#### 方式B：修改配置文件

编辑 `config.json` 文件，添加 `default_size` 字段：

```json
{
  "api_key": "sk-你的密钥",
  "default_size": "1792x1024",
  ...
}
```

若尺寸不在支持列表内，会打印警告并自动回退到下一个可用来源（`--size`/`[size:...]`/`default_size`）。

#### 方式C：编程调用

当作为库使用时：

```python
from image_generator import ImageGenerationService

service = ImageGenerationService()
service.generate("美丽的日落", size="1792x1024")
```

### 6. 可用命令


| 命令                    | 说明         |
| --------------------- | ---------- |
| `exit` / `quit` / `q` | 退出程序       |
| `clear`               | 清空当前会话历史   |
| `session`             | 查看当前会话 ID  |
| `session <id>`        | 切换到指定会话 ID |
| `ref <path/url>`      | 设置会话级参考图片  |
| `ref clear`           | 清除会话级参考图片  |
| `help`                | 显示帮助信息     |


### 7. 退出程序

输入 `exit`、`quit` 或 `q` 即可退出。

## 配置说明

通过编辑 `config.json` 可调整以下参数：


| 变量             | 说明                                                                                             | 默认值                                              |
| -------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `api_key`      | 速创API密钥                                                                                        | —                                                |
| `api_base`     | API 主机地址（推荐）                                                                                   | `https://api.suchuang.vip`                       |
| `base_url`     | 旧版完整端点地址（兼容）                                                                                   | `https://api.suchuang.vip/v1/images/generations` |
| `model`        | 使用的模型名称                                                                                        | `gpt-image-2`                                    |
| `image_dir`    | 图片保存目录                                                                                         | `./generated_images`                             |
| `max_history`  | 保留的最大对话轮数                                                                                      | 10                                               |
| `history_file` | 对话历史存储文件                                                                                       | `chat_memory.json`                               |
| `timeout`      | API 请求超时（秒）                                                                                    | 90                                               |
| `max_retries`  | 失败时最大重试次数                                                                                      | 3                                                |
| `retry_delay`  | 重试基础延迟（秒）                                                                                      | 1.0                                              |
| `default_size` | 默认输出尺寸（`256x256`/`512x512`/`1024x1024`/`1536x1024`/`1024x1536`/`1792x1024`/`1024x1792`/`auto`） | `1024x1024`                                      |


路径说明：`config.json`、`chat_memory.json`、`generated_images/` 都是相对于你执行命令时的当前工作目录解析。
响应兼容说明：客户端同时支持 `data[].url` 与 `data[].b64_json`；若两者都不存在，则判定该次生成为失败。

## 项目结构

```
.
├── image_generator.py          # 兼容入口（调用包内 CLI）
├── image_generator/            # 核心包
│   ├── __init__.py
│   ├── api_client.py           # HTTP 客户端（连接池、重试）
│   ├── cli.py                  # 命令行交互界面
│   ├── config.py               # 配置管理与验证
│   ├── history.py              # 对话历史管理（线程安全、原子写）
│   └── image_service.py        # 业务逻辑编排
├── docs/                       # 文档目录
│   └── README.zh-CN.md         # 中文版本说明文档
├── .gitignore                  # Git 忽略配置
├── README.md                   # 项目文档（英文）
├── config.json                 # 配置文件（存放密钥等，首次运行自动生成）
├── chat_memory.json            # 对话历史（自动生成）
└── generated_images/           # 生成的图片（自动创建）
```

## 常见问题

**Q: 首次运行提示"已生成配置文件 config.json"怎么办？**  
A: 这是正常引导流程。按提示编辑 `config.json` 填入密钥后重新运行即可。

**Q: 生成失败，返回 HTTP 错误？**  
A: 检查密钥是否正确，账户余额是否充足，网络是否可正常访问 `api.suchuang.vip`。脚本会自动重试可恢复的错误（如 429/500/502/503/504）。

**Q: 对话历史保存在哪里？**  
A: 保存在当前目录下的 `chat_memory.json` 文件中，可删除该文件清空记忆，或在交互模式下输入 `clear`。

**Q: 可以一次生成多张图片吗？**  
A: 当前 CLI 默认每次生成 1 张（`n=1`），且未暴露 `n` 命令参数。如需多张，请在编程调用 `generate()` 时调整 `n`。

**Q: 密钥泄露或想更换密钥怎么办？**  
A: 直接编辑 `config.json` 修改 `api_key` 字段即可，或删除该文件重新运行生成模板。

## 注意事项

- **密钥安全**：请勿将包含真实密钥的 `config.json` 上传至公开仓库。建议将 `config.json` 加入 `.gitignore`。
- **使用限制**：图像生成会消耗速创账户的额度，频繁调用前请确认余额。
- **网络延迟**：生成过程需要等待 API 返回结果，视网络及服务器负载可能需要几十秒。

## 示例对话

```
Prompt/Command | 提示词/命令 > 一个充满赛博朋克风格的城市夜景
[Prompt/提示词] 一个充满赛博朋克风格的城市夜景
[Saved/已保存] 图片已保存至: generated_images/image_20240508_223044.png
[Complete/完成] 图像已生成: generated_images/image_20240508_223044.png
----------------------------------------
Prompt/Command | 提示词/命令 > 加上细雨和霓虹灯倒影
[Prompt/提示词] Dialogue history / 对话历史:
user: 一个充满赛博朋克风格的城市夜景
assistant: [Image generated / 已生成图片]

Latest request / 最新要求: 加上细雨和霓虹灯倒影
[Saved/已保存] 图片已保存至: generated_images/image_20240508_223112.png
[Complete/完成] 图像已生成: generated_images/image_20240508_223112.png
```

---

*本工具基于速创API中转站文档开发，仅供学习和个人使用。*