#!/usr/bin/env python
import os
import sys
import json

def usage():
    return '''
constructs adjacency_graphs.coffee from QWERTY and DVORAK keyboard layouts

usage:
%s adjacency_graphs.coffee
''' % sys.argv[0]

qwerty = r'''
`~ 1! 2@ 3# 4$ 5% 6^ 7& 8* 9( 0) -_ =+
    qQ wW eE rR tT yY uU iI oO pP [{ ]} \|
     aA sS dD fF gG hH jJ kK lL ;: '"
      zZ xX cC vV bB nN mM ,< .> /?
'''

dvorak = r'''
`~ 1! 2@ 3# 4$ 5% 6^ 7& 8* 9( 0) [{ ]}
    '" ,< .> pP yY fF gG cC rR lL /? =+ \|
     aA oO eE uU iI dD hH tT nN sS -_
      ;: qQ jJ kK xX bB mM wW vV zZ
'''

keypad = r'''
  / * -
7 8 9 +
4 5 6
1 2 3
  0 .
'''

mac_keypad = r'''
  = / *
7 8 9 -
4 5 6 +
1 2 3
  0 .
'''

def get_slanted_adjacent_coords(x, y):
    '''
    returns the six adjacent coordinates on a standard keyboard, where each row is slanted to the
    right from the last. adjacencies are clockwise, starting with key to the left, then two keys
    above, then right key, then two keys below. (that is, only near-diagonal keys are adjacent,
    so g's coordinate is adjacent to those of t,y,b,v, but not those of r,u,n,c.)
    '''
    return [(x-1, y), (x, y-1), (x+1, y-1), (x+1, y), (x, y+1), (x-1, y+1)]

def get_aligned_adjacent_coords(x, y):
    '''
    returns the nine clockwise adjacent coordinates on a keypad, where each row is vert aligned.
    '''
    return [(x-1, y), (x-1, y-1), (x, y-1), (x+1, y-1), (x+1, y), (x+1, y+1), (x, y+1), (x-1, y+1)]

def build_graph(layout_str, slanted):
    '''
    builds an adjacency graph as a dictionary: {character: [adjacent_characters]}.
    adjacent characters occur in a clockwise order.
    for example:
    * on qwerty layout, 'g' maps to ['fF', 'tT', 'yY', 'hH', 'bB', 'vV']
    * on keypad layout, '7' maps to [None, None, None, '=', '8', '5', '4', None]
    '''
    position_table = {} # maps from tuple (x,y) -> characters at that position.
    tokens = layout_str.split()
    token_size = len(tokens[0])
    x_unit = token_size + 1 # x position unit len is token len plus 1 for the following whitespace.
    adjacency_func = get_slanted_adjacent_coords if slanted else get_aligned_adjacent_coords
    assert all(len(token) == token_size for token in tokens), 'token len mismatch:\n ' + layout_str
    for y, line in enumerate(layout_str.split('\n')):
        # the way I illustrated keys above, each qwerty row is indented one space in from the last
        slant = y - 1 if slanted else 0
        for token in line.split():
            x, remainder = divmod(line.index(token) - slant, x_unit)
            assert remainder == 0, 'unexpected x offset for %s in:\n%s' % (token, layout_str)
            position_table[(x,y)] = token

    adjacency_graph = {}
    for (x,y), chars in position_table.items():
        for char in chars:
            adjacency_graph[char] = []
            for coord in adjacency_func(x, y):
                # position in the list indicates direction
                # (for qwerty, 0 is left, 1 is top, 2 is top right, ...)
                # for edge chars like 1 or m, insert None as a placeholder when needed
                # so that each character in the graph has a same-length adjacency list.
                adjacency_graph[char].append(position_table.get(coord, None))
    return adjacency_graph

GRAPHS = [('qwerty', (qwerty, True)),
          ('dvorak', (dvorak, True)),
          ('keypad', (keypad, False)),
          ('mac_keypad', (mac_keypad, False))]

def output_coffee(path):
    with open(path, 'w') as f:
        f.write('# generated by scripts/build_keyboard_adjacency_graphs.py\n')
        f.write('adjacency_graphs = \n  ')
        lines = []
        for graph_name, args in GRAPHS:
            graph = build_graph(*args)
            lines.append('%s: %s' % (graph_name, json.dumps(graph, sort_keys=True)))
        f.write('\n  '.join(lines))
        f.write('\n\n')
        f.write('module.exports = adjacency_graphs\n')

def escape(x):
    return x.replace("\\", "\\\\").replace("\"", "\\\"")

def output_hpp(hpp_file):
    with open(hpp_file, 'w') as f:
        f.write('// generated by scripts/build_keyboard_adjacency_graphs.py\n')
        tags = ',\n  '.join(k.upper() for (k, _) in GRAPHS)

        f.write("""#ifndef __ZXCVBN__ADJACENCY_GRAPHS_HPP
#define __ZXCVBN__ADJACENCY_GRAPHS_HPP

#include <zxcvbn/optional.hpp>

#include <array>
#include <initializer_list>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace zxcvbn {

enum class GraphTag {
  %s
};

}

namespace std {

template<>
struct hash<zxcvbn::GraphTag> {
  std::size_t operator()(const zxcvbn::GraphTag & v) const {
    return static_cast<std::size_t>(v);
  }
};

}

namespace zxcvbn {

using Graph = std::unordered_map<std::string, std::vector<optional::optional<std::string>>>;
using Graphs = std::unordered_map<GraphTag, Graph>;
const Graphs & graphs();

using degree_t = double;

extern const degree_t KEYBOARD_AVERAGE_DEGREE;
extern const degree_t KEYPAD_AVERAGE_DEGREE;

extern const std::size_t KEYBOARD_STARTING_POSITIONS;
extern const std::size_t KEYPAD_STARTING_POSITIONS;

}

#endif
"""  % (tags,))

def output_cpp(cpp_file):
    with open(cpp_file, 'w') as f:
        f.write('// generated by scripts/build_keyboard_adjacency_graphs.py\n')
        f.write("#include <zxcvbn/adjacency_graphs.hpp>\n\n")
        f.write("#include <zxcvbn/optional.hpp>\n\n")
        f.write("#include <array>\n")
        f.write("#include <initializer_list>\n")
        f.write("#include <utility>\n\n")

        # find out largest adjacency_list
        largest = max(len(adj)
                      for (_, args2) in GRAPHS
                      for adj in build_graph(*args2).values())

        f.write("""namespace zxcvbn {

static
optional::optional<std::string> M(const char *s) {
  return optional::make_optional(std::string(s));
}

const auto no = optional::nullopt;

""")

        f.write("const Graphs _graphs = {\n")
        for (name, args2) in GRAPHS:
            graph = build_graph(*args2)

            f.write("  {GraphTag::%s, {\n" % (name.upper(),));

            for key, adj in sorted(graph.items()):
                f.write('    {"%s", {%s}},\n' %
                        (escape(key), ', '.join('M("' + escape(a) + '")'
                                                if a else
                                                'no'
                                                for a in adj)))
            f.write("  }},\n")

        f.write("""};

// on qwerty, 'g' has degree 6, being adjacent to 'ftyhbv'. '\' has degree 1.
// this calculates the average over all keys.
static
degree_t calc_average_degree(const Graph & graph)  {
  degree_t average = 0;
  for (const auto & item : graph) {
    for (const auto & neighbor : item.second) {
        average += neighbor ? 1 : 0;
    }
  }
  average /= graph.size();
  return average;
}

extern const degree_t KEYBOARD_AVERAGE_DEGREE = calc_average_degree(_graphs.at(GraphTag::QWERTY));
// slightly different for keypad/mac keypad, but close enough
extern const degree_t KEYPAD_AVERAGE_DEGREE = calc_average_degree(_graphs.at(GraphTag::KEYPAD));

extern const std::size_t KEYBOARD_STARTING_POSITIONS = _graphs.at(GraphTag::QWERTY).size();
extern const std::size_t KEYPAD_STARTING_POSITIONS = _graphs.at(GraphTag::KEYPAD).size();

const Graphs & graphs() {
  return _graphs;
}

""")
        f.write("}\n")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(usage())
        sys.exit(0)

    output_file = sys.argv[1]
    _, ext = os.path.splitext(output_file.lower())
    if ext == ".cpp":
        output_fn = output_cpp
    elif ext == ".hpp":
        output_fn = output_hpp
    else:
        output_fn = output_coffee

    output_fn(output_file)

    sys.exit(0)

