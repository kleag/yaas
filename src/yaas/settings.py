"""Persistent app configuration, stored as a plain INI file via QSettings.

A thin key-value wrapper so future settings just add another get/set pair
here, rather than each caller touching QSettings directly.
"""
import os

from PySide6.QtCore import QDir, QSettings, QStandardPaths

_CONFIG_FILENAME = "yaas.conf"

_KEY_OUTPUT_DIR = "output_dir"


def _default_output_dir():
    return os.path.join(QDir.homePath(), "yaas_tracks")


def _settings():
    config_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    QDir().mkpath(config_dir)
    config_path = os.path.join(config_dir, _CONFIG_FILENAME)
    return QSettings(config_path, QSettings.IniFormat)


def get_output_dir():
    return _settings().value(_KEY_OUTPUT_DIR, _default_output_dir())


def set_output_dir(path):
    settings = _settings()
    settings.setValue(_KEY_OUTPUT_DIR, path)
    settings.sync()


# Separation models offered in the Settings dialog, as
# key -> (label, backend, audio_separator model or None). The key is what's
# stored.
MODELS = {
    "roformer": ("BS-Roformer", "audio_separator", "roformer"),
    "htdemucs6s": ("HTDemucs 6 stems", "audio_separator", "htdemucs6s"),
    "openunmix": ("OpenUnmix", "openunmix", None),
}
_KEY_MODEL = "model"
_DEFAULT_MODEL = "roformer"


def get_model():
    model = _settings().value(_KEY_MODEL, _DEFAULT_MODEL)
    return model if model in MODELS else _DEFAULT_MODEL


def set_model(model):
    settings = _settings()
    settings.setValue(_KEY_MODEL, model)
    settings.sync()


# Sample rates the stems can be written at, as Hz -> label. The models
# work at 44.1 kHz; 48 kHz stems are resampled afterwards.
SAMPLE_RATES = {
    44100: "44.1 kHz",
    48000: "48 kHz",
}
_KEY_SAMPLE_RATE = "sample_rate"
_DEFAULT_SAMPLE_RATE = 48000


def get_sample_rate():
    try:
        rate = int(_settings().value(_KEY_SAMPLE_RATE, _DEFAULT_SAMPLE_RATE))
    except (TypeError, ValueError):
        return _DEFAULT_SAMPLE_RATE
    return rate if rate in SAMPLE_RATES else _DEFAULT_SAMPLE_RATE


def set_sample_rate(rate):
    settings = _settings()
    settings.setValue(_KEY_SAMPLE_RATE, int(rate))
    settings.sync()
