# E2E 测试素材

## `sample_ja_short.mp4`（不包含在仓库中）

为避免向仓库提交大体积二进制文件，**测试视频不会随仓库分发**。请使用你自己的日语视频进行端到端测试，或按下面的方法生成一个无版权的合成片段。

### 生成一个无版权的测试片段（可选）

需要 `edge-tts` 和 FFmpeg：

```bat
python -m pip install edge-tts
python -c "import asyncio, edge_tts; asyncio.run(edge_tts.Communicate('こんにちは。今日は天気がとてもいいですね。', 'ja-JP-NanamiNeural').save('tests/fixtures/sample_ja_short.mp3'))"
ffmpeg -y -f lavfi -i color=c=black:s=640x360:d=32 -i tests/fixtures/sample_ja_short.mp3 -c:v libx264 -tune stillimage -c:a aac -shortest tests/fixtures/sample_ja_short.mp4
```

也可自行录制约 30 秒日语朗读，或使用你拥有版权的视频片段裁剪。

> 注意：`*.mp4` 在 `.gitignore` 中被整体忽略，生成的片段不会被提交。请勿将版权视频提交到仓库。

### 端到端测试步骤

1. 运行 `scripts\warmup_models.bat` 预下载模型
2. 运行 `.venv\Scripts\python.exe -m japanese_subtitle.app.cli`（或 GUI）
3. 选择你准备好的日语视频作为输入
4. 检查输出的双语 `.srt`、彩色 `.ass` 以及（可选）硬字幕 `.mp4` 是否符合预期
