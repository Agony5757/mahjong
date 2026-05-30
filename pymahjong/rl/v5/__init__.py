"""V5: Douzero-style state+action scoring head over V4 event-stream encoder.

V5 reuses every component of V4 (observation encoding, cache format,
dataset loader, environment, self-play eval) *except* the policy head.
Where V4 maps a pooled state ``h`` to 54 logits via a single linear
projection (or two phase-split projections), V5 holds a fixed
``(54, action_feat_dim)`` semantic descriptor table, projects each
action's descriptor into ``D_a`` dims, concatenates the state with
each action embedding, and scores each ``(state, action)`` pair via a
shared MLP -> scalar.  The 54 scalars are masked and softmax'd.

The intuition mirrors Douzero's Q-architecture for DouDizhu: instead of
learning 54 independent output weight vectors, the model shares
parameters across actions that share structure (tile type, action
type, red-dora flag, chi position).  Discarding 1m and discarding 2m
no longer have completely independent output heads -- they only differ
in their tile descriptor, so improvements in "how good a state is for
discarding any X" generalise across X.
"""
