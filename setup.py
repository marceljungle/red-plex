from setuptools import setup, find_packages

setup(
    name='red-plex',
    version='1.0.0',
    description='A tool for creating Plex playlists from RED collages',
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
        'python-dotenv',
        'click',
        'pyyaml',
    ],
    entry_points='''
        [console_scripts]
        red-plex=plex_playlist_creator.cli:cli
    ''',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)