#!/usr/bin/env python3
"""
ytdlp_convert_gui.py — PyQt6 front-end for ytdlp_convert.sh
"""

import sys
import os
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QSpinBox,
    QTextEdit, QPlainTextEdit, QGroupBox, QLineEdit, QFrame,
    QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QProcess
from PyQt6.QtGui import QFont, QColor, QTextCursor, QPalette

# ── Locate ytdlp_convert.sh next to this script ───────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
YTDLP_SCRIPT = os.path.join(SCRIPT_DIR, "ytdlp_convert.sh")

PRESETS = [
    ("best",    "best — Best video+audio (MKV)"),
    ("mp4",     "mp4 — Best MP4-compatible"),
    ("2160",    "2160 — Up to 4K (MP4)"),
    ("1440",    "1440 — Up to 1440p (MP4)"),
    ("1080",    "1080 — Up to 1080p (MP4)"),
    ("720",     "720 — Up to 720p (MP4)"),
    ("480",     "480 — Up to 480p (MP4)"),
    ("mp3",     "mp3 — Audio only"),
    ("m4a",     "m4a — Audio only"),
    ("opus",    "opus — Audio only"),
    ("flac",    "flac — Audio only (lossless)"),
    ("wav",     "wav — Audio only (uncompressed)"),
    ("resolve", "resolve — DNxHR + PCM for DaVinci Resolve"),
]

DNX_QUALITIES = [
    "hq  — High Quality (default)",
    "sq  — Standard Quality",
    "lb  — Low Bitrate / Proxy",
    "hqx — High Quality 12-bit",
    "444 — Full 4:4:4 (max)",
]


# ── Worker — runs the bash script asynchronously, streams output ──────────────
class DownloadWorker(QObject):
    log_line = pyqtSignal(str)   # one line of merged stdout/stderr
    finished = pyqtSignal(int)   # exit code

    def __init__(self, cmd: list[str]):
        super().__init__()
        self._cmd = cmd
        self._buf = ""
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._done)
        self._proc.errorOccurred.connect(self._error)

    def start(self):
        self._proc.start(self._cmd[0], self._cmd[1:])

    def _read(self):
        raw = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        # yt-dlp progress can use \r; treat it like a newline
        self._buf += raw.replace("\r", "\n")
        *lines, self._buf = self._buf.split("\n")
        for line in lines:
            self.log_line.emit(line)

    def _done(self, exit_code, _status):
        self._read()
        if self._buf.strip():
            self.log_line.emit(self._buf)
        self._buf = ""
        self.finished.emit(exit_code)

    def _error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self.log_line.emit("[ERR] Failed to start: " + " ".join(self._cmd[:2]))
            self.finished.emit(127)

    def stop(self):
        if self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
            if not self._proc.waitForFinished(3000):
                self._proc.kill()


# ── Main window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("yt-dlp Converter")
        self.setMinimumSize(880, 760)
        self._worker = None
        self._build_ui()
        self._on_preset_changed()
        self._check_script()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("⬇  yt-dlp Converter")
        title.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        outer.addWidget(title)

        subtitle = QLabel("Download video or audio with yt-dlp presets and options")
        subtitle.setStyleSheet("color: #888;")
        outer.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        outer.addWidget(line)

        # ── URLs ──────────────────────────────────────────────────────────────
        urls_group = QGroupBox("URLs (one per line)")
        urls_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        urls_layout = QVBoxLayout(urls_group)
        self.urls_edit = QPlainTextEdit()
        self.urls_edit.setPlaceholderText("Paste video or playlist URLs here…")
        self.urls_edit.setFixedHeight(90)
        urls_layout.addWidget(self.urls_edit)
        outer.addWidget(urls_group)

        # ── Settings ──────────────────────────────────────────────────────────
        settings = QGroupBox("Settings")
        settings.setStyleSheet("QGroupBox { font-weight: bold; }")
        grid = QVBoxLayout(settings)
        grid.setSpacing(10)

        # Output folder
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder:"))
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Default: ./yt_downloads  (leave blank to use default)")
        out_row.addWidget(self.out_edit, 1)
        out_btn = QPushButton("Browse…")
        out_btn.setFixedWidth(90)
        out_btn.clicked.connect(self._pick_output)
        out_row.addWidget(out_btn)
        grid.addLayout(out_row)

        # Preset + DNxHR quality
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        for _, label in PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.setFixedWidth(300)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo)

        preset_row.addSpacing(24)
        self.dnx_label = QLabel("DNxHR quality:")
        preset_row.addWidget(self.dnx_label)
        self.dnx_combo = QComboBox()
        self.dnx_combo.addItems(DNX_QUALITIES)
        self.dnx_combo.setFixedWidth(220)
        preset_row.addWidget(self.dnx_combo)
        preset_row.addStretch()
        grid.addLayout(preset_row)

        # Checkboxes row 1
        chk1 = QHBoxLayout()
        self.playlist_check = QCheckBox("Allow playlists")
        self.subs_check = QCheckBox("Subtitles (embed)")
        self.thumb_check = QCheckBox("Embed thumbnail")
        self.meta_check = QCheckBox("Embed metadata")
        self.sb_check = QCheckBox("SponsorBlock")
        for c in (self.playlist_check, self.subs_check, self.thumb_check,
                  self.meta_check, self.sb_check):
            chk1.addWidget(c)
        chk1.addStretch()
        grid.addLayout(chk1)

        # Numeric / text options row
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Sub langs:"))
        self.sublang_edit = QLineEdit("en")
        self.sublang_edit.setFixedWidth(90)
        opt_row.addWidget(self.sublang_edit)

        opt_row.addSpacing(16)
        opt_row.addWidget(QLabel("Rate limit:"))
        self.rate_edit = QLineEdit()
        self.rate_edit.setPlaceholderText("e.g. 2M")
        self.rate_edit.setFixedWidth(80)
        opt_row.addWidget(self.rate_edit)

        opt_row.addSpacing(16)
        opt_row.addWidget(QLabel("Fragments:"))
        self.frag_spin = QSpinBox()
        self.frag_spin.setRange(1, 16)
        self.frag_spin.setValue(1)
        self.frag_spin.setFixedWidth(60)
        opt_row.addWidget(self.frag_spin)

        opt_row.addSpacing(16)
        opt_row.addWidget(QLabel("Cookies from:"))
        self.cookie_combo = QComboBox()
        self.cookie_combo.addItems(["(none)", "firefox", "chrome", "chromium",
                                    "brave", "edge", "opera", "vivaldi"])
        self.cookie_combo.setFixedWidth(110)
        opt_row.addWidget(self.cookie_combo)
        opt_row.addStretch()
        grid.addLayout(opt_row)

        # Custom format + extra args
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Custom format:"))
        self.format_edit = QLineEdit()
        self.format_edit.setPlaceholderText("Optional yt-dlp -f string, e.g. bv*[fps<=30]+ba")
        fmt_row.addWidget(self.format_edit, 1)
        grid.addLayout(fmt_row)

        extra_row = QHBoxLayout()
        extra_row.addWidget(QLabel("Extra args:"))
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("Optional raw yt-dlp arguments")
        extra_row.addWidget(self.extra_edit, 1)
        grid.addLayout(extra_row)

        # Archive file + dry run
        arch_row = QHBoxLayout()
        arch_row.addWidget(QLabel("Archive file:"))
        self.archive_edit = QLineEdit()
        self.archive_edit.setPlaceholderText("Optional: skip videos already downloaded")
        arch_row.addWidget(self.archive_edit, 1)
        arch_btn = QPushButton("Browse…")
        arch_btn.setFixedWidth(90)
        arch_btn.clicked.connect(self._pick_archive)
        arch_row.addWidget(arch_btn)
        arch_row.addSpacing(16)
        self.dry_check = QCheckBox("Dry-run (preview only)")
        arch_row.addWidget(self.dry_check)
        grid.addLayout(arch_row)

        outer.addWidget(settings)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  Start Download")
        self.start_btn.setFixedHeight(36)
        self.start_btn.setStyleSheet(
            "QPushButton { background:#2ecc71; color:#000; font-weight:bold; border-radius:4px; }"
            "QPushButton:hover { background:#27ae60; }"
            "QPushButton:disabled { background:#555; color:#888; }"
        )
        self.start_btn.clicked.connect(self._start)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "QPushButton { background:#e74c3c; color:#fff; font-weight:bold; border-radius:4px; }"
            "QPushButton:hover { background:#c0392b; }"
            "QPushButton:disabled { background:#555; color:#888; }"
        )
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.stop_btn)

        clear_btn = QPushButton("🗑  Clear Log")
        clear_btn.setFixedHeight(36)
        clear_btn.setFixedWidth(110)
        clear_btn.clicked.connect(lambda: self.log.clear())
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #aaa;")
        btn_row.addWidget(self.status_label)
        outer.addLayout(btn_row)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border:none; background:#333; border-radius:3px; }"
            "QProgressBar::chunk { background:#2ecc71; border-radius:3px; }"
        )
        outer.addWidget(self.progress)

        # ── Log output ────────────────────────────────────────────────────────
        log_group = QGroupBox("Output Log")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout(log_group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Monospace", 9))
        self.log.setStyleSheet(
            "QTextEdit { background:#1a1a1a; color:#e0e0e0; border:1px solid #333; }"
        )
        log_layout.addWidget(self.log)
        outer.addWidget(log_group, 1)

    # ── Script check ──────────────────────────────────────────────────────────
    def _check_script(self):
        if not os.path.isfile(YTDLP_SCRIPT):
            self._log_warn(f"ytdlp_convert.sh not found at: {YTDLP_SCRIPT}")
            self._log_warn("Place ytdlp_convert.sh in the same folder as this GUI script.")
            self.start_btn.setEnabled(False)
        elif not os.access(YTDLP_SCRIPT, os.X_OK):
            self._log_warn("ytdlp_convert.sh is not executable. Run:")
            self._log_warn(f"  chmod +x {YTDLP_SCRIPT}")
            self.start_btn.setEnabled(False)
        else:
            self._log_info(f"Found: {YTDLP_SCRIPT}")

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _on_preset_changed(self):
        is_resolve = PRESETS[self.preset_combo.currentIndex()][0] == "resolve"
        self.dnx_label.setEnabled(is_resolve)
        self.dnx_combo.setEnabled(is_resolve)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder", os.path.expanduser("~"))
        if d:
            self.out_edit.setText(d)

    def _pick_archive(self):
        f, _ = QFileDialog.getSaveFileName(
            self, "Select Archive File", os.path.expanduser("~/yt_archive.txt"),
            "Text files (*.txt);;All files (*)"
        )
        if f:
            self.archive_edit.setText(f)

    # ── Build command ─────────────────────────────────────────────────────────
    def _build_cmd(self, urls: list[str], batch_path: str | None) -> list[str]:
        preset = PRESETS[self.preset_combo.currentIndex()][0]
        cmd = ["bash", YTDLP_SCRIPT, "-p", preset]

        if preset == "resolve":
            cmd += ["-Q", self.dnx_combo.currentText().split()[0]]

        out = self.out_edit.text().strip()
        if out:
            cmd += ["-o", out]
        if self.playlist_check.isChecked():
            cmd.append("-P")
        if self.subs_check.isChecked():
            cmd.append("-s")
            langs = self.sublang_edit.text().strip()
            if langs:
                cmd += ["-l", langs]
        if self.thumb_check.isChecked():
            cmd.append("-t")
        if self.meta_check.isChecked():
            cmd.append("-m")
        if self.sb_check.isChecked():
            cmd.append("-k")

        rate = self.rate_edit.text().strip()
        if rate:
            cmd += ["-r", rate]
        if self.frag_spin.value() > 1:
            cmd += ["-N", str(self.frag_spin.value())]
        if self.cookie_combo.currentIndex() > 0:
            cmd += ["-b", self.cookie_combo.currentText()]

        fmt = self.format_edit.text().strip()
        if fmt:
            cmd += ["-f", fmt]
        extra = self.extra_edit.text().strip()
        if extra:
            cmd += ["-x", extra]
        archive = self.archive_edit.text().strip()
        if archive:
            cmd += ["-A", archive]
        if self.dry_check.isChecked():
            cmd.append("-n")

        if batch_path:
            cmd += ["-a", batch_path]
        else:
            cmd += urls
        return cmd

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _start(self):
        urls = [u.strip() for u in self.urls_edit.toPlainText().splitlines() if u.strip()]
        if not urls:
            self._log_warn("Please paste at least one URL first.")
            return

        # Multiple URLs go through a temp batch file so nothing needs shell quoting
        self._batch_tmp = None
        batch_path = None
        if len(urls) > 1:
            self._batch_tmp = tempfile.NamedTemporaryFile(
                "w", suffix=".txt", prefix="ytdlp_urls_", delete=False)
            self._batch_tmp.write("\n".join(urls) + "\n")
            self._batch_tmp.close()
            batch_path = self._batch_tmp.name

        cmd = self._build_cmd(urls, batch_path)
        self._log_info("Running: " + " ".join(cmd))
        self.log.append("")

        self._worker = DownloadWorker(cmd)
        self._worker.log_line.connect(self._on_line)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.status_label.setText("Downloading…")

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.status_label.setText("Stopped by user")

    # ── Log helpers ───────────────────────────────────────────────────────────
    def _log_color(self, text: str, color: str):
        self.log.setTextColor(QColor(color))
        self.log.append(text)
        self.log.setTextColor(QColor("#e0e0e0"))
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _log_info(self, text: str): self._log_color(text, "#5dade2")
    def _log_warn(self, text: str): self._log_color(text, "#f39c12")
    def _log_ok(self, text: str):   self._log_color(text, "#2ecc71")
    def _log_err(self, text: str):  self._log_color(text, "#e74c3c")

    # ── Handle output lines ───────────────────────────────────────────────────
    def _on_line(self, line: str):
        stripped = line.strip()
        if not stripped:
            self.log.append("")
            return
        low = stripped.lower()
        if "[ok]" in low or "finished" in low:
            self._log_ok(stripped)
        elif "[err]" in low or low.startswith("error") or "failed" in low:
            self._log_err(stripped)
        elif "[warn]" in low or low.startswith("warning"):
            self._log_warn(stripped)
        elif "[info]" in low or low.startswith("[download]") or low.startswith("[youtube]"):
            self._log_info(stripped)
        else:
            self.log.append(stripped)
            self.log.moveCursor(QTextCursor.MoveOperation.End)

    # ── Finished ──────────────────────────────────────────────────────────────
    def _on_done(self, exit_code: int):
        self.progress.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if getattr(self, "_batch_tmp", None):
            try:
                os.unlink(self._batch_tmp.name)
            except OSError:
                pass
            self._batch_tmp = None
        if exit_code == 0:
            self._log_ok(f"\n✔ Complete (exit {exit_code})")
            self.status_label.setText("Done ✔")
        else:
            self._log_err(f"\n✘ Process exited with code {exit_code}")
            self.status_label.setText(f"Error (exit {exit_code})")
        self._worker = None

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base,            QColor(22, 22, 22))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button,          QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText,      Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(46, 204, 113))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
