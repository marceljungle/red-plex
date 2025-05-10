"""Setup script for installing the package."""

import pathlib
from setuptools import setup, find_namespace_packages

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name='red_plex',
    version='0.0.0',
    description='A tool for creating Plex playlists or collections from RED collages',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='marceljungle',
    author_email='gigi.dan2011@gmail.com',
    url='https://github.com/marceljungle/red-plex',
    packages=find_namespace_packages(where="red_plex"),
    package_dir={"": "red_plex"},
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
        red-plex=infrastructure.cli.cli:main
    ''',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
