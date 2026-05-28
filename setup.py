from setuptools import setup, find_packages

setup(
    name="shared-memory",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "aiosqlite>=0.20.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "chromadb": ["chromadb>=0.5.0"],
        "openai": ["openai>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "sm=shared_memory.cli.main:main",
        ],
    },
    python_requires=">=3.13",
    description="Industrial-grade, local-first shared memory for multi-AI tools",
)
