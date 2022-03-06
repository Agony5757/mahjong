#include <type_traits>
#include <typeinfo>
#include "EncodingPy.h"

using namespace std;
namespace enc = TrainingDataEncoding;

void encode_table(const Table& table, int pid, bool use_oracle, pybind11::array_t<enc::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_table(table, pid, use_oracle, data);
}

void encode_table_riichi_step2(const Table& table, int riichi_tile, pybind11::array_t<TrainingDataEncoding::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_table_riichi_step2(table, (BaseTile)riichi_tile, data);
}

void encode_action(const Table& table, int pid, pybind11::array_t<enc::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_actions_vector(table, pid, data);
}

void encode_action_riichi_step2(pybind11::array_t<TrainingDataEncoding::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_actions_vector_riichi_step2(data);
}
