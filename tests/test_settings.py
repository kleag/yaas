import os

from yaas import settings


def test_output_dir_defaults_to_home_folder(qapp):
    assert settings.get_output_dir() == os.path.join(os.environ["HOME"], "yaas_tracks")


def test_output_dir_round_trip(qapp, tmp_path):
    settings.set_output_dir(str(tmp_path))
    try:
        assert settings.get_output_dir() == str(tmp_path)
    finally:
        settings._settings().remove(settings._KEY_OUTPUT_DIR)


def test_model_round_trip_and_default(qapp):
    assert settings.get_model() == "roformer"
    settings.set_model("openunmix")
    assert settings.get_model() == "openunmix"
    # A value from a newer or older version falls back to the default.
    settings.set_model("no-such-model")
    assert settings.get_model() == "roformer"
    settings._settings().remove(settings._KEY_MODEL)


def test_models_use_known_backends():
    for label, backend, model in settings.MODELS.values():
        assert backend in ("audio_separator", "openunmix")
        assert (model is None) == (backend == "openunmix")


def test_sample_rate_round_trip_and_default(qapp):
    assert settings.get_sample_rate() == 48000
    settings.set_sample_rate(44100)
    assert settings.get_sample_rate() == 44100
    settings._settings().setValue(settings._KEY_SAMPLE_RATE, "garbage")
    assert settings.get_sample_rate() == 48000
    settings._settings().remove(settings._KEY_SAMPLE_RATE)
