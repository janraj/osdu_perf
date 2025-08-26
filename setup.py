# setup.py
from setuptools import setup, find_packages

setup(
    name="osdu-perf",
    version="1.0.0",
    author="Janraj CJ",
    author_email="janrajcj@microsoft.com",
    description="Performance Testing Framework for OSDU Services",
    long_description="A comprehensive Python library for performance testing OSDU services with automatic service discovery, Azure authentication, and Locust integration.",
    url="https://github.com/janraj/osdu-perf",
    packages=find_packages(),
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
        "Development Status :: 4 - Beta",
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
            "osdu-perf=osdu_perf.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "osdu_perf": ["templates/*.py", "config/*.yaml"],
    },
)