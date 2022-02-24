project(tenhou_shuffle)

add_library(${PROJECT_NAME} STATIC mt19937ar.h SHA512.h tenhou.h mt19937ar.cpp SHA512.cpp tenhou.cpp)