from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

setup(
    name="api_engine_xin",
    version="0.0.25",
    author="Shawn",
    author_email="xiaoh0525@xiaoh.com",
    description="接口测试平台测试用例执行引擎",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://pypi.org/project/api_engine_xin/",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "pymysql>=1.0.0",
        "requests>=2.26.0",
        "jsonpath>=0.82",
    ],
    extras_require={
        "sqlserver": ["pymssql>=2.2.0"],
        "oracle": ["oracledb>=1.0.0"],
        "postgresql": ["psycopg2-binary>=2.9.0"],
        "all": ["pymssql>=2.2.0", "oracledb>=1.0.0", "psycopg2-binary>=2.9.0"],
    },
    keywords=["python", "apitest", "apiEngine"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
