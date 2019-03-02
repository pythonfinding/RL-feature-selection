import numpy as np
from gym import spaces

from wenvs.utils import dim_of_space, discrete_space_size


class WrapperEnv:

    def __init__(self, env, n_fake_features=0, n_combinations=0, 
    n_fake_actions=0, continuous_state=False, continuous_actions=False, 
    size_discrete_space=5):

        self.env=env
        self.metadata = env.metadata
        self.reward_range = env.reward_range
        self.spec = env.spec
        self.unwrapped = self
        
        self.n_fake_features = n_fake_features
        self.n_combinations = n_combinations
        self.orig_obs_space = env.observation_space
        self.orig_act_space = env.action_space
        self.n_fake_actions = n_fake_actions
        self.continuous_state = continuous_state
        self.continuous_actions = continuous_actions
        self.total_fake_features = self.n_fake_features + self.n_combinations
        self.size_discrete_space = size_discrete_space
        
        if isinstance(self.orig_obs_space, spaces.Tuple):
            assert not np.dtype('float32') in [x.dtype for x in self.orig_obs_space.spaces] or self.continuous_state, 'Must set continuous_state'
        else:
            assert not np.dtype('float32') in [self.orig_obs_space.dtype] or self.continuous_state, 'Must set continuous_state'

        self.state_dim = dim_of_space(self.orig_obs_space)

        if n_combinations != 0:
            assert self.state_dim / n_combinations >= 1, f'State dimension too small for combinations: {self.state_dim}'

        self.state_dim += self.total_fake_features
        self.action_dim = dim_of_space(self.orig_act_space)
        
        self._setup()


    def _setup(self):
        inf = np.finfo(np.float32).max

        if self.n_fake_actions > 0:
            if isinstance(self.orig_act_space, spaces.Tuple):
                action_space = self.orig_act_space.spaces
            else:
                action_space = [self.orig_act_space]

            if self.continuous_actions:
                box = [spaces.Box(low=-inf, high=inf, shape=(
                    self.n_fake_actions,), dtype=np.float32)]
            else:
                box = [spaces.Discrete(self.size_discrete_space) for _ in range(
                    self.n_fake_actions)]

            action_space = action_space + box
            self.action_space = spaces.Tuple(action_space)
        else:
            self.action_space = self.orig_act_space

        if self.n_fake_features > 0 or self.n_combinations > 0:
            if isinstance(self.orig_obs_space, spaces.Tuple):
                obs_space = self.orig_obs_space.spaces
            else:
                obs_space = [self.orig_obs_space]

            if self.continuous_state:
                box = [spaces.Box(low=-inf, high=inf, shape=(
                    self.total_fake_features,), dtype=np.float32)]
            else:
                box = [spaces.Discrete(self.size_discrete_space) for _ in range(
                    self.total_fake_features)]
                
            obs_space = obs_space + box
            self.observation_space = spaces.Tuple(obs_space)
        else:
            self.observation_space = self.orig_obs_space

        if not self.continuous_state:
            self.discrete_obs_space = discrete_space_size(self.observation_space)
        if not self.continuous_actions:
            self.discrete_acts_space = discrete_space_size(self.action_space)


    def _wrap_obs(self, obs):
        obs_add = []
    
        if self.n_combinations > 0:
            obs_comb = np.array(obs).copy().reshape(self.n_combinations, -1)
            param = np.arange(obs_comb.size).reshape(obs_comb.shape)

            obs_add.append(np.einsum('ij,ij->i', obs_comb, param))

        if self.n_fake_features > 0:
            if self.continuous_state:
                obs_add.append(np.random.normal(size=self.n_fake_features))
            else:
                obs_add.append(np.random.randint(
                    self.size_discrete_space, size=self.n_fake_features))

        if len(obs_add) == 0:
            return obs
        else:
            return np.concatenate([obs, *obs_add], axis=None).ravel()


    def _unwrap_obs(self, obs):
        assert self.observation_space.contains(obs), "Invalid Observation" 
        if self.n_combinations > 0 or self.n_fake_features > 0:
            if self.continuous_state:
                obs = obs[:-1]
            else:
                obs = obs[:-self.total_fake_features]
            if len(obs) == 1:
                obs = obs[0]

        return obs


    def _unwrap_act(self, action):
        assert self.action_space.contains(action), "Invalid Action" 
        if self.n_fake_actions > 0:
            if self.continuous_actions:
                action = action[:-1]
            else:
                action = action[:-self.n_fake_actions]
            if len(action) == 1:
                action = action[0]

        return action
        

    def decode_act(self, act_en):
        act = np.unravel_index(act_en, self.discrete_acts_space)
        if len(act) == 1:
            act = act[0]
        return act


    def encode_obs(self, obs):
        if self.state_dim == 1:
            obs = [obs]
        return np.ravel_multi_index(obs, self.discrete_obs_space)


    def encode_act(self, obs):
        if self.state_dim == 1:
            obs = [obs]
        return np.ravel_multi_index(obs, self.discrete_acts_space)


    def run_episode(self, policy=None, render=False):
        def render_it():
            if render:
                self.render()

        if policy is None:
            policy = lambda obs: self.action_space.sample()

        
        ss, acts, rs = [], [], [] 
        obs = self.reset()
        for _ in range(200):
            ss.append(obs)
            render_it()
            a = policy(obs)
            acts.append(a)
            obs, r, done, info = self.step(a)
            rs.append(r)
            if done:
                ss.append(obs)
                render_it()
                break

        return np.array(ss), np.array(acts), np.array(rs)


    def step(self, action):

        action = self._unwrap_act(action)
        obs, r, done, info = self.env.step(action)

        return self._wrap_obs(obs), r, done, info


    def seed(self, seed=None):
        return self.env.seed(seed)


    def render(self, mode='human', **kwargs):
        self.env.render(mode=mode, **kwargs)


    def reset(self):
        return self._wrap_obs(self.env.reset())


    def close(self):
        return self.env.close()


    def configure(self, *args, **kwargs):
        pass


    def __del__(self):
        self.close()


    def __str__(self):
        return '<{} instance>'.format(type(self).__name__)