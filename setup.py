"""Setup configuration for Champion Draft Assist Tool."""

from setuptools import setup, find_packages

setup(
    name="champion-draft-assist",
    version="0.1.0",
    description="League of Legends champion draft assistance tool",
    packages=find_packages(),
    install_requires=[
        "requests>=2.32.0",
        "click>=8.1.0",
        "pytest>=8.4.0",
        "hypothesis>=6.141.0",
    ],
    entry_points={
        "console_scripts": [
            "draft-assist=src.interface.cli:cli",
        ],
    },
    python_requires=">=3.9",
)