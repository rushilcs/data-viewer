from setuptools import setup, find_packages

setup(
    name="dataset_uploader",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["httpx>=0.26.0"],
    entry_points={
        "console_scripts": [
            "dataset-uploader=dataset_uploader.cli:main",
        ],
    },
)
