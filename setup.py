"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from os import path
# Always prefer setuptools over distutils
from setuptools import setup, find_packages

# Imports the version number from the version module
from message_adapter.version import __version__

here = path.abspath(path.dirname(__file__))

# get the dependencies and installs
with open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')
install_requires = [x.strip() for x in all_reqs if 'git+' not in x]
dependency_links = [x.strip().replace('git+', '') for x in all_reqs if 'git+' in x]
print(install_requires)
print(dependency_links)

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='cumulus-message-adapter',  # Required

    # Versions should comply with PEP 440:
    # https://www.python.org/dev/peps/pep-0440/
    version=__version__,  # Required

    # This is a one-line description or tagline of what your project does. This
    # corresponds to the "Summary" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#summary
    description=('A command-line interface for preparing and outputting '
                 'Cumulus Messages for Cumulus Tasks'),  # Required
    long_description=long_description,  # Optional
    url='https://github.com/nasa/cumulus-message-adapter',  # Optional
    author='Cumulus Authors',  # Optional
    author_email='info@developmentseed.org',  # Optional
    classifiers=[  # Optional
        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.10',
    ],
    keywords='nasa cumulus message adapter',  # Optional
    packages=find_packages(exclude=['.circleci', 'contrib', 'docs', 'tests']),  # Required
    install_requires=install_requires,
    python_requires='~=3.10',
    dependency_links=dependency_links
)
