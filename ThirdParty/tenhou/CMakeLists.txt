project(tenhou_shuffle)

add_library(${PROJECT_NAME} mt19937ar.h mt19937ar.cpp SHA512.h SHA512.cpp tenhou.cpp)