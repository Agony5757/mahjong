cmake_minimum_required(VERSION 3.1)
project(mahjong)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/Mahjong
                    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty
                    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty/pybind11
                    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty/fmt/include
                    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty/tenhou
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    )

set(LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/lib)
set(EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_CURRENT_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_CURRENT_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_CURRENT_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_CURRENT_BINARY_DIR}/lib)

set(CMAKE_CXX_STANDARD 14)

if (UNIX)
    add_definitions("-fPIC")
endif()

find_package(PythonInterp 3 REQUIRED)
find_package(PythonLibs 3 REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})

add_subdirectory(ThirdParty EXCLUDE_FROM_ALL)
add_subdirectory(Mahjong)
add_subdirectory(MahjongPyWrapper)
add_subdirectory(test)
