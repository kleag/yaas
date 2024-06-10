from setuptools import setup, find_packages

setup(
    name="Audio Splitter",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "pydub",
        "torch",
        "torchaudio",
        "openunmix",
        "pytube",
        "moviepy"
    ],
    entry_points={
        "console_scripts": [
            "yaas = yaas.yaas:main",
        ],
    },
    author="Gaël de Chalendar",
    author_email="kleagg@gmail.com",
    description="A tool to split video soundtracks into separate tracks using OpenUnmix",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/kleag/yaas",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MPL License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
