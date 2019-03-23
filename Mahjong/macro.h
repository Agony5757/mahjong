#pragma once

#define OUTPUT_OPEN_MESSAGE(PLAYER) \
	gameLog << "p"<<##PLAYER<<"T|";	\
	gameLog << p##PLAYER##ÅÆºÓ;	\
	gameLog << "p"<<##PLAYER<<"F|";	\
	gameLog << p##PLAYER##¸±Â¶s		\
		    << endl;

#define OUTPUT_PLAY_CHOICES(choices)	\
	"OUTPUT_CHOICE_PLACEHOLDER_NOT_IMPLEMENTED_YET"