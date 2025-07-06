# yProv4SQA/setup.py
from setuptools import setup, find_packages

setup(
    name='yprov4sqa',
    version='0.2.0',
    package_dir={"": "src"},              
    packages=find_packages(where="src"),  
    install_requires=[
        'requests',
        'prov>=2.0.0',
        'lxml',
        'rdflib',
        'click>=8',
    ],
    entry_points={
        'console_scripts': [
            'fetch-sqa-reports  = yprov4sqa.cli.fetch_sqa_reports:main',
            'process-provenance = yprov4sqa.cli.process_provenance:main',
            'compare            = yprov4sqa.cli.compare:main',
            'json2graph         = yprov4sqa.cli.json2graph:main',
        ],
    },
    description="A library for processing provenance of software quality assurance pipelines",
    long_description=open('README.md').read(),
    url="https://github.com/HPCI-Lab/yProv4SQA",
)