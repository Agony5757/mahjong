cmake_minimum_required(VERSION 3.1)
project(MahjongPyWrapper)

set(LIB_MahjongPy ${PROJECT_NAME})
file(GLOB_RECURSE MahjongPy_SRC_CPP *.cpp)

pybind11_add_module(${PROJECT_NAME} ${MahjongPy_SRC_CPP})

target_link_libraries(${PROJECT_NAME} PRIVATE MahjongCore ${PYTHON_LIBRARIES} fmt tenhou_shuffle)

target_compile_definitions(${PROJECT_NAME} PRIVATE VERSION_INFO=${EXAMPLE_VERSION_INFO})