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
