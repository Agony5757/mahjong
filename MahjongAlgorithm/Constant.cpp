#include "Constant.h"

namespace mahjong
{
	Wind& operator++(Wind& orgWind)
	{
		orgWind = static_cast<Wind>((static_cast<int>(orgWind) + 1) % 4);
		return orgWind;
	}

	Wind operator++(Wind& orgWind, int i)
	{
		Wind wind = orgWind;
		++orgWind;
		return wind;
	}

	Wind operator+(const Wind& orgWind, const int i)
	{
		Wind ret = static_cast<Wind>((static_cast<int>(orgWind) + i) % 4);
		return ret;
	}

	Wind operator-(const Wind& orgWind, const int i)
	{
		Wind ret = static_cast<Wind>((static_cast<int>(orgWind) - (i % 4) + 4) % 4);
		return ret;
	}

	ClaimType operator&(const ClaimType& type1, const ClaimType& type2)
	{
		return static_cast<ClaimType>(static_cast<int>(type1) & static_cast<int>(type2));
	}

	ClaimType operator|(const ClaimType& type1, const ClaimType& type2)
	{
		return static_cast<ClaimType>(static_cast<int>(type1) | static_cast<int>(type2));
	}

	ClaimType& operator|=(ClaimType& type1, const ClaimType& type2)
	{
		ClaimType newType = static_cast<ClaimType>(static_cast<int>(type1) | static_cast<int>(type2));
		type1 = newType;
		return type1;
	}
}