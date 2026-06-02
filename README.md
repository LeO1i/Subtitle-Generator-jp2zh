# 日语视频中文字幕生成器（Windows）

这个项目用于从日语视频自动生成双语字幕（`日语 + 中文`），并支持把**中文字幕硬字幕**烧录进视频。

当前版本基于 Hugging Face 模型流程：
- 默认语音识别（ASR）：`Qwen/Qwen3-ASR-0.6B`
- 默认机器翻译（MT）：`Helsinki-NLP/opus-mt-ja-zh`
- 默认输出：繁體中文字幕（OpenCC 后处理）
- 可选高级翻译链路：优先尝试 7B 级模型，失败后自动回退

## 功能概览

- 从视频提取音频并进行日语语音识别
- 将识别结果翻译为中文，输出双语 `.srt`
- 支持按分块处理长视频（可断点续跑）
- 支持可选术语表（glossary）增强翻译一致性
- 支持将中文字幕烧录为硬字幕视频
- 支持识别多个说话人，并仅保留前 3 位响度最高的说话人
- 支持生成彩色 ASS 中文字幕（Speaker A/B/C 使用不同颜色）
- 提供 PySide6 GUI（推荐）和 CLI 两种使用方式

## 环境要求

- Windows 10 / 11
- Python 3.9 及以上
- FFmpeg（已加入 PATH，或安装在 `C:\ffmpeg\...`）
- 建议使用 NVIDIA GPU（支持 CPU 回退，但速度明显更慢）

## 安装步骤

1. 安装 Python 3.9+（勾选 `Add Python to PATH`）
2. 安装 FFmpeg：https://ffmpeg.org/download.html
3. 安装依赖（推荐）：
   - 双击运行 `install.bat`
   - 脚本会优先安装 CUDA 版 PyTorch，失败时自动回退
4. 或手动安装：
   - `pip install -r requirements.txt`

## 打包为 Windows 应用（推荐）

如果希望像普通 Windows 软件一样双击图标启动应用，可以在开发机上构建 standalone 版本：

1. 先运行一次 `install.bat` 安装依赖
2. 运行 `build_app.bat`
3. 构建完成后双击：
   - `dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe`

构建输出目录结构：

```text
dist\JapaneseSubtitleGenerator\
  JapaneseSubtitleGenerator.exe
  _internal\
  ffmpeg\              # 如果你提供本地 ffmpeg 文件夹，会一起打包
```

建议将 `JapaneseSubtitleGenerator.exe` 固定到桌面或任务栏。正常使用时不需要运行 `.bat` 文件。

注意：
- 打包使用 PyInstaller `onedir` 模式，启动更快，也更适合 PyTorch / PySide6
- Hugging Face 模型权重不会被打进 exe，首次运行仍会下载模型
- 如果要内置 FFmpeg，可在项目根目录放置 `ffmpeg\ffmpeg.exe` 和 `ffmpeg\ffprobe.exe` 后再运行 `build_app.bat`
- GPU / CPU 依赖与构建机器环境相关，建议在目标运行环境相近的机器上构建

## 开发启动方式

### 方式一：GUI（开发用）

运行：
- 双击 `run.bat`

GUI 中可配置：
- 视频文件、输出目录
- 模型档位（Fast / Balanced / Accurate）和 ASR/MT 模型
- 分块时长（30-600 秒，Fast 默认 90）
- 分块重叠（默认 2 秒）
- 质量模式（`fast` / `accurate`）
- 音频增强预设（`standard` / `denoise` / `aggressive`）
- 可选术语表文件（支持 `.txt/.tsv/.csv`）
- 可选 ASR 术语/修正文件（支持 `.txt/.tsv/.csv`）
- 可选高级翻译回退链路
- 可选说话人识别（默认启用，仅保留前 3 位响度最高的说话人）

使用步骤：
1. 选择视频与输出目录
2. 根据需要调整参数
3. 点击 `生成字幕` 生成双语字幕
4. 如需硬字幕，点击 `烧录硬字幕`

### 方式二：CLI

运行：
- `python main.py`

CLI 会交互询问：
- ASR/MT 模型
- 是否启用高级翻译回退
- 质量模式
- 分块时长与重叠时长
- 术语表路径（可选）
- ASR 术语/修正文件路径（可选）
- 音频增强预设（`standard` / `denoise` / `aggressive`）
- 是否启用说话人识别
- 视频路径

## ASR 准确率增强建议（同模型）

建议优先调这些参数：

- 有背景音乐/噪声：使用 `denoise`
- 噪声很重且语音较弱：使用 `aggressive`
- 一般清晰视频：使用 `standard`
- 质量模式选择 `accurate` 时，程序会自动把超长分块（>=120s）收紧到 60s，并确保至少 2s 重叠，通常更稳

### ASR 术语/修正文件格式

用于提升人名、术语一致性。纯文本每行一条：

- `术语词条`：作为偏置提示词（例如：`宇智波佐助`）
- `误识别=>标准写法`：做确定性替换（例如：`宇治波佐助=>宇智波佐助`）

示例：

```text
# 术语
宇智波佐助
查克拉

# 修正
宇治波佐助=>宇智波佐助
卡卡西老师=>旗木卡卡西
```

## 长视频与断点续跑

- 音频会按分块处理，并在块之间保留重叠，减少断句误差
- 每个视频会生成对应检查点目录：`<video_name>_checkpoints`
- 如果中途中断，重新运行后会自动续跑已完成分块
- 最终输出时会自动映射回全局时间轴，生成完整 `.srt`

## 输出说明

- 生成字幕为双语格式：
  - 第 1 行：日语
  - 第 2 行：繁體中文
- 同时生成彩色 ASS 字幕：`<name>_styled.ass`
- 烧录硬字幕时，优先使用同名 ASS 文件保留说话人颜色；没有 ASS 时会从双语 SRT 提取中文行
- 默认硬字幕输出名：`<video_name>_cn_hardsub.mp4`

## 模型档位

| 档位 | ASR | MT | 默认分块 | 适用场景 |
|------|-----|----|----------|----------|
| Fast | `Qwen/Qwen3-ASR-0.6B` | `Helsinki-NLP/opus-mt-ja-zh` | 90 秒 | 有限显存、长视频 |
| Balanced | `Qwen/Qwen3-ASR-0.6B` | `tencent/HY-MT1.5-1.8B` | 90 秒 | 更好的翻译质量 |
| Accurate | `Qwen/Qwen3-ASR-1.7B` | `tencent/HY-MT1.5-1.8B` | 60 秒 | 短视频或高准确率需求 |

## 性能建议

- 首次运行会下载模型权重，需要联网
- 30 分钟以上视频强烈建议 GPU
- 显存/内存不足时，优先使用 Fast 档位、关闭高级翻译、减小分块时长或关闭说话人识别
- 程序会先完成 ASR，再释放 ASR 模型并加载 MT 模型，以降低峰值显存
- 如果高级 MT 加载失败，程序会自动回退到更轻量翻译模型

## 常见问题排查

1. **依赖问题**：重新运行 `install.bat`
2. **找不到 FFmpeg**：确认 `ffmpeg -version` 可执行
3. **首次运行报模型错误**：检查网络连接后重试
4. **速度过慢**：确认 PyTorch 已启用 CUDA（不是 CPU-only）
5. **内存不足**：减小分块时长，或切换 `fast` 模式

**开发环境**
CPU：AMD 9700x
GPU：NVIDA 5070Ti（16GB 显存，建议使用 12GB 显存以上的 GPU）
内存：32GB
系统：Windows 11
CUDA：12.8

