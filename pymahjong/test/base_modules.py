import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
import torch.distributions as dis
import warnings


class MinusOneModule(nn.Module):
    def __init__(self):
        super(MinusOneModule, self).__init__()

    def forward(self, x):
        return x - 1


class MahjongNet(nn.Module):
    def __init__(self, n_channels):
        super(MahjongNet, self).__init__()

        self.n_channels = n_channels

        cnn_list = nn.ModuleList()
        cnn_list.append(nn.Conv1d(n_channels, 64, 3, 1, 1))
        cnn_list.append(nn.Conv1d(64, 64, 3, 1, 1))
        cnn_list.append(nn.ReLU())
        cnn_list.append(nn.Conv1d(64, 64, 3, 1, 1))
        cnn_list.append(nn.ReLU())
        cnn_list.append(nn.Conv1d(64, 32, 3, 1, 1))
        cnn_list.append(nn.ReLU())
        cnn_list.append(nn.Flatten())

        self.cnn = nn.Sequential(*cnn_list)
        # 1088

        self.phi_size = 1088

    def forward(self, x):
        # Shape of x: [batch_size x n_channels x 34]

        phi = self.cnn(x)

        return phi


class DiscreteActionQNetwork(nn.Module):
    def __init__(self, input_size, output_size, hidden_layers=None, dueling=False, act_fn=nn.ReLU):
        super(DiscreteActionQNetwork, self).__init__()

        if hidden_layers is None:
            hidden_layers = [256, 256]
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_layers = hidden_layers
        self.dueling = dueling

        self.network_modules = nn.ModuleList()

        last_layer_size = input_size
        for layer_size in hidden_layers:
            self.network_modules.append(nn.Linear(last_layer_size, layer_size))
            self.network_modules.append(act_fn())
            last_layer_size = layer_size

        if not dueling:
            self.network_modules.append(nn.Linear(last_layer_size, output_size))
        else:
            self.value_layer = nn.Linear(last_layer_size, 1)
            self.advantage_layer = nn.Linear(last_layer_size, output_size)

        self.main_network = nn.Sequential(*self.network_modules)

    def forward(self, x):

        if not self.dueling:
            q = self.main_network(x)
        else:
            h = self.main_network(x)
            v = self.value_layer(h).repeat_interleave(self.output_size, dim=-1)
            q0 = self.advantage_layer(h)
            a = q0 - torch.mean(q0, dim=-1, keepdim=True).repeat_interleave(self.output_size, dim=-1)
            q = v + a

        return q

    def get_log_prob(self, x, q_target):

        return - 0.5 * (self.forward(x) - q_target).pow(2)


class ContinuousActionQNetwork(nn.Module):
    def __init__(self, input_size, action_size, hidden_layers=None, act_fn=nn.ReLU):
        super(ContinuousActionQNetwork, self).__init__()

        if hidden_layers is None:
            hidden_layers = [256, 256]
        self.input_size = input_size
        self.action_size = action_size
        self.output_size = 1
        self.hidden_layers = hidden_layers

        self.network_modules = nn.ModuleList()

        last_layer_size = input_size + action_size
        for layer_size in hidden_layers:
            self.network_modules.append(nn.Linear(last_layer_size, layer_size))
            self.network_modules.append(act_fn())
            last_layer_size = layer_size

        self.network_modules.append(nn.Linear(last_layer_size, self.output_size))

        self.main_network = nn.Sequential(*self.network_modules)

    def forward(self, x, a):

        q = self.main_network(torch.cat((x, a), dim=-1))

        return q


class ContinuousActionVNetwork(nn.Module):
    def __init__(self, input_size, hidden_layers=None, act_fn=nn.ReLU):
        super(ContinuousActionVNetwork, self).__init__()

        if hidden_layers is None:
            hidden_layers = [256, 256]
        self.input_size = input_size
        self.output_size = 1
        self.hidden_layers = hidden_layers

        self.network_modules = nn.ModuleList()

        last_layer_size = input_size
        for layer_size in hidden_layers:
            self.network_modules.append(nn.Linear(last_layer_size, layer_size))
            self.network_modules.append(act_fn())
            last_layer_size = layer_size

        self.network_modules.append(nn.Linear(last_layer_size, self.output_size))

        self.main_network = nn.Sequential(*self.network_modules)

    def forward(self, x):

        q = self.main_network(x)

        return q


class DiscreteActionPolicyNetwork(nn.Module):
    def __init__(self, input_size, output_size, hidden_layers=None, act_fn=nn.ReLU, logit_clip=None, device='cpu'):
        super(DiscreteActionPolicyNetwork, self).__init__()

        if logit_clip is None:
            logit_clip = [-np.inf, np.inf]
        if hidden_layers is None:
            hidden_layers = [256, 256]
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_layers = hidden_layers

        self.device = device
        self.network_modules = nn.ModuleList()

        last_layer_size = input_size
        for layer_size in hidden_layers:
            self.network_modules.append(nn.Linear(last_layer_size, layer_size))
            self.network_modules.append(act_fn())
            last_layer_size = layer_size

        self.network_modules.append(nn.Linear(last_layer_size, output_size))

        self.main_network = nn.Sequential(*self.network_modules)

        self.logit_clip = logit_clip

    def forward(self, x):
        logit_pi = self.main_network(x).clamp(self.logit_clip[0], self.logit_clip[1])

        return logit_pi

    def sample_action(self, x, action_mask=None, greedy=False):

        pi = F.softmax(self.forward(x).clamp(self.logit_clip[0], self.logit_clip[1]), dim=-1)
        pi_np = (pi.cpu().detach() * action_mask).numpy()
        if greedy:
            if np.any(pi_np > 0):
                a = np.argmax(pi_np, axis=-1)
            else:
                a = np.random.choice(action_mask.shape[-1], 1, p=action_mask.numpy().reshape([-1]) / action_mask.numpy().sum())
                # warnings.warn("No preferred action, select action {}".format(a[0]))
        else:
            size_a = pi_np.shape[-1]
            a = np.zeros_like(pi_np[:, 0], dtype=np.int)
            for i in range(pi_np.shape[0]):
                a[i] = np.random.choice(size_a, p=pi_np[i, :] / pi_np[i, :].sum())
        return a


class ContinuousActionPolicyNetwork(nn.Module):
    def __init__(self, input_size, output_size, output_distribution="Gaussian", hidden_layers=None, act_fn=nn.ReLU,
                 logsig_clip=None):
        super(ContinuousActionPolicyNetwork, self).__init__()

        if logsig_clip is None:
            logsig_clip = [-20, 2]
        if hidden_layers is None:
            hidden_layers = [256, 256]
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_layers = hidden_layers
        self.logsig_clip = logsig_clip

        self.output_distribution = output_distribution  # Currently only support "Gaussian" or "DiracDelta"

        self.mu_layers = nn.ModuleList()
        self.logsig_layers = nn.ModuleList()

        last_layer_size = input_size
        for layer_size in hidden_layers:
            self.mu_layers.append(nn.Linear(last_layer_size, layer_size))
            self.mu_layers.append(act_fn())
            self.logsig_layers.append(nn.Linear(last_layer_size, layer_size))
            self.logsig_layers.append(act_fn())
            last_layer_size = layer_size
        self.mu_layers.append(nn.Linear(last_layer_size, self.output_size))
        self.logsig_layers.append(nn.Linear(last_layer_size, self.output_size))

        self.mu_net = nn.Sequential(*self.mu_layers)
        self.logsig_net = nn.Sequential(*self.logsig_layers)

    def forward(self, x):

        if self.output_distribution == "Gaussian":
            mu = self.mu_net(x)
            logsig = self.logsig_net(x).clamp(self.logsig_clip[0], self.logsig_clip[1])

            return mu, logsig

        else:
            raise NotImplementedError

    def get_log_action_probability(self, x, a):

        mu = self.mu_net(x)
        logsig = self.logsig_net(x).clamp(self.logsig_clip[0], self.logsig_clip[1])

        dist = torch.distributions.normal.Normal(loc=mu, scale=torch.exp(logsig))
        log_action_probability = dist.log_prob(a)

        return log_action_probability

    def sample_action(self, x, greedy=False):

        mu = self.mu_net(x)
        logsig = self.logsig_net(x).clamp(self.logsig_clip[0], self.logsig_clip[1])

        if greedy:
            return torch.tanh(mu).detach().cpu().numpy()

        else:
            dist = torch.distributions.normal.Normal(loc=mu, scale=torch.exp(logsig))
            sampled_u = dist.sample()

            return torch.tanh(sampled_u.detach().cpu()).numpy()


def make_cnn(resolution, n_channels):
    if resolution == "10x10":
        # -------- MinAtar ---------
        cnn_module_list = nn.ModuleList()
        cnn_module_list.append(nn.Conv2d(n_channels, 16, 3, 1, 0))
        cnn_module_list.append(nn.ReLU())
        cnn_module_list.append(nn.Conv2d(16, 32, 3, 1, 0))
        cnn_module_list.append(nn.ReLU())
        cnn_module_list.append(nn.Conv2d(32, 128, 4, 2, 0))
        cnn_module_list.append(nn.ReLU())
        cnn_module_list.append(nn.Conv2d(128, 256, 2, 1, 0))
        cnn_module_list.append(nn.ReLU())
        cnn_module_list.append(nn.Flatten())
        phi_size = 256

    elif resolution == "34":
        # -------- for Mahjong ---------
        mahjong_net = MahjongNet(n_channels)
        phi_size = mahjong_net.phi_size
        return mahjong_net, phi_size

    return nn.Sequential(*cnn_module_list), phi_size
