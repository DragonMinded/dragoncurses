from setuptools import setup  # pyre-ignore


def format_req(req: str) -> str:
    if ";" not in req:
        return req

    req, extra = req.split(";", 1)
    req = req.strip()
    extra = extra.strip()

    if "sys.platform" in extra and "==" in extra:
        platform = None
        if "win32" in extra:
            platform = "Windows"

        if platform is not None:
            return f"{req}; platform_system=='{platform}'"

    raise Exception(f"Don't know how to format {req}!")


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
        format_req(req) for req in open('requirements.txt').read().split('\n') if len(req) > 0
    ],
    include_package_data=True,
    zip_safe=False,
)
