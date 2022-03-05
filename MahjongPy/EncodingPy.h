#ifndef ENCODINGPY_H
#define ENCODINGPY_H

#include "pybind11/numpy.h"
#include "Table.h"

void encode_table(const Table& table, int pid, pybind11::array_t<TrainingDataEncoding::dtype> arr);

#endif