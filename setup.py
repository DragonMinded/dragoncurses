from setuptools import setup  # pyre-ignore

setup(
    name='dragoncurses',
    version='0.1',
    description='Console-based UI toolkit building on top of curses.',
    author='DragonMinded',
    license='Public Domain',
    package_data={"dragoncurses": ["py.typed"]},
    packages=[
        # Core packages
        'dragoncurses',
    ],
    install_requires=[
        req for req in open('requirements.txt').read().split('\n') if len(req) > 0
    ],
    include_package_data=True,
    zip_safe=False,
)
