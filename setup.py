from setuptools import setup, find_packages
import codecs
import os

# 获取当前项目根目录
here = os.path.abspath(os.path.dirname(__file__))

# 读取README.md作为项目长描述（可选）
with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

# 核心配置
setup(
    name="api_engine_xin",  # ✅【必须改】pip install 这个名字！全网唯一，不能和PyPI上已有的包名重复
    version="0.0.16", # ✅【必须改】版本号，每次更新包都要升级版本（如0.0.2、0.1.0）
    author="Shawn",# ✅【必须改】你的名字/昵称
    author_email="xiaoh0525@xiaoh.com",# ✅【必须改】你的注册PyPI的邮箱
    description="接口测试平台测试用例执行引擎", # ✅【必须改】一句话说明你的包是干嘛的
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://pypi.org/project/api_engine_xin/", # 可选，比如你的github/gitee地址，没有就写你的PyPI包地址
    packages=find_packages(), # 自动识别你的包目录下的所有py文件，不用手动写
    python_requires=">=3.6", # 支持的Python版本，建议写3.6+，兼容大部分环境
    install_requires=["pymysql>=1.0.0", "requests>=2.26.0"], # ✅【按需改】你的包依赖的第三方库，例如["redis>=4.0.0", "pymysql>=1.0.0"]，无依赖则留空列表
    keywords=["python", "apitest", "apiEngine"], # 可选，方便别人搜索你的包
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