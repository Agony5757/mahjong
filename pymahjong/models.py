import torch
import torch.nn as nn
import numpy as np
import torch.distributions as dis
from .base_modules import *

torch.set_default_dtype(torch.float32)

INFINITY = 1e9


class VLOGMahjong(nn.Module):

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
