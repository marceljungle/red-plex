"""Setup script for installing the package."""

import re
import pathlib
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

# Read the version from the package's __init__.py
with open('src/__init__.py', 'r', encoding="utf-8") as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string.")

setup(
    name='red-plex',
    version=version,
    description='A tool for creating Plex playlists or collections from RED collages',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='marceljungle',
    author_email='gigi.dan2011@gmail.com',
    url='https://github.com/marceljungle/red-plex',
    packages=find_packages(),
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
        red-plex=src.infrastructure.cli.cli:cli
    ''',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
