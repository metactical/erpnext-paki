from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in erpnext_paki/__init__.py
from erpnext_paki import __version__ as version

setup(
	name="erpnext_paki",
	version=version,
	description="Customizations for ERPNext Paki",
	author="Metactical",
	author_email="web6@dogtagbuilder.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
