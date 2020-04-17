from setuptools import setup, find_namespace_packages

setup(
    name='cocotbext-interfaces',
    version='0.1',
    author='Nicholas Redd',
    author_email="redd@google.com",
    packages = find_namespace_packages(include=['cocotbext.*']),
    install_requires = ['cocotb', 'transitions'],
    python_requires = '>=3.6',
    classifiers = [
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)"
    ]
)
