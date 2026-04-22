import torch
import torch.nn as nn
import numpy as np
import torch.distributions as dis
from .base_modules import *

torch.set_default_dtype(torch.float32)

INFINITY = 1e9


class VLOGMahjong(nn.Module):
    """Variational Latent Oracle Guiding (VLOG) model for Mahjong decision-making.

    This neural network implements the VLOG architecture from the paper
    "Variational Oracle Guiding for Reinforcement Learning" (ICLR 2022).
    It combines oracle information (opponents' hidden tiles) with executor
    observations to make action decisions.

    The model supports multiple algorithm types:
        - ``ddqn``: Double DQN for value-based reinforcement learning
        - ``bc``: Behavior cloning for supervised learning from demonstrations

    Args:
        algorithm: Training algorithm. Either ``"ddqn"`` or ``"bc"``.
            Defaults to ``"ddqn"``.
        hidden_layer_width: Width of hidden layers. Defaults to 1024.
        half_hidden_layer_depth: Number of hidden layer blocks (each block
            is Linear + activation). Defaults to 2.
        act_fn: Activation function, either ``"relu"`` or ``"tanh"``.
            Defaults to ``"relu"``.
        z_stochastic_size: Size of latent stochastic variable z. If None,
            uses half of hidden_layer_width for VLOG variants.
        type: Model type. One of ``"baseline"``, ``"oracle"``, ``"vlog"``,
            ``"vlog-self"``, ``"suphx"``, ``"opd"``, ``"vlog-oracle"``.
            Defaults to ``"vlog"``.
        epsilon: Exploration rate for epsilon-greedy (DDQN only).
            Defaults to 0.05.
        dueling: Whether to use dueling network architecture (DDQN only).
            Defaults to True.
        alg_config: Additional algorithm configuration dict.
        opd_mu: Distillation loss weight (OPD type only).
        opd_teacher_model: Teacher model for distillation (OPD type only).

    Example:
        >>> model = VLOGMahjong(algorithm="bc")
        >>> obs = np.random.randint(0, 2, (93, 34)).astype(np.float32)
        >>> action_mask = np.ones(47, dtype=np.float32)
        >>> action = model.select(obs, action_mask=action_mask, greedy=True)
    """

    def __init__(self, **kwargs):

        super(VLOGMahjong, self).__init__()

        self.action_size = 47
        self.algorithm = kwargs["algorithm"] if ("algorithm" in kwargs) else 'ddqn'

        self.hidden_layer_width = kwargs["hidden_layer_width"] if ("hidden_layer_width" in kwargs) else 1024
        self.half_hidden_layer_depth = kwargs["half_hidden_layer_depth"] if ("half_hidden_layer_depth" in kwargs) else 2
        self.act_fn = kwargs["act_fn"] if ("act_fn" in kwargs) else 'relu'
        self.z_stochastic_size = kwargs["z_stochastic_size"] if ("z_stochastic_size" in kwargs) else None

        self.type = kwargs["type"] if ("type" in kwargs) else "vlog"

        # ---------------------------------------- type settings ----------------------------------------
        # Available options:
        if self.type not in ["baseline", "oracle", "vlog", "vlog-self", "suphx", "opd", "vlog-oracle"]:
            raise ValueError(
                "Model type must be one of these: ['baseline', 'oracle', 'vlog', 'vlog-self', 'suphx', 'opd', 'vlog-oracle']")

        if self.type not in ["oracle", "suphx", "vlog-oracle"]:
            self.input_forward_size = [93, 34]
        else:
            self.input_forward_size = [111, 34]

        if self.type not in ["vlog-self"]:
            self.input_oracle_size = [111, 34]
        else:
            self.input_oracle_size = self.input_forward_size

        if self.type in ["baseline", "oracle", "suphx", "opd"]:
            self.use_prior_only = True
        else:
            self.use_prior_only = False

        self.device = 'cpu'

        if self.z_stochastic_size is None:
            if self.type in ["vlog", "vlog-self", "vlog-oracle"]:
                self.z_stochastic_size = int(self.hidden_layer_width / 2)
            else:
                self.z_stochastic_size = 0
        # ---------------------------------------- setting for OPD ----------------------------------------
        if self.type == "opd":
            self.opd_mu = kwargs["opd_mu"]  # weight of distillation loss
            self.opd_teacher_model = kwargs["opd_teacher_model"]

        # -------------------- Define Network Connections ------------------
        if self.act_fn == "relu":
            self.forward_act_fn = nn.ReLU
        elif self.act_fn == "tanh":
            self.forward_act_fn = nn.Tanh
        else:
            raise ValueError("activation function should be tanh or relu")

        self.latent_module = nn.ModuleList()

        if len(self.input_forward_size) == 1:
            self.encoder = nn.Sequential(nn.Linear(self.input_forward_size[0], self.hidden_layer_width),
                                         self.forward_act_fn()
                                         )
            self.encoder_oracle = nn.Sequential(nn.Linear(self.input_oracle_size[0], self.hidden_layer_width),
                                                self.forward_act_fn()
                                                )
            self.phi_size = self.hidden_layer_width
            self.phi_size_oracle = self.hidden_layer_width

        else:
            if len(self.input_forward_size) == 2:
                resolution = "{}".format(self.input_forward_size[1])
            elif len(self.input_forward_size) == 3:
                resolution = "{}x{}".format(self.input_forward_size[1], self.input_forward_size[2])
            else:
                raise NotImplementedError

            self.encoder, self.phi_size = make_cnn(resolution, self.input_forward_size[0])
            self.encoder_oracle, self.phi_size_oracle = make_cnn(resolution, self.input_oracle_size[0])

        self.latent_module.append(self.encoder_oracle)
        self.latent_module.append(self.encoder)

        forward_fnns = nn.ModuleList()
        last_layer_size = self.phi_size
        for _ in range(self.half_hidden_layer_depth - 1):
            forward_fnns.append(nn.Linear(last_layer_size, self.hidden_layer_width))
            forward_fnns.append(self.forward_act_fn())
            last_layer_size = self.hidden_layer_width
        self.forward_fnn = nn.Sequential(*forward_fnns)
        self.latent_module.append(self.forward_fnn)

        pre_zp_size = self.hidden_layer_width

        if self.z_stochastic_size:
            self.f_h2muzp = nn.Linear(pre_zp_size, self.z_stochastic_size)
            self.f_h2logsigzp = nn.Sequential(nn.Linear(pre_zp_size, self.z_stochastic_size),
                                              MinusOneModule()
                                              )
            self.latent_module.append(self.f_h2logsigzp)
            self.latent_module.append(self.f_h2muzp)

        else:
            self.f_h2zp = nn.Sequential(nn.Linear(pre_zp_size, self.hidden_layer_width),
                                        self.forward_act_fn())
            self.latent_module.append(self.f_h2zp)

        if not self.use_prior_only:
            oracle_fnns = nn.ModuleList()
            last_layer_size = self.phi_size_oracle
            for _ in range(self.half_hidden_layer_depth - 1):
                oracle_fnns.append(nn.Linear(last_layer_size, self.hidden_layer_width))
                oracle_fnns.append(self.forward_act_fn())
                last_layer_size = self.hidden_layer_width

            self.oracle_fnn = nn.Sequential(*oracle_fnns)
            self.latent_module.append(self.oracle_fnn)

            pre_zq_size = self.hidden_layer_width
            if self.z_stochastic_size:
                self.f_hb2muzq = nn.Linear(pre_zq_size, self.z_stochastic_size)
                self.f_hb2logsigzq = nn.Sequential(nn.Linear(pre_zq_size, self.z_stochastic_size),
                                                   MinusOneModule())
                self.latent_module.append(self.f_hb2logsigzq)
                self.latent_module.append(self.f_hb2muzq)
            else:
                self.f_hb2zq = nn.Sequential(nn.Linear(pre_zq_size, self.hidden_layer_width),
                                             self.forward_act_fn())
                self.latent_module.append(self.f_hb2zq)

        # ----------------------------- RL part -----------------------------
        self.alg_config = kwargs["alg_config"] if ("alg_config" in kwargs) else {}

        pre_rl_size = self.z_stochastic_size if self.z_stochastic_size else self.hidden_layer_width

        if self.algorithm == 'ddqn':
            self.epsilon = kwargs["epsilon"] if ("epsilon" in kwargs) else 0.05
            self.dueling = self.alg_config["dueling"] if ("dueling" in self.alg_config) else True
            self.alg_type = 'value_based'
            self.f_s2q = DiscreteActionQNetwork(pre_rl_size, self.action_size,
                                                 hidden_layers=[self.hidden_layer_width] * self.half_hidden_layer_depth,
                                                 dueling=self.dueling, act_fn=self.forward_act_fn)

        elif self.algorithm == 'bc':
            self.f_s2pi0 = DiscreteActionPolicyNetwork(pre_rl_size, self.action_size,
                                                       hidden_layers=[self.hidden_layer_width] * self.half_hidden_layer_depth,
                                                       act_fn=self.forward_act_fn, device=self.device)
            self.alg_type = 'supervised'

        else:
            raise NotImplementedError("algorithm can only be 'bc' or 'ddqn'")


    def select(self, x, action_mask=None, greedy=True):
        """Select an action given an observation.

        Args:
            x: Observation array of shape (93, 34) for executor-only input,
                or (111, 34) if using oracle input.
            action_mask: Optional boolean array of shape (47,) or (action_size,).
                Valid actions are True/1, invalid actions are False/0.
                If provided, invalid actions are masked out.
            greedy: If True, select the highest-value action. If False, use
                epsilon-greedy exploration (DDQN) or sample from policy (BC).

        Returns:
            int: Selected action index.
        """
        with torch.no_grad():

            if action_mask is not None:
                action_mask = torch.from_numpy(
                    action_mask.astype(np.float32).reshape([1, self.action_size]))

            x = torch.from_numpy(x.astype(np.float32).reshape([1, *list(x.shape)])).to(device=self.device)

            x = self.encoder(x)
            e = self.forward_fnn(x)
            muz = self.f_h2muzp(e)
            logsigz = self.f_h2logsigzp(e)
            dist = dis.normal.Normal(muz, torch.exp(logsigz))
            z = dist.sample()

            self.h_t = z
            self.zp_tm1 = z

            if self.algorithm == 'bc':

                a = self.f_s2pi0.sample_action(self.h_t, action_mask=action_mask, greedy=greedy).item()

            elif self.algorithm == 'ddqn':
                q = self.f_s2q(self.h_t).detach().cpu()
                if action_mask is not None:
                    q = q.clamp(-INFINITY, INFINITY) * action_mask - 2 * INFINITY * (1 - action_mask)

                if greedy:
                    a = torch.argmax(q, dim=-1)
                    if np.prod(a.shape) == 1:
                        a = a.item()  # discrete action
                else:
                    if np.random.rand() < self.epsilon:
                        if action_mask is None:
                            a = np.random.randint(self.action_size)
                        else:
                            valid_action_ind = np.nonzero(action_mask.cpu().numpy().reshape([-1]))
                            valid_actions = np.arange(self.action_size)[valid_action_ind]
                            a = int(valid_actions[np.random.randint(len(valid_actions))])
                    else:
                        a = torch.argmax(q, dim=-1)
                        if np.prod(a.shape) == 1:
                            a = int(a.item())  # discrete action

        return a
