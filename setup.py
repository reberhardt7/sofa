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

setup(name='jack',
      version='0.0',
      description='Python API framework',
      author='Ryan Eberhardt',
      author_email='ryan@reberhardt.com',
      packages=['jack', 'jack.scripts'],
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = jack:main
      [console_scripts]
      jack = jack.scripts.js:main
      """
     )
