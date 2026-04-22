import time
import numpy as np
from .env_pymahjong import MahjongEnv, SingleAgentMahjongEnv


def test(num_games=100):
    """Run random-play games to verify the environment works correctly.

    Creates a multi-agent Mahjong environment and runs the specified number
    of games with random action selection. Any errors during gameplay are
    caught and reported with debug replay information.

    Args:
        num_games: Number of games to run. Defaults to 100.

    Example:
        >>> import pymahjong
        >>> pymahjong.test(10)
        Game 0, payoffs: [-15.  35.   5. -25.]
        ...
        Total 10 random-play games, 10 games without error, takes 2.5 s
    """

    env = MahjongEnv()

    start_time = time.time()
    game = 0
    success_games = 0

    while game < num_games:

        try:

            env.reset(oya=game % 4, game_wind="east", debug_mode=1)

            while not env.is_over():

                curr_player_id = env.get_curr_player_id()

                # --------- get decision information -------------

                valid_actions_mask = env.get_valid_actions(nhot=True)
                executor_obs = env.get_obs(curr_player_id)

                # oracle_obs = env.get_oracle_obs(curr_player_id)
                # full_obs = env.get_full_obs(curr_player_id)
                # full_obs = np.concatenate([executor_obs, oracle_obs], axis=0)

                # --------- make decision -------------

                a = np.random.choice(np.argwhere(
                    valid_actions_mask).reshape([-1]))

                env.step(curr_player_id, a)

            # ----------------------- get result ---------------------------------

            payoffs = np.array(env.get_payoffs())
            print("Game {}, payoffs: {}".format(game, payoffs))
            # env.render()

            success_games += 1
            game += 1

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print(
                "-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            print("-------------- replayable log -------------------------------")
            env.t.print_debug_replay()
            continue

    print("Total {} random-play games, {} games without error, takes {} s".format(
        num_games, success_games, time.time() - start_time))


def test_with_pretrained(opponent_agent, num_games=100):
    """Test the single-agent environment with pretrained opponent models.

    Creates a single-agent environment where the agent (player 0) plays
    against pretrained VLOG models. The agent selects actions randomly,
    demonstrating the environment's basic functionality with intelligent
    opponents.

    Args:
        opponent_agent: Path to a pretrained model file (.pth). Available
            models are ``mahjong_VLOG_CQL.pth`` (CQL) and
            ``mahjong_VLOG_BC.pth`` (BC). Download from `GitHub releases
            <https://github.com/Agony5757/mahjong/releases/tag/v1.0.2>`_.
        num_games: Number of games to run. Defaults to 100.

    Example:
        >>> import pymahjong
        >>> pymahjong.test_with_pretrained("mahjong_VLOG_BC.pth", 10)
        Game 0, agent payoff -15.0
        ...
        Total 10 random-play games with pretrained VLOG models as opponents,
        10 games without error, takes 30.2 s
    """

    env = SingleAgentMahjongEnv(opponent_agent)

    start_time = time.time()
    success_games = 0

    for game in range(num_games):

        try:
            env.reset()
            payoff = 0

            while True:

                valid_actions = env.get_valid_actions()

                a = np.random.choice(valid_actions)

                obs, reward, done, _ = env.step(a)

                payoff = payoff + reward  # reward may != 0 only when done

                if done:
                    success_games += 1
                    print("Game {}, agent payoff {}".format(game, payoff))
                    break

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print(
                "-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            continue

    print("Total {} random-play games with pretrained VLOG models as opponents, {} games without error, takes {} s".format(
        num_games, success_games, time.time() - start_time))
