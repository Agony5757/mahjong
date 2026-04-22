cmake_minimum_required(VERSION 3.15)
project(MahjongPyWrapper)

# Find pybind11 (installed via pip as build requirement)
find_package(pybind11 CONFIG REQUIRED)

set(LIB_MahjongPy ${PROJECT_NAME})
file(GLOB_RECURSE MahjongPy_SRC_CPP *.cpp)

pybind11_add_module(${PROJECT_NAME} ${MahjongPy_SRC_CPP})

target_link_libraries(${PROJECT_NAME} PRIVATE MahjongCore fmt tenhou_shuffle)

# Version info from scikit-build-core or legacy setup.py
if(DEFINED SKBUILD_PROJECT_VERSION)
    target_compile_definitions(${PROJECT_NAME} PRIVATE VERSION_INFO="${SKBUILD_PROJECT_VERSION}")
elseif(DEFINED EXAMPLE_VERSION_INFO)
    target_compile_definitions(${PROJECT_NAME} PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})
endif()

# Install the Python module to the correct location for scikit-build-core
install(TARGETS ${PROJECT_NAME} LIBRARY DESTINATION .)