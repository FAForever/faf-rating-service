from distutils.core import setup

from setuptools import find_packages

import service

setup(
    name="Forged Alliance Forever Server",
    version="dev",
    packages=["service"] + find_packages(),
    url="http://www.faforever.com",
    license=service.__license__,
    author=service.__author__,
    author_email=service.__contact__,
    description="Trueskill rating service",
    include_package_data=True,
)
