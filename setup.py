# yProv4SQA/setup.py
from setuptools import setup, find_packages

setup(
    name='yProv4SQA',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'requests', 
    ],
    entry_points={
        'console_scripts': [
            'fetch-sqa-reports=yProv4SQA.models.get_SQAaaS_AReports:main',
            'process-provenance=yProv4SQA.models.processor:main',
            'compare=yProv4SQA.models.commit_provenance:main', 
        ],
    },
    description="A library for processing provenance data and generating models.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/yProv4SQA",  # Replace with actual URL
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
