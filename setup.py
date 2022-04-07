from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext
import os
import subprocess
import sys

with open("README.md") as fp:
    readme = fp.read()

class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=''):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)

class CMakeBuild(build_ext):
    def run(self):
        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        extdir = self.get_ext_fullpath(ext.name)
        if not os.path.exists(extdir):
            os.makedirs(extdir)

        install_prefix = os.path.abspath(os.path.dirname(extdir))
        print(install_prefix)
        cmake_args = ['-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={}'.format(install_prefix),
                      '-DCMAKE_C_COMPILER=clang',
                      '-DCMAKE_CXX_COMPILER=clang++',
                      '-DCMAKE_BUILD_TYPE=Release']
        if sys.platform == 'win32':
            cmake_args += ['-G MinGW Makefiles']

        print(self.build_temp)
        subprocess.check_call(['cmake', ext.sourcedir, *cmake_args], cwd=self.build_temp)
        subprocess.check_call(['cmake', '--build', os.path.join(ext.sourcedir, self.build_temp), '--target', 'MahjongPyWrapper'], cwd=self.build_temp)

CLASSIFIERS = """\
Development Status :: 5 - Production/Stable
Intended Audience :: Science/Research
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: C++
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: 3.8
Programming Language :: Python :: 3.9
Programming Language :: Python :: 3.10
Programming Language :: Python :: 3 :: Only
Topic :: Scientific/Engineering :: Artificial Intelligence
Operating System :: Microsoft :: Windows
Operating System :: POSIX
Operating System :: Unix
"""

setup(
    name = "pymahjong",
    version = "1.0.2",
    author = "Agony",
    author_email = "chenzhaoyun@iai.ustc.edu.cn",
    description= "A Japanese Mahjong environment for decision AI research.",
    long_description = readme,
    long_description_content_type="text/markdown",
    ext_modules=[CMakeExtension('pymahjong', '.')],
    cmdclass=dict(build_ext=CMakeBuild),
    project_urls={
        "Source Code": "https://github.com/Agony5757/mahjong",
    },
    classifiers=[_f for _f in CLASSIFIERS.split('\n') if _f],
    packages = ['pymahjong'],
    install_requires=['numpy', 'gym'],
    python_requires='>=3.6',
)
