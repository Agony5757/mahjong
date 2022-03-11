import warnings

import gym
import torch
import torch.nn as nn
import numpy as np
import time

import torch.nn.functional as F
import torch.distributions as dis
from gym.spaces import Box, Discrete
from base_modules import *

torch.set_default_dtype(torch.float32)

INFINITY = 1e9


def augment_mahjong_data(x, a, mask):
    assert x.shape[-1] == 34

    agumented_ind = np.zeros([34], dtype=np.int64)

    mps_permu = np.random.permutation(3)

    if np.random.rand() < 0.5:
        through = np.flip(np.arange(9))
    else:
        through = np.arange(9)

    agumented_ind[0:9] = mps_permu[0] * 9 + through
    agumented_ind[9:18] = mps_permu[1] * 9 + through
    agumented_ind[18:27] = mps_permu[2] * 9 + through

    agumented_ind[27:31] = np.random.permutation(4) + 27
    agumented_ind[31:34] = np.random.permutation(3) + 31

    agumented_ind_a = np.zeros([mask.shape[-1]], dtype=np.int64)
    agumented_ind_a[:34] = agumented_ind
    agumented_ind_a[34:] = np.arange(34, mask.shape[-1])

    a_one_hot_augmented = F.one_hot(a, num_classes=mask.shape[-1])[:, agumented_ind_a]
    a_augmented = torch.argmax(a_one_hot_augmented, dim=-1, keepdim=False)

    return x[:, :, agumented_ind], a_augmented, mask[:, agumented_ind_a]


class VLOG(nn.Module):

    def __init__(self, observation_space, oracle_observation_space, action_space, is_main_network=True, **kwargs):

        super(VLOG, self).__init__()

        if isinstance(action_space, Discrete):
            self.action_size = action_space.n
            self.algorithm = kwargs["algorithm"] if ("algorithm" in kwargs) else 'ddqn'
        else:
            raise NotImplementedError

        assert isinstance(observation_space, Box) and isinstance(oracle_observation_space, Box)

        self.observation_space = observation_space
        self.oracle_observation_space = oracle_observation_space

        # Must ensure that the feature dimension for input is at the first axis.
        self.full_observation_space_shape = [observation_space.shape[0] + oracle_observation_space.shape[0]] + list(
            oracle_observation_space.shape[1:])

        self.hidden_layer_width = kwargs["hidden_layer_width"] if ("hidden_layer_width" in kwargs) else 256
        self.half_hidden_layer_depth = kwargs["half_hidden_layer_depth"] if ("half_hidden_layer_depth" in kwargs) else 2
        self.act_fn = kwargs["act_fn"] if ("act_fn" in kwargs) else 'relu'
        self.z_stochastic_size = kwargs["z_stochastic_size"] if ("z_stochastic_size" in kwargs) else None
        self.beta = kwargs["beta"] if ("beta" in kwargs) else 0.0001  # Coefficient for KLD term in ELBO
        self.kld_target = kwargs["kld_target"] if ("kld_target" in kwargs) else -1

        self.tau = kwargs["tau"] if ("tau" in kwargs) else 1000
        self.lr = kwargs["lr"] if ("lr" in kwargs) else 1e-4
        self.gamma = kwargs["gamma"] if ("gamma" in kwargs) else 0.99

        self.type = kwargs["type"] if ("type" in kwargs) else "vlog"

        # ---------------------------------------- type settings ----------------------------------------
        # Available options:
        if self.type not in ["baseline", "oracle", "vlog", "vlog-self", "suphx", "opd", "vlog-oracle"]:
            raise ValueError(
                "Model type must be one of these: ['baseline', 'oracle', 'vlog', 'vlog-self', 'suphx', 'opd', 'vlog-oracle']")

        if self.type not in ["oracle", "suphx", "vlog-oracle"]:
            self.input_forward_size = [*observation_space.shape]
        else:
            self.input_forward_size = [*self.full_observation_space_shape]

        if self.type not in ["vlog-self"]:
            self.input_oracle_size = [*self.full_observation_space_shape]
        else:
            self.input_oracle_size = self.input_forward_size

        if self.type in ["baseline", "oracle", "suphx", "opd"]: 
            self.use_prior_only = True
        else:
            self.use_prior_only = False

        if "device" in kwargs:
            self.device = kwargs["device"]
        else:
            if torch.cuda.is_available():
                self.device = 'cuda'
            else:
                self.device = 'cpu'

        if self.z_stochastic_size is None:
            if self.type in ["vlog", "vlog-self", "vlog-oracle"]:
                self.z_stochastic_size = int(self.hidden_layer_width / 2)
            else:
                self.z_stochastic_size = 0

        self.verbose = kwargs["verbose"] if ("verbose" in kwargs) else 1

        self.update_times = 0

        # -------------------------------------- KLD coefficient (if using) ------------------------------
        if self.beta:
            if self.kld_target > 0:
                log_beta = torch.tensor(np.log(self.beta).astype(np.float32)).to(device=self.device)
                self.log_beta = log_beta.clone().detach().requires_grad_(True)
            else:
                self.log_beta = torch.tensor(np.log(self.beta).astype(np.float32)).to(device=self.device)

        self.alpha = 1  # speed of adjusting beta

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
            self.cql_alpha = self.alg_config["cql_alpha"] if (
                        "cql_alpha" in self.alg_config) else 0  # Conservative Q-learning (H)
            self.use_cql = True if self.cql_alpha else False
            self.soft_update_target_network = self.alg_config["soft_update_target_network"] if (
                    "soft_update_target_network" in self.alg_config) else False
            self.dueling = self.alg_config["dueling"] if ("dueling" in self.alg_config) else True

            self.alg_type = 'value_based'

            # Q network 1
            self.f_s2q = DiscreteActionQNetwork(pre_rl_size, self.action_size,
                                                 hidden_layers=[self.hidden_layer_width] * self.half_hidden_layer_depth,
                                                 dueling=self.dueling, act_fn=self.forward_act_fn)

            self.optimizer_q = torch.optim.Adam(self.parameters(), lr=self.lr)

        elif self.algorithm == 'bc':
            self.f_s2pi0 = DiscreteActionPolicyNetwork(pre_rl_size, self.action_size,
                                                       hidden_layers=[self.hidden_layer_width] * self.half_hidden_layer_depth,
                                                       act_fn=self.forward_act_fn, device=self.device)
            self.alg_type = 'supervised'
            self.ce_loss = nn.CrossEntropyLoss(reduction='none')
            self.optimizer_a = torch.optim.Adam(self.parameters(), lr=self.lr)

        else:
            raise NotImplementedError("algorithm can only be 'bc' or 'ddqn'")

        if not self.use_prior_only:
            self.optimizer_b = torch.optim.Adam([self.log_beta], lr=self.lr)

        self.to(device=self.device)

        self.h_t = None
        self.a_tm1 = None

        self.zp_tm1 = torch.zeros([1, self.z_stochastic_size],
                                  dtype=torch.float32).to(device=self.device)

        # target network
        if is_main_network:

            target_net = VLOG(observation_space, oracle_observation_space, action_space, is_main_network=False, **kwargs)

            # synchronizing target network and main network
            state_dict_tar = target_net.state_dict()
            state_dict = self.state_dict()
            for key in list(target_net.state_dict().keys()):
                state_dict_tar[key] = state_dict[key]
            target_net.load_state_dict(state_dict_tar)

            self.target_net = target_net

    def init_states(self):
        # held for future RNN implementation
        pass

    def select(self, x, o, action_mask=None, greedy=False, need_other_info=False, use_posterior=False):

        with torch.no_grad():

            if action_mask is not None:
                action_mask = torch.from_numpy(
                    action_mask.astype(np.float32).reshape([1, self.action_size]))

            x = torch.from_numpy(x.astype(np.float32).reshape([1, *list(x.shape)])).to(device=self.device)
            o = torch.from_numpy(o.astype(np.float32).reshape([1, *list(o.shape)])).to(device=self.device)

            if self.type == "suphx":
                x = torch.cat([x, 0 * o], dim=1)
            elif self.type == "oracle" or self.type == "vlog-oracle" or use_posterior:
                x = torch.cat([x, o], dim=1)
            else:
                pass

            if use_posterior and self.use_prior_only:
                warnings.warn("use_posterior does not works for non-VLOG model!")

            if (not use_posterior) or self.use_prior_only:
                x = self.encoder(x)
                e = self.forward_fnn(x)
                if self.z_stochastic_size > 0:
                    muz = self.f_h2muzp(e)
                    logsigz = self.f_h2logsigzp(e)
                    dist = dis.normal.Normal(muz, torch.exp(logsigz))
                    z = dist.sample()
                else:
                    z = self.f_h2zp(e)

            else:
                x = self.encoder_oracle(x)
                e = self.oracle_fnn(x)
                if self.z_stochastic_size > 0:
                    muz = self.f_hb2muzq(e)
                    logsigz = self.f_hb2logsigzq(e)
                    dist = dis.normal.Normal(muz, torch.exp(logsigz))
                    z = dist.sample()
                else:
                    z = self.f_hb2zq(e)

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
                            a = valid_actions[np.random.randint(len(valid_actions))]
                    else:
                        a = torch.argmax(q, dim=-1)
                        if np.prod(a.shape) == 1:
                            a = a.item()  # discrete action

            self.a_tm1 = torch.from_numpy(np.array([a]).reshape([-1])).to(device=self.device)

        if not need_other_info:
            return a
        else:
            return a, self.h_t, self.zp_tm1

    def learn_bc(self, X, XP, O, OP, A, R, D, V,
                 action_masks=None, action_masks_tp1=None, mahjong_augment=False, suphx_gamma=0):

        start_time = time.time()

        h_tensor, _, _, kld, x, xo, a, _, _, v, _, _ = self.process_data(
            X, XP, O, OP, A, R, D, V, action_masks, action_masks_tp1, mahjong_augment, suphx_gamma)

        if (not self.use_prior_only) and self.verbose and np.random.rand() < 0.005 * self.verbose:
            print("beta = {}, kld = {}, kld_target= {}".format(
                np.exp(self.log_beta.item()), kld.detach().item(), self.kld_target))

        logit_a_predict = self.f_s2pi0(h_tensor)
        loss_a = torch.mean(self.ce_loss(logit_a_predict, a) * v)
        loss_critic = torch.tensor(0)

        self.optimizer_a.zero_grad()
        if not self.use_prior_only:
            (torch.exp(self.log_beta.detach()) * kld / self.action_size + loss_a).backward()
        else:
            loss_a.backward()
        self.optimizer_a.step()

        if (not self.use_prior_only) and self.alpha and (self.kld_target > 0) and torch.sum(v).item() > 0:
            loss_beta = - torch.mean(self.log_beta * self.alpha * (
                    torch.log10(torch.clamp(kld, 1e-9, np.inf)) - np.log10(self.kld_target)).detach())

            self.optimizer_b.zero_grad()
            loss_beta.backward()
            self.optimizer_b.step()

        if self.update_times < 10:
            print("training time:", time.time() - start_time)

        self.update_times += 1

        return kld.cpu().item(), loss_critic.cpu().item(), loss_a.cpu().item()

    def learn(self, X, XP, O, OP, A, R, D, V,
              action_masks=None, action_masks_tp1=None, mahjong_augment=False, suphx_gamma=0):

        start_time = time.time()

        h_tensor, h_tp1_tensor, h_tp1_tar_tensor, kld, x, xo, a, r, d, v, m, mp = self.process_data(
            X, XP, O, OP, A, R, D, V, action_masks, action_masks_tp1, mahjong_augment, suphx_gamma)

        # ------------ compute value prediction loss  -------------
        if self.algorithm == 'ddqn':
            loss_q, loss_a = self.get_ddqn_loss(h_tensor, h_tp1_tensor, h_tp1_tar_tensor, a, r, d, v, mp)
        else:
            raise NotImplementedError

        if self.type in ["vlog", "vlog-self", "vlog-oracle"]:

            loss_q = loss_q + torch.exp(self.log_beta.detach()) * kld

            if (not self.use_prior_only) and self.verbose and np.random.rand() < 0.005 * self.verbose:
                print("beta = {}, kld = {}, kld_target= {}".format(
                    np.exp(self.log_beta.item()), kld.detach().item(), self.kld_target))

        # ---------------------- Distillation loss (only for OPD) -------------------------
        if self.type == "opd":

            phi_teacher = self.opd_teacher_model.encoder(xo)
            e_teacher = self.opd_teacher_model.forward_fnn(phi_teacher)
            h_tensor_teacher = self.opd_teacher_model.f_h2zp(e_teacher)
            q_target_teacher = self.opd_teacher_model.f_s2q(h_tensor_teacher).detach()

            a_one_hot = F.one_hot(a.to(torch.int64), num_classes=self.action_size).to(torch.float32)

            loss_q = loss_q + self.opd_mu * torch.mean(
                torch.sum(- self.f_s2q.get_log_prob(h_tensor, q_target_teacher) * a_one_hot, dim=-1) * v)

        # ---------------- Gradient descent for value functions --------------------

        self.optimizer_q.zero_grad()
        loss_q.backward()
        self.optimizer_q.step()

        # --------------------- Learning beta (only for VLOG) -----------------------------
        if self.type in ["vlog", "vlog-self", "vlog-oracle"] and self.alpha and (self.kld_target > 0) and torch.sum(v).item() > 0:
            loss_beta = - torch.mean(self.log_beta * self.alpha * (
                    torch.log10(torch.clamp(kld, 1e-9, np.inf)) - np.log10(self.kld_target)).detach())
            self.optimizer_b.zero_grad()
            loss_beta.backward()
            self.optimizer_b.step()

        # ----------------- update target Q network -------------------------------

        if self.soft_update_target_network:
            state_dict_tar = self.target_net.state_dict()
            state_dict = self.state_dict()
            for key in list(self.target_net.state_dict().keys()):
                state_dict_tar[key] = (1 - 1 / self.tau) * state_dict_tar[key] + 1 / self.tau * state_dict[key]
            self.target_net.load_state_dict(state_dict_tar)
        else:
            if self.update_times % int(self.tau) == 0:
                state_dict_tar = self.target_net.state_dict()
                state_dict = self.state_dict()
                for key in list(self.target_net.state_dict().keys()):
                    state_dict_tar[key] = 0 * state_dict_tar[key] + 1 * state_dict[key]
                self.target_net.load_state_dict(state_dict_tar)

        if self.update_times < 10:
            print("training time:", time.time() - start_time)

        self.update_times += 1

        return kld.cpu().item(), loss_q.cpu().item(), loss_a.cpu().item()

    def process_data(self, X, XP, O, OP, A, R, D, V, action_masks, action_masks_tp1,
                     mahjong_augment=False, suphx_gamma=0):

        batch_size = A.shape[0]

        if isinstance(X, np.ndarray):
            X = torch.from_numpy(X).to(device=self.device)
            XP = torch.from_numpy(XP).to(device=self.device)
            O = torch.from_numpy(O).to(device=self.device)
            OP = torch.from_numpy(OP).to(device=self.device)
            A = torch.from_numpy(A).to(device=self.device)
            R = torch.from_numpy(R).to(device=self.device)
            D = torch.from_numpy(D).to(device=self.device)
            V = torch.from_numpy(V).to(device=self.device)

            if action_masks is not None:
                action_masks = torch.from_numpy(action_masks).to(device=self.device)
            if action_masks_tp1 is not None:
                action_masks_tp1 = torch.from_numpy(action_masks_tp1).to(device=self.device)

        if not self.type == "vlog-self":
            if self.type == "suphx":
                if suphx_gamma > 0:
                    oracle_mask = torch.bernoulli(suphx_gamma * torch.ones_like(O))
                else:
                    oracle_mask = torch.zeros_like(O)
            else:
                oracle_mask = torch.ones_like(O)
            x_oracle = torch.cat([X, oracle_mask * O], dim=1).to(torch.float32)
            xp_oracle = torch.cat([XP, oracle_mask * OP], dim=1).to(torch.float32)
        else:
            x_oracle = X.to(torch.float32)
            xp_oracle = XP.to(torch.float32)

        if self.type not in ["oracle", "suphx", "vlog-oracle"]:
            x = X.to(torch.float32)
            xp = XP.to(torch.float32)
        else:
            x = x_oracle
            xp = xp_oracle

        if action_masks is not None:
            m = action_masks.to(torch.float32)
            mp = action_masks_tp1.to(torch.float32)
        else:
            m = torch.ones([batch_size, self.action_size], device=self.device).to(torch.float32)
            mp = torch.ones([batch_size, self.action_size], device=self.device).to(torch.float32)

        v = V.to(torch.float32)
        a = A.to(torch.int64)
        d = D.to(torch.float32)
        r = R.to(torch.float32)

        if mahjong_augment:  # only for Mahjong
            all_obs_concat, a, mp = augment_mahjong_data(torch.cat([x, xp, x_oracle, xp_oracle], dim=-2), a, mp)
            x = all_obs_concat[:, :x.shape[-2], :]
            xp = all_obs_concat[:, x.shape[-2]: int(2 * x.shape[-2]), :]
            x_oracle = all_obs_concat[:, int(2 * x.shape[-2]): int(2 * x.shape[-2] + x_oracle.shape[-2]), :]
            xp_oracle = all_obs_concat[:, int(2 * x.shape[-2] + x_oracle.shape[-2]):, :]

        phi = self.encoder(x)
        phi_oracle = self.encoder_oracle(x_oracle)

        phi_tp1 = self.encoder(xp)
        phi_oracle_tp1 = self.encoder_oracle(xp_oracle)

        phi_tp1_tar = self.target_net.encoder(xp)
        phi_oracle_tp1_tar = self.target_net.encoder_oracle(xp_oracle)

        if not self.use_prior_only:
            if self.z_stochastic_size > 0:
                e = self.forward_fnn(phi)
                e_oracle = self.oracle_fnn(phi_oracle)

                muzp_tensor = self.f_h2muzp(e)
                logsigzp_tensor = self.f_h2logsigzp(e)

                muzq_tensor = self.f_hb2muzq(e_oracle)
                logsigzq_tensor = self.f_hb2logsigzq(e_oracle)

                dist_q = dis.normal.Normal(muzq_tensor, torch.exp(logsigzq_tensor))
                h_tensor = dist_q.rsample()
                zq_tensor = h_tensor

                dist_p = dis.normal.Normal(muzp_tensor, torch.exp(logsigzp_tensor))
                hp_tensor = dist_p.rsample()
                zp_tensor = hp_tensor

                with torch.no_grad():
                    e_oracle_tp1 = self.oracle_fnn(phi_oracle_tp1)

                    muzq_tensor_tp1 = self.f_hb2muzq(e_oracle_tp1)
                    logsigzq_tensor_tp1 = self.f_hb2logsigzq(e_oracle_tp1)

                    dist = dis.normal.Normal(muzq_tensor_tp1, torch.exp(logsigzq_tensor_tp1))
                    h_tp1_tensor = dist.sample().detach()

                    e_oracle_tp1_tar = self.target_net.oracle_fnn(phi_oracle_tp1_tar)

                    muzq_tensor_tp1_tar = self.target_net.f_hb2muzq(e_oracle_tp1_tar)
                    logsigzq_tensor_tp1_tar = self.target_net.f_hb2logsigzq(e_oracle_tp1_tar)

                    dist = dis.normal.Normal(muzq_tensor_tp1_tar, torch.exp(logsigzq_tensor_tp1_tar))
                    h_tp1_tar_tensor = dist.sample().detach()

            else:
                zp_tensor = self.f_h2zp(self.forward_fnn(phi))
                zq_tensor = self.f_hb2zq(self.oracle_fnn(phi_oracle))

                h_tensor = zq_tensor
                hp_tensor = zp_tensor

                with torch.no_grad():
                    e_oracle_tp1 = self.oracle_fnn(phi_oracle_tp1).detach_()
                    h_tp1_tensor = self.f_hb2zq(e_oracle_tp1).detach_()

                    e_oracle_tp1_tar = self.target_net.oracle_fnn(phi_oracle_tp1_tar).detach_()
                    h_tp1_tar_tensor = self.target_net.f_hb2zq(e_oracle_tp1_tar).detach_()

        else:
            # use_prior_only (baseline)
            if self.z_stochastic_size > 0:
                e_t = self.forward_fnn(phi)
                muzp_tensor = self.f_h2muzp(e_t)
                logsigzp_tensor = self.f_h2logsigzp(self.forward_fnn(e_t))
                dist_p = dis.normal.Normal(muzp_tensor, torch.exp(logsigzp_tensor))
                zp_tensor = dist_p.rsample()

                h_tensor = zp_tensor

                with torch.no_grad():
                    e_tp1 = self.forward_fnn(phi_tp1).detach()

                    muzp_tensor_tp1 = self.f_h2muzp(e_tp1)
                    logsigzp_tensor_tp1 = self.f_h2logsigzp(self.forward_fnn(e_tp1))
                    dist_p = dis.normal.Normal(muzp_tensor_tp1, torch.exp(logsigzp_tensor_tp1))
                    h_tp1_tensor = dist_p.sample().detach()

                    e_tp1_tar = self.target_net.forward_fnn(phi_tp1_tar).detach()
                    muzp_tensor_tp1_tar = self.f_h2muzp(e_tp1_tar)
                    logsigzp_tensor_tp1_tar = self.f_h2logsigzp(self.forward_fnn(e_tp1_tar))
                    dist_p = dis.normal.Normal(muzp_tensor_tp1_tar, torch.exp(logsigzp_tensor_tp1_tar))
                    h_tp1_tar_tensor = dist_p.sample().detach()

            else:
                zp_tensor = self.f_h2zp(self.forward_fnn(phi))
                h_tensor = zp_tensor

                with torch.no_grad():
                    e_tp1 = self.forward_fnn(phi_tp1).detach()
                    h_tp1_tensor = self.f_h2zp(e_tp1).detach()

                    e_tp1_tar = self.target_net.forward_fnn(phi_tp1_tar).detach()
                    h_tp1_tar_tensor = self.target_net.f_h2zp(e_tp1_tar).detach()

        # ------------ compute divergence between z^p and z^q ------------

        if not self.use_prior_only:
            if self.z_stochastic_size > 0:

                if self.verbose and np.random.rand() < 0.005 * self.verbose:
                    tmp = np.array2string(muzp_tensor[0, :6].detach().cpu().numpy(), precision=4, separator=',  ')
                    print("muzp = " + tmp)
                    tmp = np.array2string(muzq_tensor[0, :6].detach().cpu().numpy(), precision=4, separator=',  ')
                    print("muzq = " + tmp)

                    tmp = np.array2string(logsigzp_tensor[0, :6].detach().cpu().exp().numpy(),
                                          precision=4, separator=', ')
                    print("sigzp = " + tmp)
                    tmp = np.array2string(logsigzq_tensor[0, :6].detach().cpu().exp().numpy(),
                                          precision=4, separator=', ')
                    print("sigzq = " + tmp)

                kld = torch.mean(
                    torch.sum(logsigzp_tensor - logsigzq_tensor + ((muzp_tensor - muzq_tensor).pow(2) + torch.exp(
                        logsigzq_tensor * 2)) / (2.0 * torch.exp(logsigzp_tensor * 2)) - 0.5, dim=-1) * v)
            else:
                raise NotImplementedError
        else:
            kld = torch.tensor(0)

        return h_tensor, h_tp1_tensor, h_tp1_tar_tensor, kld, x, x_oracle, a, r, d, v, m, mp

    def get_ddqn_loss(self, h_tensor, h_tp1_tensor, h_tp1_tar_tensor, a, r, d, v, mp):

        gamma = self.gamma

        # ---------- Compute Q Target ---------------

        # q_tensor = self.f_s2q(h_tensor)
        qp_tensor = self.f_s2q(h_tp1_tensor).detach()
        qp_tensor_tar = self.target_net.f_s2q(h_tp1_tar_tensor).detach()

        qp_tensor = qp_tensor * mp - (1 - mp) * INFINITY
        qp_tensor_tar = qp_tensor_tar * mp - (1 - mp) * INFINITY

        a_one_hot = F.one_hot(a.to(torch.int64), num_classes=self.action_size).to(torch.float32)

        # double Q-learning
        a_greedy = torch.argmax(qp_tensor, dim=-1, keepdim=False)
        # greedy action is selected using the main network
        a_greedy_one_hot = F.one_hot(a_greedy.to(torch.int64), num_classes=self.action_size).to(torch.float32)
        q_target = (r + (1 - d) * gamma * torch.sum(qp_tensor_tar.detach() * a_greedy_one_hot, dim=-1))

        q_target_expand = q_target.view([*q_target.size(), 1]).repeat_interleave(self.action_size, dim=-1)

        # ---------- Train ----------------

        loss_critic = torch.mean(
            torch.sum(- self.f_s2q.get_log_prob(h_tensor, q_target_expand) * a_one_hot, dim=-1) * v)

        if self.use_cql:
            loss_cql = self.cql_alpha * torch.mean(torch.logsumexp(self.f_s2q(h_tensor), dim=-1) * v
                                                   - torch.sum(a_one_hot * self.f_s2q(h_tensor), dim=-1) * v)
        else:
            loss_cql = 0

        loss_q = loss_cql + loss_critic
        loss_a = torch.tensor(0)

        return loss_q, loss_a
