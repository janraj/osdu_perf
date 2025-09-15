# setup.py
from setuptools import setup, find_packages
import os

# Read README.md safely
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
long_description = "A comprehensive Python library for performance testing OSDU services with automatic service discovery, Azure authentication, and Locust integration."

try:
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
except (FileNotFoundError, UnicodeDecodeError):
    pass  # Use default description if README can't be read

setup(
    name="osdu_perf",
    version="1.0.8",
    author="Janraj CJ",
    author_email="janrajcj@microsoft.com",
    description="Performance Testing Framework for OSDU Services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/janraj/osdu_perf",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "locust>=2.0.0",
        "azure-identity>=1.12.0",
        "azure-core>=1.26.0",
        "requests>=2.28.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Testing :: Traffic Generation",
    ],
    entry_points={
        "console_scripts": [
            "osdu_perf=osdu_perf.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "osdu_perf": ["templates/*.py"],
    },
    license="MIT",
    zip_safe=False,
)