#ifndef ENCODINGPY_H
#define ENCODINGPY_H

#include "Encoding/TrainingDataEncoding.h"
#include "pybind11/numpy.h"
#include "Table.h"

void encode_table(const mahjong::Table& table, int pid, bool use_oracle, pybind11::array_t<mahjong::TrainingDataEncoding::dtype> arr);

void encode_table_riichi_step2(const mahjong::Table& table, int riichi_tile, pybind11::array_t<mahjong::TrainingDataEncoding::dtype> arr);

void encode_action(const mahjong::Table& table, int pid, pybind11::array_t<mahjong::TrainingDataEncoding::dtype> arr);

void encode_action_riichi_step2(pybind11::array_t<mahjong::TrainingDataEncoding::dtype> arr);



#endif