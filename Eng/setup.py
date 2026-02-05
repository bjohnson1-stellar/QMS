"""
Setup script for refrig_calc package.

Installation:
    pip install -e .
    
Or:
    python setup.py install
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="refrig_calc",
    version="1.0.0",
    author="Refrigeration Engineering Tools",
    author_email="engineering@example.com",
    description="A comprehensive Python library for industrial refrigeration calculations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/refrig-calc",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    python_requires=">=3.8",
    install_requires=[
        # No external dependencies - pure Python
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "mypy>=1.0",
        ],
    },
    keywords=[
        "refrigeration",
        "ammonia",
        "HVAC",
        "engineering",
        "thermodynamics",
        "pipe sizing",
        "charge calculation",
        "ventilation",
        "IIAR",
        "ASHRAE",
    ],
    project_urls={
        "Bug Reports": "https://github.com/example/refrig-calc/issues",
        "Source": "https://github.com/example/refrig-calc",
        "Documentation": "https://github.com/example/refrig-calc#readme",
    },
)
