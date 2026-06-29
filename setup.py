# yProv4SQA/setup.py
from setuptools import setup, find_packages
from pathlib import Path

# Read README if it exists, otherwise use a short description
readme = Path('README.md')
long_description = readme.read_text(encoding='utf-8') if readme.exists() else (
    "A library for processing provenance of software quality assurance pipelines"
)

setup(
    name    = 'yprov4sqa',
    version = '0.3.0',
    package_dir = {"": "src"},
    packages    = find_packages(where="src"),
    install_requires = [
        # existing
        'requests',
        'prov>=2.0.0',
        'lxml',
        'rdflib',
        'click>=8',
        # chat agent (LangChain 1.x API)
        'langchain>=1.0.0',
        'langchain-ollama>=1.0.0',
        'langchain-community>=0.3.0',
        'flask>=3.0.0',
        'rich>=13.0.0',
        'python-dotenv>=1.0.0',
    ],
    extras_require = {
        'google': ['langchain-google-genai>=2.0.0'],
    },
    entry_points = {
        'console_scripts': [
            # existing commands
            'fetch-sqa-reports  = yprov4sqa.cli.fetch_sqa_reports:main',
            'fetch-all-reports  = yprov4sqa.cli.fetch_all_reports:main',
            'normalize-reports  = yprov4sqa.cli.normalize_reports:main',
            'process-provenance = yprov4sqa.cli.process_provenance:main',
            'compare            = yprov4sqa.cli.compare:main',
            'json2graph         = yprov4sqa.cli.json2graph:main',
            # conversational agent command
            'prov-chat          = yprov4sqa.cli.prov_chat:main',
        ],
    },
    description      = "Provenance library for software quality assurance pipelines",
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = "https://github.com/HPCI-Lab/yProv4SQA",
)
