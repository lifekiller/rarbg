from setuptools import setup

setup(
    name='rarbg',
    version='0.1-dev',
    description='RSS interface to TorrentAPI',
    url='https://github.com/banteg/rarbg',
    py_modules=['rarbg'],
    install_requires=[
        'aiohttp',
        'python-dateutil',
        'humanize',
        'jinja2'
    ],
    entry_points={
        'console_scripts': [
            'rarbg = rarbg:main',
        ],
    }
)
