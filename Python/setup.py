"""Setup script for CompyMac Python package."""

from setuptools import setup, find_packages

setup(
    name="compymac",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'aiohttp>=3.8.0',
        'websockets>=10.0',
        'pytest>=7.0.0',
        'pytest-asyncio>=0.20.0',
        'pytest-cov>=4.0.0',
        'playwright>=1.40.0',
        'pyobjc-core>=10.0',
        'pyobjc-framework-Cocoa>=10.0',
        'pyobjc-framework-Quartz>=10.0'
    ]
)
