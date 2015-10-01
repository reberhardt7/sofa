from setuptools import setup

requires = [
    'pyramid',
    'SQLAlchemy',
    'transaction',
    'validate_email',
    'pyDNS',
    'passlib',
    'pycrypto',
    'requests',
    'python-slugify',
    'uritemplate',
    'pyyaml',
    ]

setup(name='sofa',
      version='0.5',
      description='A lightweight REST API framework',
      author='Ryan Eberhardt',
      author_email='ryan@reberhardt.com',
      url='https://github.com/reberhardt/sofa',
      download_url='https://github.com/reberhardt/sofa/tarball/0.5',
      keywords=['rest', 'api'],
      packages=['sofa', 'sofa.scripts'],
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = sofa:main
      [console_scripts]
      sofa = sofa.scripts.js:main
      """
     )
