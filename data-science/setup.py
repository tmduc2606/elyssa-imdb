from setuptools import setup, find_packages

setup(
    name="elyssa-imdb",
    version="3.0.0",
    description="Elyssa IMDb — Multi-modal ML pipeline for genre classification, rating regression, and recommendation",
    author="Elyssa Team",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests*", "notebooks*", "scripts*"]),
    install_requires=[
        "numpy>=1.26",
        "pandas>=2.2",
        "duckdb>=1.1",
        "joblib>=1.4",
        "scikit-learn>=1.5",
        "scipy>=1.13",
        "pyyaml>=6.0",
        "torch>=2.3",
        "catboost>=1.2",
        "mlflow>=2.16",
        "optuna>=4.0",
        "transformers>=4.44",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-cov>=5.0",
        ],
    },
)
