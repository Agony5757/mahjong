cmake_minimum_required(VERSION 3.15...3.26)
project(mahjong LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Position-independent code for static libraries
if(NOT WIN32)
    set(CMAKE_POSITION_INDEPENDENT_CODE ON)
endif()

# Output directories
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Find Python using modern CMake methods
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# Include directories for project source
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/Mahjong
    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty
    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty/fmt/include
    ${CMAKE_CURRENT_SOURCE_DIR}/ThirdParty/tenhou
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# Copy resource file
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/resource/syanten.dat
    ${CMAKE_CURRENT_BINARY_DIR}/resource/syanten.dat
    COPYONLY
)

# Add subdirectories
add_subdirectory(ThirdParty)
add_subdirectory(Mahjong)
add_subdirectory(Pybinder)
add_subdirectory(test)
