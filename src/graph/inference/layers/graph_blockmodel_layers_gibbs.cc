// graph-tool -- a general graph modification and manipulation thingy
//
// Copyright (C) 2006-2018 Tiago de Paula Peixoto <tiago@skewed.de>
//
// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 3
// of the License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <http://www.gnu.org/licenses/>.

#include "graph_tool.hh"
#include "random.hh"

#include <boost/python.hpp>

#include "../blockmodel/graph_blockmodel_util.hh"
#include "../blockmodel/graph_blockmodel.hh"
#define BASE_STATE_params BLOCK_STATE_params
#include "graph_blockmodel_layers.hh"
#include "../blockmodel/graph_blockmodel_gibbs.hh"
#include "../loops/gibbs_loop.hh"

using namespace boost;
using namespace graph_tool;

GEN_DISPATCH(block_state, BlockState, BLOCK_STATE_params)

template <class BaseState>
GEN_DISPATCH(layered_block_state, Layers<BaseState>::template LayeredBlockState,
             LAYERED_BLOCK_STATE_params)

template <class State>
GEN_DISPATCH(gibbs_block_state, Gibbs<State>::template GibbsBlockState,
             GIBBS_BLOCK_STATE_params(State))

python::object gibbs_layered_sweep(python::object ogibbs_state,
                                   python::object olayered_state,
                                   rng_t& rng)
{
    python::object ret;
    auto dispatch = [&](auto* block_state)
    {
        typedef typename std::remove_pointer<decltype(block_state)>::type
            state_t;

        layered_block_state<state_t>::dispatch
            (olayered_state,
             [&](auto& ls)
             {
                 typedef typename std::remove_reference<decltype(ls)>::type
                     layered_state_t;

                 gibbs_block_state<layered_state_t>::make_dispatch
                     (ogibbs_state,
                      [&](auto& s)
                      {
                          auto ret_ = gibbs_sweep(s, rng);
                          ret = tuple_apply([&](auto&... args){ return python::make_tuple(args...); }, ret_);
                      });
             },
             false);
    };
    block_state::dispatch(dispatch);
    return ret;
}

class gibbs_sweep_base
{
public:
    virtual std::tuple<double, size_t, size_t> run(rng_t&) = 0;
};

template <class State>
class gibbs_sweep_dispatch : public gibbs_sweep_base
{
public:
    gibbs_sweep_dispatch(State& s) : _s(s) {}

    virtual std::tuple<double, size_t, size_t> run(rng_t& rng)
    {
        return gibbs_sweep(_s, rng);
    }
private:
    State _s;
};

python::object gibbs_layered_sweep_parallel(python::object ogibbs_states,
                                           python::object olayered_states,
                                           rng_t& rng)
{
    std::vector<std::shared_ptr<gibbs_sweep_base>> sweeps;

    size_t N = python::len(ogibbs_states);
    for (size_t i = 0; i < N; ++ i)
    {
        auto dispatch = [&](auto* block_state)
            {
                typedef typename std::remove_pointer<decltype(block_state)>::type
                    state_t;

                layered_block_state<state_t>::dispatch
                    (olayered_states[i],
                     [&](auto& ls)
                     {
                         typedef typename std::remove_reference<decltype(ls)>::type
                             layered_state_t;

                         gibbs_block_state<layered_state_t>::make_dispatch
                             (ogibbs_states[i],
                              [&](auto& s)
                              {
                                  typedef typename std::remove_reference<decltype(s)>::type
                                      s_t;
                                  sweeps.push_back(std::make_shared<gibbs_sweep_dispatch<s_t>>(s));
                              });
                     },
                     false);
            };
        block_state::dispatch(dispatch);
    }

    std::vector<std::shared_ptr<rng_t>> rngs;
    init_rngs(rngs, rng);

    std::vector<std::tuple<double, size_t, size_t>> rets(N);

    #pragma omp parallel for schedule(runtime)
    for (size_t i = 0; i < N; ++i)
    {
        auto& rng_ = get_rng(rngs, rng);
        rets[i] = sweeps[i]->run(rng_);
    }

    python::list orets;
    for (auto& ret : rets)
        orets.append(tuple_apply([&](auto&... args){ return python::make_tuple(args...); }, ret));
    return orets;
}

void export_layered_blockmodel_gibbs()
{
    using namespace boost::python;
    def("gibbs_layered_sweep", &gibbs_layered_sweep);
    def("gibbs_layered_sweep_parallel", &gibbs_layered_sweep_parallel);
}
