import json
import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui_components import StrokedLabel
from i18n import available_languages, restart_application, tr
from translator import ENGINES, LANGUAGES
import lyrics_sources

def _settings_path():
    """Keep settings next to the app so a restart cannot lose the language."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    preferred = os.path.join(base, "settings.json")
    legacy = os.path.abspath("settings.json")
    if not os.path.exists(preferred) and os.path.exists(legacy):
        return legacy
    return preferred


SETTINGS_FILE = _settings_path()

OVERLAY_WIDTH = 1200
OVERLAY_HEIGHT = 400


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def get_track_info_height(font_size):
    return max(60, int(font_size * 3))


def get_track_info_width(screen_width):
    return min(screen_width, max(OVERLAY_WIDTH, int(screen_width * 0.9)))


def get_track_info_gap(font_size):
    return max(6, int(font_size * 0.5))


def compute_overlay_geometry(settings, screen_geom):
    width = OVERLAY_WIDTH
    height = OVERLAY_HEIGHT

    extra_y = height // 2
    min_y_offset = -extra_y
    max_y_offset = screen_geom.height() - height + extra_y
    y_offset = clamp(settings.get("window_y_offset", 0), min_y_offset, max_y_offset)
    base_y = screen_geom.y() + (screen_geom.height() - height)
    y_pos = base_y - y_offset

    max_x_offset = max(0, (screen_geom.width() - width) // 2)
    x_offset = clamp(settings.get("window_x_offset", 0), -max_x_offset, max_x_offset)

    center_x = screen_geom.x() + (screen_geom.width() - width) // 2
    x_pos = center_x + x_offset

    min_x = screen_geom.x()
    max_x = screen_geom.x() + screen_geom.width() - width
    if max_x < min_x:
        x_pos = center_x
    else:
        x_pos = clamp(x_pos, min_x, max_x)

    return {
        "x": x_pos,
        "y": y_pos,
        "width": width,
        "height": height,
        "min_y_offset": min_y_offset,
        "max_y_offset": max_y_offset,
    }


DEFAULT_SETTINGS = {
    "highlight_color": "#ffff00",
    "stroke_color": "#000000",
    "normal_color": "#ebebeb",
    "background_color": "rgba(0, 0, 0, 100)",
    "font_family": "Century Gothic",
    "font_size_highlight": 24,
    "font_size_normal": 14,
    "window_y_offset": 0,
    "window_x_offset": 0,
    "screen_index": 0,
    "num_history_lines": 0,
    "num_future_lines": 1,
    "sync_offset_ms": 0,
    "enable_animations": False,
    "animation_type": "fade",
    "stroke_enabled_highlight": True,
    "stroke_enabled_context": False,
    "toggle_hotkey": "",
    "track_info_enabled": False,
    "track_info_x_offset": 0,
    "track_info_y_offset": 0,
    "language": "auto",
    # --- Lyrics lookup ---
    "lyrics_source": "auto",
    # --- Lyrics translation ---
    "translation_enabled": False,
    "translation_engine": "auto",
    "translation_source": "auto",
    "translation_target": "zh-Hans",
    "translation_font_size": 16,
    "translation_color": "#7fd7ff",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
}


class SettingsManager:
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, settings_manager, parent=None, translation_controller=None):
        super().__init__(parent)
        self.manager = settings_manager
        self.translation_controller = translation_controller
        self.temp_settings = self.manager.settings.copy()
        self.setWindowTitle(tr("MusicLine Settings"))
        self.setFixedWidth(450)
        # Four tabs would otherwise make the dialog taller than a 768p screen.
        # Scrollable pages keep Save / Cancel reachable on small displays.
        self.setMaximumHeight(650)
        if translation_controller is not None:
            translation_controller.test_finished.connect(self._on_test_finished)

        # Keep window on top
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        main_layout = QVBoxLayout()

        # --- Preview Section (Always Visible) ---
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(
            f"background-color: {self.temp_settings.get('background_color', '#000000')}; border-radius: 8px;"
        )
        self.preview_frame.setMinimumHeight(140)

        preview_layout = QVBoxLayout()
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_prev = StrokedLabel(tr("Previous Lyric Line"))
        self.preview_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_prev)

        self.preview_label = StrokedLabel(tr("Current Active Lyric"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)

        self.preview_translation = StrokedLabel(tr("Translated Lyric Line"))
        self.preview_translation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_translation.setStrokeEnabled(True)
        preview_layout.addWidget(self.preview_translation)

        self.preview_next = StrokedLabel(tr("Upcoming Lyric Line"))
        self.preview_next.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_next)

        self.preview_frame.setLayout(preview_layout)
        main_layout.addWidget(QLabel(tr("<b>Live Preview:</b>")))
        main_layout.addWidget(self.preview_frame)
        main_layout.addSpacing(10)

        # --- Tabbed Categories ---
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(420)

        self.tabs.addTab(self._scrollable(self.create_appearance_tab()), tr("Appearance"))
        self.tabs.addTab(self._scrollable(self.create_layout_tab()), tr("Layout"))
        self.tabs.addTab(
            self._scrollable(self.create_translation_tab()), tr("Translation")
        )
        self.tabs.addTab(self._scrollable(self.create_system_tab()), tr("System"))

        main_layout.addWidget(self.tabs)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self.reset_defaults
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(
            tr("Restore Defaults")
        )
        main_layout.addWidget(buttons)

        self.setLayout(main_layout)
        self.update_preview()

    @staticmethod
    def _scrollable(page):
        area = QScrollArea()
        area.setWidget(page)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return area

    def create_appearance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Text Style Group
        font_group = QGroupBox(tr("Typography"))
        font_layout = QFormLayout()

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.temp_settings["font_family"]))
        self.font_combo.currentFontChanged.connect(self.update_font)
        font_layout.addRow(tr("Font Family:"), self.font_combo)

        self.spin_size_high = QSpinBox()
        self.spin_size_high.setRange(8, 72)
        self.spin_size_high.setValue(self.temp_settings["font_size_highlight"])
        self.spin_size_high.valueChanged.connect(
            lambda v: self.update_setting("font_size_highlight", v)
        )
        font_layout.addRow(tr("Highlight Size:"), self.spin_size_high)

        self.spin_size_norm = QSpinBox()
        self.spin_size_norm.setRange(8, 72)
        self.spin_size_norm.setValue(self.temp_settings["font_size_normal"])
        self.spin_size_norm.valueChanged.connect(
            lambda v: self.update_setting("font_size_normal", v)
        )
        font_layout.addRow(tr("Context Size:"), self.spin_size_norm)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # Colors & Effects Group
        color_group = QGroupBox(tr("Colors & Visuals"))
        color_layout = QFormLayout()

        self.btn_color_high = QPushButton(tr("Choose..."))
        self.btn_color_high.setFixedWidth(100)
        self.btn_color_high.setStyleSheet(
            f"background-color: {self.temp_settings['highlight_color']}"
        )
        self.btn_color_high.clicked.connect(
            lambda: self.pick_color("highlight_color", self.btn_color_high)
        )
        color_layout.addRow(tr("Highlight Color:"), self.btn_color_high)

        self.btn_color_norm = QPushButton(tr("Choose..."))
        self.btn_color_norm.setFixedWidth(100)
        self.btn_color_norm.setStyleSheet(
            f"background-color: {self.temp_settings['normal_color']}"
        )
        self.btn_color_norm.clicked.connect(
            lambda: self.pick_color("normal_color", self.btn_color_norm)
        )
        color_layout.addRow(tr("Context Color:"), self.btn_color_norm)

        self.btn_color_stroke = QPushButton(tr("Choose..."))
        self.btn_color_stroke.setFixedWidth(100)
        self.btn_color_stroke.setStyleSheet(
            f"background-color: {self.temp_settings.get('stroke_color', '#000000')}"
        )
        self.btn_color_stroke.clicked.connect(
            lambda: self.pick_color("stroke_color", self.btn_color_stroke)
        )
        color_layout.addRow(tr("Stroke Color:"), self.btn_color_stroke)

        self.check_anim = QCheckBox(tr("Enable Transitions"))
        self.check_anim.setChecked(self.temp_settings.get("enable_animations", True))
        self.check_anim.toggled.connect(
            lambda v: self.update_setting("enable_animations", v)
        )
        color_layout.addRow(tr("Visuals:"), self.check_anim)
        color_layout.addRow(
            QLabel(tr("<small>Apply smooth motion when the lyric line changes.</small>"))
        )

        self.combo_anim_type = QComboBox()
        for _effect in ("fade", "slide", "zoom"):
            self.combo_anim_type.addItem(tr(_effect), _effect)
        _anim = self.temp_settings.get("animation_type", "fade")
        _idx = self.combo_anim_type.findData(_anim)
        if _idx >= 0:
            self.combo_anim_type.setCurrentIndex(_idx)

        def _on_anim_changed(_index):
            value = self.combo_anim_type.currentData()
            if value:
                self.update_setting("animation_type", value)

        self.combo_anim_type.currentIndexChanged.connect(_on_anim_changed)
        color_layout.addRow(tr("Effect Style:"), self.combo_anim_type)

        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_layout_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Position Group
        pos_group = QGroupBox(tr("Screen Position"))
        pos_layout = QVBoxLayout()

        screen_layout = QFormLayout()
        self.screen_combo = QComboBox()
        screens = QApplication.screens()
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            name = screen.name() or tr("Display {n}", n=i + 1)
            self.screen_combo.addItem(
                f"{name} ({geometry.width()}x{geometry.height()})", i
            )

        screen_index = self.temp_settings.get("screen_index", 0)
        if 0 <= screen_index < self.screen_combo.count():
            self.screen_combo.setCurrentIndex(screen_index)
        self.screen_combo.currentIndexChanged.connect(self.update_screen_selection)
        screen_layout.addRow(tr("Display:"), self.screen_combo)
        pos_layout.addLayout(screen_layout)

        # Vertical Position
        y_layout = QHBoxLayout()
        self.slider_offset_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_offset_y.setValue(self.temp_settings["window_y_offset"])
        self.slider_offset_y.valueChanged.connect(
            lambda v: self.update_setting("window_y_offset", v)
        )

        self.spin_offset_y = QSpinBox()
        self.spin_offset_y.setValue(self.temp_settings["window_y_offset"])
        self.spin_offset_y.valueChanged.connect(
            lambda v: self.update_setting("window_y_offset", v)
        )

        self.slider_offset_y.valueChanged.connect(self.spin_offset_y.setValue)
        self.spin_offset_y.valueChanged.connect(self.slider_offset_y.setValue)

        y_layout.addWidget(QLabel(tr("Screen Bottom")))
        y_layout.addWidget(self.slider_offset_y)
        y_layout.addWidget(QLabel(tr("Screen Top")))
        y_layout.addWidget(self.spin_offset_y)

        pos_layout.addLayout(y_layout)
        pos_layout.addWidget(
            QLabel(
                tr("<small>Adjust the vertical height. Negative values push lower.</small>")
            )
        )

        # Horizontal Position
        x_layout = QHBoxLayout()
        self.slider_offset_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_offset_x.setValue(self.temp_settings.get("window_x_offset", 0))
        self.slider_offset_x.valueChanged.connect(
            lambda v: self.update_setting("window_x_offset", v)
        )

        self.spin_offset_x = QSpinBox()
        self.spin_offset_x.setValue(self.temp_settings.get("window_x_offset", 0))
        self.spin_offset_x.valueChanged.connect(
            lambda v: self.update_setting("window_x_offset", v)
        )

        self.slider_offset_x.valueChanged.connect(self.spin_offset_x.setValue)
        self.spin_offset_x.valueChanged.connect(self.slider_offset_x.setValue)

        x_layout.addWidget(QLabel(tr("Screen Left")))
        x_layout.addWidget(self.slider_offset_x)
        x_layout.addWidget(QLabel(tr("Screen Right")))
        x_layout.addWidget(self.spin_offset_x)

        pos_layout.addLayout(x_layout)
        pos_layout.addWidget(
            QLabel(tr("<small>Adjust the horizontal position. 0 = center.</small>"))
        )

        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # Context Group
        ctx_group = QGroupBox(tr("Lyric Lines"))
        ctx_layout = QFormLayout()

        self.spin_history = QSpinBox()
        self.spin_history.setRange(0, 5)
        self.spin_history.setValue(self.temp_settings.get("num_history_lines", 1))
        self.spin_history.valueChanged.connect(
            lambda v: self.update_setting("num_history_lines", v)
        )
        ctx_layout.addRow(tr("History Lines:"), self.spin_history)
        ctx_layout.addRow(
            QLabel(
                tr("<small>Number of previous lines to keep visible above the current one.</small>")
            )
        )

        self.spin_future = QSpinBox()
        self.spin_future.setRange(0, 5)
        self.spin_future.setValue(self.temp_settings.get("num_future_lines", 1))
        self.spin_future.valueChanged.connect(
            lambda v: self.update_setting("num_future_lines", v)
        )
        ctx_layout.addRow(tr("Upcoming Lines:"), self.spin_future)
        ctx_layout.addRow(
            QLabel(
                tr("<small>Number of future lines to show ahead of time below the current one.</small>")
            )
        )

        ctx_group.setLayout(ctx_layout)
        layout.addWidget(ctx_group)

        # Track Info Group
        track_group = QGroupBox(tr("Track Info"))
        track_layout = QVBoxLayout()

        self.check_track_info = QCheckBox(tr("Show song and artist permanently"))
        self.check_track_info.setChecked(
            self.temp_settings.get("track_info_enabled", False)
        )
        self.check_track_info.toggled.connect(
            lambda v: self.update_setting("track_info_enabled", v)
        )
        track_layout.addWidget(self.check_track_info)

        track_x_layout = QHBoxLayout()
        self.slider_track_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_track_x.setValue(self.temp_settings.get("track_info_x_offset", 0))
        self.slider_track_x.valueChanged.connect(
            lambda v: self.update_setting("track_info_x_offset", v)
        )

        self.spin_track_x = QSpinBox()
        self.spin_track_x.setValue(self.temp_settings.get("track_info_x_offset", 0))
        self.spin_track_x.valueChanged.connect(
            lambda v: self.update_setting("track_info_x_offset", v)
        )

        self.slider_track_x.valueChanged.connect(self.spin_track_x.setValue)
        self.spin_track_x.valueChanged.connect(self.slider_track_x.setValue)

        track_x_layout.addWidget(QLabel(tr("Left")))
        track_x_layout.addWidget(self.slider_track_x)
        track_x_layout.addWidget(QLabel(tr("Right")))
        track_x_layout.addWidget(self.spin_track_x)
        track_layout.addLayout(track_x_layout)

        track_y_layout = QHBoxLayout()
        self.slider_track_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_track_y.setValue(self.temp_settings.get("track_info_y_offset", 0))
        self.slider_track_y.valueChanged.connect(
            lambda v: self.update_setting("track_info_y_offset", v)
        )

        self.spin_track_y = QSpinBox()
        self.spin_track_y.setValue(self.temp_settings.get("track_info_y_offset", 0))
        self.spin_track_y.valueChanged.connect(
            lambda v: self.update_setting("track_info_y_offset", v)
        )

        self.slider_track_y.valueChanged.connect(self.spin_track_y.setValue)
        self.spin_track_y.valueChanged.connect(self.slider_track_y.setValue)

        track_y_layout.addWidget(QLabel(tr("Top")))
        track_y_layout.addWidget(self.slider_track_y)
        track_y_layout.addWidget(QLabel(tr("Bottom")))
        track_y_layout.addWidget(self.spin_track_y)
        track_layout.addLayout(track_y_layout)

        track_layout.addWidget(
            QLabel(tr("<small>Offsets are relative to the lyrics overlay.</small>"))
        )

        track_group.setLayout(track_layout)
        layout.addWidget(track_group)

        # Stroke Toggle Group
        stroke_group = QGroupBox(tr("Stroke/Outline Toggles"))
        stroke_layout = QHBoxLayout()

        self.check_stroke_high = QCheckBox(tr("On Highlight"))
        self.check_stroke_high.setChecked(
            self.temp_settings.get("stroke_enabled_highlight", True)
        )
        self.check_stroke_high.toggled.connect(
            lambda v: self.update_setting("stroke_enabled_highlight", v)
        )

        self.check_stroke_context = QCheckBox(tr("On Context"))
        self.check_stroke_context.setChecked(
            self.temp_settings.get("stroke_enabled_context", True)
        )
        self.check_stroke_context.toggled.connect(
            lambda v: self.update_setting("stroke_enabled_context", v)
        )

        stroke_layout.addWidget(self.check_stroke_high)
        stroke_layout.addWidget(self.check_stroke_context)
        stroke_group.setLayout(stroke_layout)
        layout.addWidget(stroke_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_translation_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # --- General ---
        general = QGroupBox(tr("Lyrics Translation"))
        general_layout = QFormLayout()

        self.check_translation = QCheckBox(tr("Enable automatic translation"))
        self.check_translation.setChecked(
            self.temp_settings.get("translation_enabled", False)
        )
        self.check_translation.toggled.connect(
            lambda v: self.update_setting("translation_enabled", v)
        )
        general_layout.addRow(self.check_translation)

        self.combo_translation_source = QComboBox()
        for _lang in LANGUAGES:
            _name = (
                tr("Auto detect")
                if _lang["id"] == "auto"
                else _lang["name"]
            )
            self.combo_translation_source.addItem(_name, _lang["id"])
        _src_idx = self.combo_translation_source.findData(
            self.temp_settings.get("translation_source", "auto")
        )
        if _src_idx >= 0:
            self.combo_translation_source.setCurrentIndex(_src_idx)
        self.combo_translation_source.currentIndexChanged.connect(
            lambda _i: self.update_setting(
                "translation_source", self.combo_translation_source.currentData()
            )
        )
        general_layout.addRow(tr("From:"), self.combo_translation_source)

        self.combo_translation_target = QComboBox()
        for _lang in LANGUAGES:
            if _lang["id"] == "auto":
                continue
            self.combo_translation_target.addItem(_lang["name"], _lang["id"])
        _tgt_idx = self.combo_translation_target.findData(
            self.temp_settings.get("translation_target", "zh-Hans")
        )
        if _tgt_idx >= 0:
            self.combo_translation_target.setCurrentIndex(_tgt_idx)
        self.combo_translation_target.currentIndexChanged.connect(
            lambda _i: self.update_setting(
                "translation_target", self.combo_translation_target.currentData()
            )
        )
        general_layout.addRow(tr("To:"), self.combo_translation_target)

        self.spin_translation_size = QSpinBox()
        self.spin_translation_size.setRange(8, 72)
        self.spin_translation_size.setValue(
            self.temp_settings.get("translation_font_size", 16)
        )
        self.spin_translation_size.valueChanged.connect(
            lambda v: self.update_setting("translation_font_size", v)
        )
        general_layout.addRow(tr("Translation Size:"), self.spin_translation_size)

        self.btn_color_translation = QPushButton(tr("Choose..."))
        self.btn_color_translation.setFixedWidth(100)
        self.btn_color_translation.setStyleSheet(
            f"background-color: {self.temp_settings.get('translation_color', '#7fd7ff')}"
        )
        self.btn_color_translation.clicked.connect(
            lambda: self.pick_color(
                "translation_color", self.btn_color_translation
            )
        )
        general_layout.addRow(tr("Translation Color:"), self.btn_color_translation)
        general_layout.addRow(
            QLabel(tr("<small>Translations appear directly below the active lyric line.</small>"))
        )
        general.setLayout(general_layout)
        layout.addWidget(general)

        # --- Engine ---
        engine_group = QGroupBox(tr("Translation Engine"))
        engine_layout = QFormLayout()

        self.combo_translation_engine = QComboBox()
        for _engine_id, _label in ENGINES:
            self.combo_translation_engine.addItem(tr(_label), _engine_id)
        _eng_idx = self.combo_translation_engine.findData(
            self.temp_settings.get("translation_engine", "auto")
        )
        if _eng_idx >= 0:
            self.combo_translation_engine.setCurrentIndex(_eng_idx)
        self.combo_translation_engine.currentIndexChanged.connect(
            lambda _i: self.update_setting(
                "translation_engine", self.combo_translation_engine.currentData()
            )
        )
        engine_layout.addRow(tr("Engine:"), self.combo_translation_engine)
        engine_layout.addRow(
            QLabel(
                tr(
                    "<small>Built-in engines are free and need no key. They try Bing, then Google, then MyMemory. Baidu is not used.</small>"
                )
            )
        )
        engine_group.setLayout(engine_layout)
        layout.addWidget(engine_group)

        # --- AI API ---
        ai_group = QGroupBox(tr("Custom AI API (OpenAI compatible)"))
        ai_layout = QFormLayout()

        self.edit_ai_base = QLineEdit(
            self.temp_settings.get("ai_base_url", "https://api.openai.com/v1")
        )
        self.edit_ai_base.setPlaceholderText("https://api.openai.com/v1")
        self.edit_ai_base.textChanged.connect(
            lambda v: self.update_setting("ai_base_url", v)
        )
        ai_layout.addRow(tr("API Base URL:"), self.edit_ai_base)

        key_row = QHBoxLayout()
        self.edit_ai_key = QLineEdit(self.temp_settings.get("ai_api_key", ""))
        self.edit_ai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_ai_key.setPlaceholderText("sk-...")
        self.edit_ai_key.textChanged.connect(
            lambda v: self.update_setting("ai_api_key", v)
        )
        key_row.addWidget(self.edit_ai_key)
        self.check_show_key = QCheckBox(tr("Show key"))
        self.check_show_key.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.check_show_key)
        ai_layout.addRow(tr("API Key:"), key_row)

        self.edit_ai_model = QLineEdit(
            self.temp_settings.get("ai_model", "gpt-4o-mini")
        )
        self.edit_ai_model.setPlaceholderText("gpt-4o-mini")
        self.edit_ai_model.textChanged.connect(
            lambda v: self.update_setting("ai_model", v)
        )
        ai_layout.addRow(tr("Model:"), self.edit_ai_model)
        ai_layout.addRow(
            QLabel(
                tr(
                    "<small>Works with OpenAI, DeepSeek, Moonshot, Ollama, LM Studio or any /chat/completions endpoint.</small>"
                )
            )
        )
        ai_layout.addRow(
            QLabel(tr("<small>The key is stored locally in settings.json.</small>"))
        )

        self.btn_test_translation = QPushButton(tr("Test Connection"))
        self.btn_test_translation.clicked.connect(self._test_translation)
        ai_layout.addRow(self.btn_test_translation)

        self.label_test_result = QLabel("")
        self.label_test_result.setWordWrap(True)
        self.label_test_result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        ai_layout.addRow(self.label_test_result)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _toggle_key_visibility(self, visible):
        self.edit_ai_key.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def _test_translation(self):
        if self.translation_controller is None:
            self.label_test_result.setText(tr("Translation controller unavailable"))
            return
        self.btn_test_translation.setEnabled(False)
        self.btn_test_translation.setText(tr("Testing..."))
        self.label_test_result.setText(
            tr("<small>Testing the selected engine, please wait...</small>")
        )
        self.translation_controller.test_engine(self.temp_settings.copy())

    def _on_test_finished(self, ok, detail):
        self.btn_test_translation.setEnabled(True)
        self.btn_test_translation.setText(tr("Test Connection"))
        short = detail if len(detail) <= 160 else detail[:157] + "..."
        self.label_test_result.setText(
            tr("Connection OK: {result}", result=short)
            if ok
            else tr("Connection failed: {error}", error=short)
        )

    def create_system_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Sync Group
        sync_group = QGroupBox(tr("Timing & Sync"))
        sync_layout = QFormLayout()

        self.spin_sync = QDoubleSpinBox()
        self.spin_sync.setRange(-10.0, 10.0)
        self.spin_sync.setSingleStep(0.1)
        self.spin_sync.setValue(self.temp_settings.get("sync_offset_ms", 0) / 1000.0)
        self.spin_sync.valueChanged.connect(
            lambda v: self.update_setting("sync_offset_ms", int(v * 1000))
        )
        sync_layout.addRow(tr("Sync Offset (sec):"), self.spin_sync)
        sync_layout.addRow(
            QLabel(tr("<small>Use this if lyrics are consistently early or late.</small>"))
        )

        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)

        # Controls Group
        ctrl_group = QGroupBox(tr("Controls"))
        ctrl_layout = QFormLayout()

        self.hotkey_edit = QKeySequenceEdit()
        current_hotkey = self.temp_settings.get("toggle_hotkey", "")
        if current_hotkey:
            self.hotkey_edit.setKeySequence(QKeySequence(current_hotkey))
        self.hotkey_edit.keySequenceChanged.connect(self.update_hotkey)

        ctrl_layout.addRow(tr("Toggle Overlay Hotkey:"), self.hotkey_edit)
        ctrl_layout.addRow(
            QLabel(
                tr("<small>Click and press a key combination (e.g., Ctrl+L) to hide/show.</small>")
            )
        )

        ctrl_group.setLayout(ctrl_layout)
        layout.addWidget(ctrl_group)

        # Language Group
        lang_group = QGroupBox(tr("Language"))
        lang_layout = QFormLayout()

        self.lang_combo = QComboBox()
        self.lang_combo.addItem(tr("Auto (system language)"), "auto")
        for _code, _name in available_languages():
            self.lang_combo.addItem(_name, _code)
        _lang = self.temp_settings.get("language", "auto")
        _lang_idx = self.lang_combo.findData(_lang)
        if _lang_idx >= 0:
            self.lang_combo.setCurrentIndex(_lang_idx)
        self.lang_combo.currentIndexChanged.connect(
            lambda _i: self.update_setting("language", self.lang_combo.currentData())
        )
        lang_layout.addRow(tr("Interface Language:"), self.lang_combo)
        lang_layout.addRow(
            QLabel(tr("<small>Changing the language restarts MusicLine.</small>"))
        )
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        # Lyrics source Group
        lyrics_group = QGroupBox(tr("Lyrics Source"))
        lyrics_layout = QFormLayout()

        self.combo_lyrics_source = QComboBox()
        for _code, _label in lyrics_sources.SOURCE_LABELS.items():
            self.combo_lyrics_source.addItem(tr(_label), _code)
        _lyrics_idx = self.combo_lyrics_source.findData(
            self.temp_settings.get("lyrics_source", "auto")
        )
        if _lyrics_idx >= 0:
            self.combo_lyrics_source.setCurrentIndex(_lyrics_idx)
        self.combo_lyrics_source.currentIndexChanged.connect(
            lambda _i: self.update_setting(
                "lyrics_source", self.combo_lyrics_source.currentData()
            )
        )
        lyrics_layout.addRow(tr("Lyrics Source:"), self.combo_lyrics_source)
        lyrics_layout.addRow(
            QLabel(
                tr("<small>Sources are tried in order; lyrics are cached locally so a player metadata flicker never drops them.</small>")
            )
        )

        self.btn_clear_lyrics_cache = QPushButton(tr("Clear Lyrics Cache"))
        self.btn_clear_lyrics_cache.clicked.connect(self.clear_lyrics_cache)
        lyrics_layout.addRow(self.btn_clear_lyrics_cache)

        lyrics_group.setLayout(lyrics_layout)
        layout.addWidget(lyrics_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def clear_lyrics_cache(self):
        count = lyrics_sources.clear_cache()
        self.btn_clear_lyrics_cache.setText(tr("Cache cleared ({count})", count=count))

    def update_preview(self):
        self.update_position_bounds()
        context_font = QFont(
            self.temp_settings["font_family"], self.temp_settings["font_size_normal"]
        )
        context_color = self.temp_settings["normal_color"]
        stroke_color = self.temp_settings.get("stroke_color", "#000000")
        anim_type = self.temp_settings.get("animation_type", "fade")

        num_history = self.temp_settings.get("num_history_lines", 0)
        num_future = self.temp_settings.get("num_future_lines", 1)

        # Update History Preview
        self.preview_prev.setFont(context_font)
        self.preview_prev.setStyleSheet(f"color: {context_color};")
        self.preview_prev.setStrokeColor(stroke_color)
        self.preview_prev.setStrokeEnabled(
            self.temp_settings.get("stroke_enabled_context", True)
        )
        self.preview_prev.animation_type = anim_type
        self.preview_prev.setVisible(num_history > 0)

        # Update Future Preview
        self.preview_next.setFont(context_font)
        self.preview_next.setStyleSheet(f"color: {context_color};")
        self.preview_next.setStrokeColor(stroke_color)
        self.preview_next.setStrokeEnabled(
            self.temp_settings.get("stroke_enabled_context", True)
        )
        self.preview_next.animation_type = anim_type
        self.preview_next.setVisible(num_future > 0)

        # Update Highlight Preview
        font = QFont(
            self.temp_settings["font_family"],
            self.temp_settings["font_size_highlight"],
            QFont.Weight.Bold,
        )
        self.preview_label.setFont(font)
        self.preview_label.setStyleSheet(
            f"color: {self.temp_settings['highlight_color']};"
        )
        self.preview_label.setStrokeColor(stroke_color)
        self.preview_label.setStrokeEnabled(
            self.temp_settings.get("stroke_enabled_highlight", True)
        )
        self.preview_label.animation_type = anim_type

        # Translation preview line
        translation_enabled = self.temp_settings.get("translation_enabled", False)
        self.preview_translation.setVisible(translation_enabled)
        if translation_enabled:
            self.preview_translation.setFont(
                QFont(
                    self.temp_settings["font_family"],
                    self.temp_settings.get("translation_font_size", 16),
                )
            )
            self.preview_translation.setStyleSheet(
                f"color: {self.temp_settings.get('translation_color', '#7fd7ff')};"
            )
            self.preview_translation.setStrokeColor(stroke_color)
            self.preview_translation.setStrokeEnabled(
                self.temp_settings.get("stroke_enabled_context", True)
            )

    def update_setting(self, key, value):
        self.temp_settings[key] = value
        self.update_preview()

    def update_hotkey(self, sequence):
        hotkey_str = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        self.temp_settings["toggle_hotkey"] = hotkey_str

    def update_font(self, font):
        self.temp_settings["font_family"] = font.family()
        self.update_preview()

    def pick_color(self, key, button):
        color = QColorDialog.getColor(
            QColor(self.temp_settings[key]), self, tr("Select Color")
        )
        if color.isValid():
            hex_color = color.name()
            self.temp_settings[key] = hex_color
            button.setStyleSheet(f"background-color: {hex_color}")
            self.update_preview()

    def reset_defaults(self):
        self.temp_settings = DEFAULT_SETTINGS.copy()

        # Appearance
        self.font_combo.setCurrentFont(QFont(self.temp_settings["font_family"]))
        self.spin_size_high.setValue(self.temp_settings["font_size_highlight"])
        self.spin_size_norm.setValue(self.temp_settings["font_size_normal"])
        self.btn_color_high.setStyleSheet(
            f"background-color: {self.temp_settings['highlight_color']}"
        )
        self.btn_color_stroke.setStyleSheet(
            f"background-color: {self.temp_settings['stroke_color']}"
        )
        self.btn_color_norm.setStyleSheet(
            f"background-color: {self.temp_settings['normal_color']}"
        )
        self.check_anim.setChecked(self.temp_settings.get("enable_animations", True))
        _anim = self.temp_settings.get("animation_type", "fade")
        _idx = self.combo_anim_type.findData(_anim)
        if _idx >= 0:
            self.combo_anim_type.setCurrentIndex(_idx)

        # Layout
        self.spin_history.setValue(self.temp_settings.get("num_history_lines", 1))
        self.spin_future.setValue(self.temp_settings.get("num_future_lines", 1))
        self.check_stroke_high.setChecked(
            self.temp_settings.get("stroke_enabled_highlight", True)
        )
        self.check_stroke_context.setChecked(
            self.temp_settings.get("stroke_enabled_context", True)
        )
        if 0 <= self.temp_settings.get("screen_index", 0) < self.screen_combo.count():
            self.screen_combo.setCurrentIndex(self.temp_settings.get("screen_index", 0))
        self.slider_offset_y.setValue(self.temp_settings["window_y_offset"])
        self.slider_offset_x.setValue(self.temp_settings.get("window_x_offset", 0))
        self.check_track_info.setChecked(
            self.temp_settings.get("track_info_enabled", False)
        )
        self.slider_track_x.setValue(self.temp_settings.get("track_info_x_offset", 0))
        self.slider_track_y.setValue(self.temp_settings.get("track_info_y_offset", 0))

        self.update_position_bounds()

        # System
        self.spin_sync.setValue(self.temp_settings.get("sync_offset_ms", 0) / 1000.0)
        _lang_idx = self.lang_combo.findData(
            self.temp_settings.get("language", "auto")
        )
        if _lang_idx >= 0:
            self.lang_combo.setCurrentIndex(_lang_idx)
        _lyrics_idx = self.combo_lyrics_source.findData(
            self.temp_settings.get("lyrics_source", "auto")
        )
        if _lyrics_idx >= 0:
            self.combo_lyrics_source.setCurrentIndex(_lyrics_idx)
        self.btn_clear_lyrics_cache.setText(tr("Clear Lyrics Cache"))
        hotkey = self.temp_settings.get("toggle_hotkey", "")
        self.hotkey_edit.setKeySequence(QKeySequence(hotkey))

        # Translation
        self.check_translation.setChecked(
            self.temp_settings.get("translation_enabled", False)
        )
        _src_idx = self.combo_translation_source.findData(
            self.temp_settings.get("translation_source", "auto")
        )
        if _src_idx >= 0:
            self.combo_translation_source.setCurrentIndex(_src_idx)
        _tgt_idx = self.combo_translation_target.findData(
            self.temp_settings.get("translation_target", "zh-Hans")
        )
        if _tgt_idx >= 0:
            self.combo_translation_target.setCurrentIndex(_tgt_idx)
        _eng_idx = self.combo_translation_engine.findData(
            self.temp_settings.get("translation_engine", "auto")
        )
        if _eng_idx >= 0:
            self.combo_translation_engine.setCurrentIndex(_eng_idx)
        self.spin_translation_size.setValue(
            self.temp_settings.get("translation_font_size", 16)
        )
        self.btn_color_translation.setStyleSheet(
            f"background-color: {self.temp_settings['translation_color']}"
        )
        self.edit_ai_base.setText(self.temp_settings["ai_base_url"])
        self.edit_ai_key.setText(self.temp_settings["ai_api_key"])
        self.edit_ai_model.setText(self.temp_settings["ai_model"])
        self.check_show_key.setChecked(False)
        self.label_test_result.setText("")

        self.update_preview()

    def get_selected_screen_geometry(self):
        screens = QApplication.screens()
        screen_index = self.temp_settings.get("screen_index", 0)
        if 0 <= screen_index < len(screens):
            return screens[screen_index].geometry()
        return QApplication.primaryScreen().geometry()

    def update_screen_selection(self, index):
        self.temp_settings["screen_index"] = index
        self.update_position_bounds()

    def update_position_bounds(self):
        if not hasattr(self, "slider_offset_y"):
            return

        screen_geom = self.get_selected_screen_geometry()
        overlay_geom = compute_overlay_geometry(self.temp_settings, screen_geom)
        min_y_offset = overlay_geom["min_y_offset"]
        max_y_offset = overlay_geom["max_y_offset"]
        max_x_offset = max(0, (screen_geom.width() - OVERLAY_WIDTH) // 2)

        y_value = clamp(
            self.temp_settings.get("window_y_offset", 0), min_y_offset, max_y_offset
        )
        x_value = clamp(
            self.temp_settings.get("window_x_offset", 0), -max_x_offset, max_x_offset
        )

        self.slider_offset_y.blockSignals(True)
        self.spin_offset_y.blockSignals(True)
        self.slider_offset_x.blockSignals(True)
        self.spin_offset_x.blockSignals(True)

        self.slider_offset_y.setRange(min_y_offset, max_y_offset)
        self.spin_offset_y.setRange(min_y_offset, max_y_offset)
        self.slider_offset_x.setRange(-max_x_offset, max_x_offset)
        self.spin_offset_x.setRange(-max_x_offset, max_x_offset)

        self.slider_offset_y.setValue(y_value)
        self.spin_offset_y.setValue(y_value)
        self.slider_offset_x.setValue(x_value)
        self.spin_offset_x.setValue(x_value)

        self.slider_offset_y.blockSignals(False)
        self.spin_offset_y.blockSignals(False)
        self.slider_offset_x.blockSignals(False)
        self.spin_offset_x.blockSignals(False)

        self.temp_settings["window_y_offset"] = y_value
        self.temp_settings["window_x_offset"] = x_value

        font_size = self.temp_settings.get("font_size_normal", 14)
        track_height = get_track_info_height(font_size)
        track_width = get_track_info_width(screen_geom.width())
        track_gap = get_track_info_gap(font_size)

        base_x = overlay_geom["x"] + (overlay_geom["width"] - track_width) // 2
        base_y = (
            overlay_geom["y"] + (overlay_geom["height"] // 2) - track_height - track_gap
        )

        min_track_x = screen_geom.x() - base_x
        max_track_x = screen_geom.x() + screen_geom.width() - track_width - base_x
        min_track_y = screen_geom.y() - base_y
        max_track_y = screen_geom.y() + screen_geom.height() - track_height - base_y

        track_x_value = clamp(
            self.temp_settings.get("track_info_x_offset", 0),
            min_track_x,
            max_track_x,
        )
        track_y_value = clamp(
            self.temp_settings.get("track_info_y_offset", 0),
            min_track_y,
            max_track_y,
        )

        self.slider_track_x.blockSignals(True)
        self.spin_track_x.blockSignals(True)
        self.slider_track_y.blockSignals(True)
        self.spin_track_y.blockSignals(True)

        self.slider_track_x.setRange(min_track_x, max_track_x)
        self.spin_track_x.setRange(min_track_x, max_track_x)
        self.slider_track_y.setRange(min_track_y, max_track_y)
        self.spin_track_y.setRange(min_track_y, max_track_y)

        self.slider_track_x.setValue(track_x_value)
        self.spin_track_x.setValue(track_x_value)
        self.slider_track_y.setValue(track_y_value)
        self.spin_track_y.setValue(track_y_value)

        self.slider_track_x.blockSignals(False)
        self.spin_track_x.blockSignals(False)
        self.slider_track_y.blockSignals(False)
        self.spin_track_y.blockSignals(False)

        self.temp_settings["track_info_x_offset"] = track_x_value
        self.temp_settings["track_info_y_offset"] = track_y_value

    def accept(self):
        old_language = self.manager.settings.get("language", "auto")
        new_language = self.temp_settings.get("language", "auto")
        self.manager.settings = self.temp_settings
        self.manager.save()
        self.settings_changed.emit(self.manager.settings)
        super().accept()
        if old_language != new_language:
            restart_application()
