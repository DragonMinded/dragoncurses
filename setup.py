import os
from setuptools import setup  # pyre-ignore


with open(os.path.join("dragoncurses", "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="dragoncurses",
    version="0.2.0",
    description="Console-based UI toolkit building on top of curses.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="DragonMinded",
    author_email="dragonminded@dragonminded.com",
    license="Public Domain",
    url="https://github.com/DragonMinded/dragoncurses",
    package_data={"dragoncurses": ["py.typed", "README.md"]},
    packages=[
        # Core packages
        "dragoncurses",
    ],
    install_requires=[
        "windows-curses; platform_system=='Windows'",
    ],
    python_requires=">=3.6",
)
