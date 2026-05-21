import os
import subprocess
import sys
from pathlib import Path

import torch
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ffmpeg_utils import subprocess_kwargs as _subprocess_kwargs
from speech_extract import JapaneseVideoSubtitleGenerator
from write_sutitle import WriteSubtitle


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


def app_icon():
    for relative_path in ("assets/app.ico", "assets/app.svg"):
        path = resource_path(relative_path)
        if path.exists():
            return QIcon(str(path))
    return QIcon()


MODEL_TIERS = {
    "Fast": {
        "key": "fast",
        "asr": "Qwen/Qwen3-ASR-0.6B",
        "mt": "Helsinki-NLP/opus-mt-ja-zh",
        "chunk": "90",
        "quality": "fast",
    },
    "Balanced": {
        "key": "balanced",
        "asr": "Qwen/Qwen3-ASR-0.6B",
        "mt": "tencent/HY-MT1.5-1.8B",
        "chunk": "90",
        "quality": "fast",
    },
    "Accurate": {
        "key": "accurate",
        "asr": "Qwen/Qwen3-ASR-1.7B",
        "mt": "tencent/HY-MT1.5-1.8B",
        "chunk": "60",
        "quality": "accurate",
    },
}


class SubtitleWorker(QObject):
    progress = Signal(float, str)
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            self.log.emit("开始生成字幕...")
            self.log.emit(f"模型档位：{self.config['model_tier']}")
            self.log.emit(f"ASR 模型：{self.config['asr_model']}")
            self.log.emit(f"MT 模型：{self.config['mt_model']}")
            generator = JapaneseVideoSubtitleGenerator(
                model_tier=self.config["model_tier"],
                asr_model_id=self.config["asr_model"],
                mt_model_id=self.config["mt_model"],
                use_advanced_mt=self.config["use_advanced_mt"],
                quality_mode=self.config["quality_mode"],
                glossary_path=self.config["glossary_path"],
                asr_terms_path=self.config["asr_terms_path"],
                audio_preset=self.config["audio_preset"],
                enable_speaker_diarization=self.config["enable_speaker_diarization"],
                device=self.config["device"],
                progress_callback=lambda value, message: self.progress.emit(value, message),
            )
            srt_path = generator.process_video(
                self.config["video_path"],
                self.config["output_dir"],
                chunk_size_seconds=int(self.config["chunk_size"]),
                overlap_seconds=float(self.config["overlap"]),
                quality_mode=self.config["quality_mode"],
                glossary_path=self.config["glossary_path"],
                asr_terms_path=self.config["asr_terms_path"],
                audio_preset=self.config["audio_preset"],
            )
            if srt_path:
                self.finished.emit(True, srt_path)
            else:
                self.finished.emit(False, "字幕生成失败，请查看日志。")
        except Exception as err:
            self.finished.emit(False, str(err))


class BurnWorker(QObject):
    progress = Signal(float, str)
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, video_path, subtitle_path, output_path):
        super().__init__()
        self.video_path = video_path
        self.subtitle_path = subtitle_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(10, "准备烧录字幕...")
            self.log.emit(f"输出视频：{self.output_path}")
            success = WriteSubtitle().burn_subtitles(self.video_path, self.subtitle_path, self.output_path)
            if success:
                self.progress.emit(100, "烧录完成")
                self.finished.emit(True, self.output_path)
            else:
                self.finished.emit(False, "字幕烧录失败，请查看日志。")
        except Exception as err:
            self.finished.emit(False, str(err))


class SubtitleGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("日语视频繁体中文字幕生成器")
        self.setWindowIcon(app_icon())
        self.resize(980, 780)
        self.worker_thread = None
        self.worker = None
        self._build_ui()
        self._check_system_requirements()
        self._log_device_info()
        self._apply_tier_defaults()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("日语视频繁体中文字幕生成器")
        title_font = QFont("Microsoft YaHei", 16)
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        system_group = QGroupBox("系统信息")
        system_layout = QVBoxLayout(system_group)
        active_device = "CUDA 显卡" if torch.cuda.is_available() else "CPU（回退）"
        device_text = f"设备偏好：CUDA 显卡（默认） | 当前：{active_device}"
        if torch.cuda.is_available():
            device_text += f"（{torch.cuda.get_device_name(0)}） | CUDA：{getattr(torch.version, 'cuda', 'Unknown')}"
        self.device_label = QLabel(device_text)
        self.device_label.setStyleSheet("color: green;" if torch.cuda.is_available() else "color: orange;")
        system_layout.addWidget(self.device_label)
        system_layout.addWidget(QLabel("提示：Fast 档位使用较小模型与 90 秒分块，适合有限显存。"))
        root.addWidget(system_group)

        form_group = QGroupBox("输入与模型设置")
        form = QGridLayout(form_group)
        root.addWidget(form_group)

        self.video_path = QLineEdit()
        self.srt_path = QLineEdit()
        self.output_dir = QLineEdit(os.getcwd())
        self.glossary_path = QLineEdit()
        self.asr_terms_path = QLineEdit()

        self._add_path_row(form, 0, "视频文件：", self.video_path, self._browse_video)
        self._add_path_row(form, 1, "字幕文件（可选）：", self.srt_path, self._browse_subtitle)
        self._add_path_row(form, 2, "输出目录：", self.output_dir, self._browse_output_dir)

        form.addWidget(QLabel("模型档位："), 3, 0)
        self.model_tier = QComboBox()
        self.model_tier.addItems(MODEL_TIERS.keys())
        self.model_tier.currentTextChanged.connect(self._apply_tier_defaults)
        form.addWidget(self.model_tier, 3, 1)

        self.speaker_detection = QCheckBox("启用说话人识别，仅保留前 3 位响度说话人")
        self.speaker_detection.setChecked(True)
        form.addWidget(self.speaker_detection, 3, 2)

        form.addWidget(QLabel("ASR 模型："), 4, 0)
        self.asr_model = QComboBox()
        self.asr_model.setEditable(True)
        self.asr_model.addItems(["Qwen/Qwen3-ASR-0.6B", "Qwen/Qwen3-ASR-1.7B"])
        form.addWidget(self.asr_model, 4, 1, 1, 2)

        form.addWidget(QLabel("MT 模型："), 5, 0)
        self.mt_model = QComboBox()
        self.mt_model.setEditable(True)
        self.mt_model.addItems(["Helsinki-NLP/opus-mt-ja-zh", "tencent/HY-MT1.5-1.8B"])
        form.addWidget(self.mt_model, 5, 1)
        self.use_advanced_mt = QCheckBox("启用高级翻译回退链（优先尝试 7B）")
        form.addWidget(self.use_advanced_mt, 5, 2)

        self.chunk_size = QLineEdit("90")
        self.overlap = QLineEdit("2")
        self.quality_mode = QComboBox()
        self.quality_mode.addItems(["fast", "accurate"])
        self.audio_preset = QComboBox()
        self.audio_preset.addItems(["standard", "denoise", "aggressive"])

        settings_layout = QFormLayout()
        settings_layout.addRow("分块时长（秒）：", self.chunk_size)
        settings_layout.addRow("重叠时长（秒）：", self.overlap)
        settings_layout.addRow("质量模式：", self.quality_mode)
        settings_layout.addRow("音频增强：", self.audio_preset)
        form.addLayout(settings_layout, 6, 0, 1, 3)

        self._add_path_row(form, 7, "术语表文件：", self.glossary_path, self._browse_glossary)
        self._add_path_row(form, 8, "ASR 术语/修正：", self.asr_terms_path, self._browse_asr_terms)

        legend = QHBoxLayout()
        legend.addWidget(QLabel("说话人颜色："))
        for label, color in [("A", "#ffffff"), ("B", "#ffff66"), ("C", "#66ffff")]:
            chip = QLabel(f" Speaker {label} ")
            chip.setStyleSheet(f"background-color: {color}; color: #111; border: 1px solid #333; padding: 3px;")
            legend.addWidget(chip)
        legend.addStretch()
        form.addLayout(legend, 9, 0, 1, 3)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        root.addWidget(separator)

        buttons = QHBoxLayout()
        self.generate_btn = QPushButton("生成字幕")
        self.generate_btn.clicked.connect(self.generate_subtitles)
        self.burn_btn = QPushButton("烧录硬字幕")
        self.burn_btn.clicked.connect(self.burn_subtitles)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_all)
        self.help_btn = QPushButton("帮助")
        self.help_btn.clicked.connect(self.show_help)
        for button in [self.generate_btn, self.burn_btn, self.clear_btn, self.help_btn]:
            buttons.addWidget(button)
        buttons.addStretch()
        root.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        root.addWidget(self.status_label)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(240)
        root.addWidget(self.log_text)

    def _add_path_row(self, layout, row, label, edit, callback):
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(edit, row, 1)
        button = QPushButton("浏览...")
        button.clicked.connect(callback)
        layout.addWidget(button, row, 2)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv);;所有文件 (*.*)")
        if path:
            self.video_path.setText(path)
            if not self.output_dir.text().strip():
                self.output_dir.setText(os.path.dirname(path))

    def _browse_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字幕文件", self.output_dir.text() or "", "字幕文件 (*.srt *.ass);;所有文件 (*.*)")
        if path:
            self.srt_path.setText(path)

    def _browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir.text() or os.getcwd())
        if path:
            self.output_dir.setText(path)

    def _browse_glossary(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择术语表文件", "", "文本文件 (*.txt *.tsv *.csv);;所有文件 (*.*)")
        if path:
            self.glossary_path.setText(path)

    def _browse_asr_terms(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 ASR 术语/修正文件", "", "文本文件 (*.txt *.tsv *.csv);;所有文件 (*.*)")
        if path:
            self.asr_terms_path.setText(path)

    def _apply_tier_defaults(self):
        tier = MODEL_TIERS.get(self.model_tier.currentText(), MODEL_TIERS["Fast"])
        self.asr_model.setCurrentText(tier["asr"])
        self.mt_model.setCurrentText(tier["mt"])
        self.chunk_size.setText(tier["chunk"])
        self.quality_mode.setCurrentText(tier["quality"])

    def _set_processing(self, processing):
        for button in [self.generate_btn, self.burn_btn, self.clear_btn]:
            button.setEnabled(not processing)

    def _log(self, message):
        self.log_text.appendPlainText(str(message))

    def _update_progress(self, value, message):
        self.progress.setValue(int(max(0, min(100, value))))
        if message:
            self.status_label.setText(message)

    def _validate_common(self):
        if not self.video_path.text().strip() or not os.path.exists(self.video_path.text().strip()):
            QMessageBox.critical(self, "错误", "请选择有效的视频文件。")
            return False
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            QMessageBox.critical(self, "错误", "请选择输出目录。")
            return False
        os.makedirs(output_dir, exist_ok=True)
        try:
            chunk = int(self.chunk_size.text().strip())
            if chunk < 30 or chunk > 600:
                raise ValueError
            overlap = float(self.overlap.text().strip())
            if overlap < 0 or overlap > 10:
                raise ValueError
        except Exception:
            QMessageBox.critical(self, "错误", "分块时长必须为 30-600，重叠时长必须为 0-10。")
            return False
        for label, path in [("术语表文件", self.glossary_path.text().strip()), ("ASR 术语/修正文件", self.asr_terms_path.text().strip())]:
            if path and not os.path.exists(path):
                QMessageBox.critical(self, "错误", f"{label}不存在。")
                return False
        return True

    def _worker_finished(self, success, payload):
        self._set_processing(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.worker_thread = None
        self.worker = None
        if success:
            self.progress.setValue(100)
            self.status_label.setText("完成")
            if payload.lower().endswith((".srt", ".ass")):
                self.srt_path.setText(payload)
                self._log(f"双语 SRT 文件：{payload}")
                self._log("烧录时会优先使用同名 _styled.ass 彩色字幕。")
            QMessageBox.information(self, "成功", f"处理完成：\n{payload}")
        else:
            self.status_label.setText("失败")
            self._log(f"错误：{payload}")
            QMessageBox.critical(self, "错误", payload)

    def generate_subtitles(self):
        if not self._validate_common():
            return
        tier = MODEL_TIERS.get(self.model_tier.currentText(), MODEL_TIERS["Fast"])
        config = {
            "video_path": self.video_path.text().strip(),
            "output_dir": self.output_dir.text().strip(),
            "model_tier": tier["key"],
            "asr_model": self.asr_model.currentText().strip(),
            "mt_model": self.mt_model.currentText().strip(),
            "use_advanced_mt": self.use_advanced_mt.isChecked(),
            "quality_mode": self.quality_mode.currentText().strip(),
            "chunk_size": self.chunk_size.text().strip(),
            "overlap": self.overlap.text().strip(),
            "audio_preset": self.audio_preset.currentText().strip(),
            "glossary_path": self.glossary_path.text().strip() or None,
            "asr_terms_path": self.asr_terms_path.text().strip() or None,
            "enable_speaker_diarization": self.speaker_detection.isChecked(),
            "device": "cuda:0",
        }
        self._start_worker(SubtitleWorker(config))

    def burn_subtitles(self):
        if not self._validate_common():
            return
        subtitle_path = self.srt_path.text().strip()
        if not subtitle_path or not os.path.exists(subtitle_path):
            QMessageBox.critical(self, "错误", "请选择有效的 SRT 或 ASS 字幕文件。")
            return
        video_name = os.path.splitext(os.path.basename(self.video_path.text().strip()))[0]
        output_path = os.path.join(self.output_dir.text().strip(), f"{video_name}_cn_hardsub.mp4")
        self._start_worker(BurnWorker(self.video_path.text().strip(), subtitle_path, output_path))

    def _start_worker(self, worker):
        self._set_processing(True)
        self.progress.setValue(0)
        self.worker_thread = QThread()
        self.worker = worker
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._update_progress)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._worker_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.start()

    def clear_all(self):
        self.video_path.clear()
        self.srt_path.clear()
        self.output_dir.setText(os.getcwd())
        self.glossary_path.clear()
        self.asr_terms_path.clear()
        self.model_tier.setCurrentText("Fast")
        self.overlap.setText("2")
        self.audio_preset.setCurrentText("standard")
        self.speaker_detection.setChecked(True)
        self.use_advanced_mt.setChecked(False)
        self.log_text.clear()
        self.status_label.setText("就绪")
        self.progress.setValue(0)
        self._apply_tier_defaults()
        self._log_device_info()

    def _check_system_requirements(self):
        issues = []
        if sys.version_info < (3, 9):
            issues.append("Python 版本过低，需要 Python 3.9 或更高版本")
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, **_subprocess_kwargs())
            if result.returncode != 0:
                issues.append("找不到 FFmpeg 或无法运行")
        except FileNotFoundError:
            issues.append("FFmpeg 未安装或未加入 PATH")
        if issues:
            QMessageBox.warning(self, "系统检查", "检测到以下问题：\n\n" + "\n".join(issues))

    def _log_device_info(self):
        self._log("设备偏好：CUDA 显卡（cuda:0）")
        if torch.cuda.is_available():
            self._log(f"当前设备：CUDA 显卡 - {torch.cuda.get_device_name(0)}")
        else:
            self._log("当前设备：CPU（回退）")
        self._log("Speaker A/B/C 将分别使用白色、黄色、青色 ASS 字幕。")

    def show_help(self):
        QMessageBox.information(
            self,
            "帮助",
            "1. 选择视频和输出目录。\n"
            "2. 选择模型档位：Fast 适合有限显存，Balanced 提升翻译质量，Accurate 提升识别质量。\n"
            "3. 默认输出双语 SRT 和同名 _styled.ass 彩色中文字幕。\n"
            "4. 烧录硬字幕时会优先使用 _styled.ass，以保留说话人颜色。\n"
            "5. Traditional Chinese 由 OpenCC 后处理生成。",
        )

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(self, "确认", "正在处理中，确定要退出吗？")
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    window = SubtitleGeneratorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
