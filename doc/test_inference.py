#!/bin/env python

from __future__ import print_function

verbose = __name__ == "__main__"

import os
import sys
if not verbose:
    out = open(os.devnull, 'w')
else:
    out = sys.stdout
from collections import OrderedDict
import itertools
from graph_tool.all import *
import numpy.random
from numpy.random import randint, normal, random

numpy.random.seed(42)
seed_rng(42)

graph_tool.inference.set_test(True)

g = collection.data["football"]

# # add self-loops
# for i in range(10):
#     v = numpy.random.randint(g.num_vertices())
#     g.add_edge(v, v)

# # add parallel edges
# for e in list(g.edges())[:10]:
#     g.add_edge(e.source(), e.target())

ec = g.new_ep("int", randint(0, 10, g.num_edges()))

rec_p = g.new_ep("double", random(g.num_edges()))
rec_s = g.new_ep("double", normal(0, 10, g.num_edges()))


def _gen_state(directed, deg_corr, layers, overlap, rec, rec_type):
    u = GraphView(g, directed=directed)
    if layers != False:
        base_type = graph_tool.inference.LayeredBlockState
        state_args = dict(B=u.num_vertices(),
                          deg_corr=deg_corr,
                          ec=ec.copy(),
                          recs=[rec] if rec is not None else [],
                          rec_types=[rec_type] if rec is not None else [],
                          overlap=overlap,
                          layers=layers == True)
    elif overlap:
        base_type = graph_tool.inference.OverlapBlockState
        state_args = dict(B=2 * u.num_edges(),
                          recs=[rec] if rec is not None else [],
                          rec_types=[rec_type] if rec is not None else [],
                          deg_corr=deg_corr)
    else:
        base_type = graph_tool.inference.BlockState
        state_args = dict(B=u.num_vertices(),
                          recs=[rec] if rec is not None else [],
                          rec_types=[rec_type] if rec is not None else [],
                          deg_corr=deg_corr)
    return u, base_type, state_args


def gen_state(*args):
    u, base_type, state_args = _gen_state(*args)
    return base_type(u, **state_args)

def gen_nested_state(*args):
    u, base_type, state_args = _gen_state(*args)
    B = state_args.pop("B")
    return NestedBlockState(u,
                            bs=[numpy.arange(B)] + [numpy.zeros(1)] * 6,
                            base_type=base_type, state_args=state_args,
                            sampling=True)


pranges = [("directed", [False, True]),
           ("overlap", [False, True]),
           ("layered", [False, "covariates", True]),
           ("rec", [None, "real-exponential", "real-normal"]),
           ("deg_corr", [False, True]),
           ("dl", [False, True]),
           ("degree_dl_kind", ["uniform", "distributed", "entropy"]),
           ("exact", [True, False])]

pranges = OrderedDict(pranges)

def iter_ranges(ranges):
    for vals in itertools.product(*[v for k, v in ranges.items()]):
        yield zip(ranges.keys(), vals)


for pvals in iter_ranges(pranges):
    params = OrderedDict(pvals)

    locals().update(params)

    if not deg_corr and degree_dl_kind != "uniform":
        continue

    if overlap and deg_corr and degree_dl_kind != "distributed":      # FIXME
        continue

    if (rec is not None or layered != False) and not exact:
        continue

    print(params, file=out)

    rec_ = None
    if rec == "real-exponential":
        rec_ = rec_p
    elif rec == "real-normal":
        rec_ = rec_s

    print("\t mcmc (unweighted)", file=out)
    state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)

    print("\t\t",
          state.mcmc_sweep(beta=0,
                           entropy_args=dict(dl=dl,
                                             degree_dl_kind=degree_dl_kind,
                                             exact=exact, beta_dl=0.95)),
          state.get_nonempty_B(), file=out)

    if overlap:
        print("\t\t",
              state.mcmc_sweep(beta=0, bundled=True,
                               entropy_args=dict(dl=dl,
                                                 degree_dl_kind=degree_dl_kind,
                                                 exact=exact, beta_dl=0.95)),
              state.get_nonempty_B(), file=out)

    print("\t mcmc (unweighted, multiflip)", file=out)
    state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)
    print("\t\t",
          state.multiflip_mcmc_sweep(beta=0,
                                     entropy_args=dict(dl=dl,
                                                       degree_dl_kind=degree_dl_kind,
                                                       exact=exact, beta_dl=0.95)),
          state.get_nonempty_B(), file=out)

    print("\t gibbs (unweighted)", file=out)
    state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)

    print("\t\t",
          state.gibbs_sweep(beta=0,
                            entropy_args=dict(dl=dl,
                                              degree_dl_kind=degree_dl_kind,
                                              exact=exact, beta_dl=0.95)),
          state.get_nonempty_B(), file=out)

    if not overlap:
        state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)

        print("\t mcmc", file=out)
        bstate = state.get_block_state(vweight=True,  deg_corr=deg_corr)

        print("\t\t",
              bstate.mcmc_sweep(beta=0,
                                entropy_args=dict(dl=dl,
                                                  degree_dl_kind=degree_dl_kind,
                                                  exact=exact, beta_dl=0.95)),
              bstate.get_nonempty_B(), file=out)

        print("\t\t",
              bstate.mcmc_sweep(beta=0,
                                entropy_args=dict(dl=dl,
                                                  degree_dl_kind=degree_dl_kind,
                                                  exact=exact, beta_dl=0.95)),
              bstate.get_nonempty_B(), file=out)

        print("\t\t",
              bstate.gibbs_sweep(beta=0,
                                 entropy_args=dict(dl=dl,
                                                   degree_dl_kind=degree_dl_kind,
                                                   exact=exact, beta_dl=0.95)),
              bstate.get_nonempty_B(), file=out)

    print("\t merge", file=out)

    state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)

    if not overlap:
        bstate = state.get_block_state(vweight=True, deg_corr=deg_corr)

        print("\t\t",
              bstate.merge_sweep(50,
                                 entropy_args=dict(dl=dl,
                                                   degree_dl_kind=degree_dl_kind,
                                                   multigraph=False,
                                                   exact=exact, beta_dl=0.95)),
              file=out)

        bstate = bstate.copy()

        print("\t\t",
              bstate.mcmc_sweep(beta=0,
                                entropy_args=dict(dl=dl,
                                                  degree_dl_kind=degree_dl_kind,
                                                  exact=exact, beta_dl=0.95)),
              file=out)
        print("\t\t",
              bstate.gibbs_sweep(beta=0,
                                 entropy_args=dict(dl=dl,
                                                   degree_dl_kind=degree_dl_kind,
                                                   exact=exact, beta_dl=0.95)),
              file=out)
    else:
        print("\t\t",
              state.merge_sweep(50,
                                entropy_args=dict(dl=dl,
                                                  degree_dl_kind=degree_dl_kind,
                                                  multigraph=False,
                                                  exact=exact, beta_dl=0.95)),
              file=out)

    print("\t shrink", file=out)

    state = gen_state(directed, deg_corr, layered, overlap, rec_, rec)
    state = state.shrink(B=5, entropy_args=dict(dl=dl,
                                                degree_dl_kind=degree_dl_kind,
                                                multigraph=False,
                                                exact=exact, beta_dl=0.95))
    print("\t\t", state.B, "\n", file=out)

pranges = [("directed", [False, True]),
           ("overlap", [False]),
           ("layered", [False, "covariates", True]),
           ("rec", [None, "real-exponential", "real-normal"]),
           ("deg_corr", [True, False]),
           ("degree_dl_kind", ["distributed"]),
           ("exact", [True])]

pranges = OrderedDict(pranges)

def iter_ranges(ranges):
    for vals in itertools.product(*[v for k, v in ranges.items()]):
        yield zip(ranges.keys(), vals)

for pvals in iter_ranges(pranges):
    params = OrderedDict(pvals)

    locals().update(params)

    if overlap and deg_corr and degree_dl_kind != "distributed":      # FIXME
        continue

    if (rec is not None or layered != False) and not exact:
        continue

    print(params, file=out)

    rec_ = None
    if rec == "real-exponential":
        rec_ = rec_p
    elif rec == "real-normal":
        rec_ = rec_s

    print("\t mcmc (single flip)", file=out)
    state = gen_nested_state(directed, deg_corr, layered, overlap, rec_, rec)

    for i in range(5):
        print("\t\t",
              state.mcmc_sweep(beta=0, d=0.5,
                               entropy_args=dict(degree_dl_kind=degree_dl_kind,
                                                 exact=exact,
                                                 beta_dl=0.95)),
              [s.get_nonempty_B() for s in state.levels], file=out)

    print("\n\t mcmc (multiple flip)", file=out)
    state = gen_nested_state(directed, deg_corr, layered, overlap, rec_, rec)

    for i in range(5):
        print("\t\t",
              state.multiflip_mcmc_sweep(beta=0, d=0.5,
                                         entropy_args=dict(degree_dl_kind=degree_dl_kind,
                                                           exact=exact, beta_dl=0.95)),
              [s.get_nonempty_B() for s in state.levels], file=out)

pranges = [("directed", [False, True]),
           ("overlap", [False, True]),
           ("layered", [False, "covariates", True]),
           ("rec", [None, "real-exponential", "real-normal"]),
           ("deg_corr", [False, True]),
           ("degree_dl_kind", ["uniform", "distributed", "entropy"]),
           ("exact", [True])]

pranges = OrderedDict(pranges)

for pvals in iter_ranges(pranges):
    params = OrderedDict(pvals)

    locals().update(params)

    if not deg_corr and degree_dl_kind != "uniform":
        continue

    if overlap and deg_corr and degree_dl_kind != "distributed":    # FIXME
        continue

    print(params, file=out)

    rec_ = []
    if rec == "real-exponential":
        rec_ = [rec_p]
        rec = [rec]
    elif rec == "real-normal":
        rec_ = [rec_s]
        rec = [rec]
    else:
        rec = []

    if layered != False:
        state_args = dict(ec=ec, layers=(layered == True), recs=rec_,
                          rec_types=rec)
    else:
        state_args = dict(recs=rec_, rec_types=rec)

    entropy_args = dict(exact=exact, beta_dl=0.95)

    state = minimize_blockmodel_dl(GraphView(g, directed=directed),
                                   verbose=(1, "\t") if verbose else False,
                                   deg_corr=deg_corr,
                                   overlap=overlap,
                                   layers=layered != False,
                                   state_args=state_args,
                                   mcmc_args=dict(entropy_args=entropy_args))

    print(state.B, state.entropy(), file=out)

    state = minimize_nested_blockmodel_dl(GraphView(g, directed=directed),
                                          verbose=(2, "\t") if verbose else False,
                                          deg_corr=deg_corr,
                                          overlap=overlap,
                                          layers=layered != False,
                                          state_args=state_args,
                                          mcmc_args=dict(entropy_args=entropy_args))
    if verbose:
        state.print_summary()

    print(state.entropy(), "\n", file=out)

graph_tool.inference.set_test(False)

print("OK")