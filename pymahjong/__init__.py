import MahjongPyWrapper
print(dir(MahjongPyWrapper))
del MahjongPyWrapper

from .env_pymahjong import MahjongEnv, SingleAgentMahjongEnv
from .test import test, test_with_pretrained
from .tenhou_paipu_check import paipu_replay, paipu_replay_1
from MahjongPyWrapper import *


