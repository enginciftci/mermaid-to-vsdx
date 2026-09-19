from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="mermaid-to-vsdx",
    version="1.0.0",
    description="Professional Mermaid diagram to Microsoft Visio (.vsdx) converter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Engin Ciftci",
    license="MIT",
    url="https://github.com/enginciftci/mermaid-to-vsdx",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "mermaid_to_vsdx.compiler": ["*.xml"],
    },
    include_package_data=True,
    install_requires=[
        "pillow>=10.0.0",
        "sv-ttk>=2.6.0",
        "pywin32>=306; sys_platform == 'win32'",
    ],
    entry_points={
        "console_scripts": [
            "mermaid-to-vsdx=mermaid_to_vsdx.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
