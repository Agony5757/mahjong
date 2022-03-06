from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext
import os
import subprocess

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
                      '-DCMAKE_CXX_COMPILER=clang++',
                      '-DCMAKE_BUILD_TYPE=Release']
        print(self.build_temp)
        subprocess.check_call(['cmake', ext.sourcedir, *cmake_args], cwd=self.build_temp)
        subprocess.check_call(['cmake', '--build', os.path.join(ext.sourcedir, self.build_temp), '--target', 'MahjongPyWrapper'], cwd=self.build_temp)

setup(
    name = "pymahjong",
    version = "0.1.2",
    author = "Agony",
    author_email = "chenzhaoyun@iai.ustc.edu.cn",
    description= "An essential Japanese riichi mahjong environment.",
    long_description = readme,
    long_description_content_type="text/markdown",
    ext_modules=[CMakeExtension('pymahjong', '.')],
    cmdclass=dict(build_ext=CMakeBuild),
    # package_data = {"pymahjong": ["MahjongPy.so", "MahjongPy.pyd", "MahjongPy.dylib"]},
    packages = ['pymahjong'],
    install_requires=['eventlet']
)
