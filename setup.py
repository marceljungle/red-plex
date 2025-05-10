"""Setup script for installing the package."""

import re
import pathlib
from setuptools import setup, find_namespace_packages

# Resolve the absolute path to the directory containing setup.py
here = pathlib.Path(__file__).parent.resolve()

# Read the long description from README.md
long_description = (here / "README.md").read_text(encoding="utf-8")

# Construct the absolute path to __init__.py within your package
init_py_path = here / "red_plex" / "__init__.py"

# Read the version from the package's __init__.py
with open(init_py_path, 'r', encoding="utf-8") as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        # It's good to show the path it tried to open for easier debugging
        raise RuntimeError(f"Unable to find version string in {init_py_path}")

setup(
    name='red_plex',
    version=version,
    description='A tool for creating Plex playlists or collections from RED collages',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='marceljungle',
    author_email='gigi.dan2011@gmail.com',
    url='https://github.com/marceljungle/red-plex',
    packages=find_namespace_packages(include=['red_plex*']),
    include_package_data=True,
    install_requires=[
        'plexapi',
        'requests',
        'tenacity',
        'pyrate-limiter',
        'click',
        'pyyaml',
    ],
    entry_points='''
        [console_scripts]
        red-plex=red_plex.infrastructure.cli.cli:main
    ''',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
