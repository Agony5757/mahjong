#include <type_traits>
#include <typeinfo>
#include "EncodingPy.h"

using namespace std;
namespace enc = TrainingDataEncoding;

void encode_table(const Table& table, int pid, pybind11::array_t<enc::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_table(table, pid, data);
}

void encode_action(const Table& table, int pid, pybind11::array_t<enc::dtype> arr)
{
	enc::dtype* data = arr.mutable_data();
	enc::encode_actions_vector(table, pid, data);
}