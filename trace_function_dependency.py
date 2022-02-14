"""
This tool can trace function dependency. The goal is to get function call stack 
that help refactoring. Please note that it can only trace approximately dependencies, 
some rare usages might not be traced(use --verbose to get details) or irrelevant 
usages might be traced. Still, it can trace most of the cases.

The function dependencies are like function A is used in function B1 and B2,
function B1 is used in function C. 
i.e. A -> B1 -> C
     A -> B2

-----------------------------
Usage:
    trace where is a function used:
        python trace_function_dependency.py <target path> --function <function name>
    trace where are a module used:
        python trace_function_dependency.py <target path> --module <module path>
    do not trace some dirs:
        --skip dir1 dir2 dir3

Example:
    python trace_function_dependency.py . --function foo
    python trace_function_dependency.py . --module foo.py  --skip /dir1 /dir2

-----------------------------
Output format:
    Node Tree:
        filepath:lineno, class::function::function
            filepath:lineno, class::function::function::call
                filepath:lineno, function::call
                    filepath:lineno, function::function::call
                    filepath:lineno, function::function::call
        filepath:lineno, function::function::call
            filepath:lineno, function::call
            filepath:lineno, function::call

    JSON structure:
        {
            str: filepath,
            int: lineno,
            list: names,
            list: child_nodes = [
                {
                    str: filepath,
                    int: lineno,
                    list: names,
                    list: child_nodes
                },
                {
                    str: filepath,
                    int: lineno,
                    list: names,
                    list: child_nodes
                },
            ]
        }
"""


import os
import argparse
import ast
import json
import logging as log


SKIP = []


class File():
    """
    Attributes:
        filepath: A string of filepath.
        import_list: A list store all import name or asname in a file.
    """
    def __init__(self, filepath, import_list=[]):
        self.filepath = filepath
        self.import_list = import_list


class Node(object):
    """
    Every object in AST(abstract syntax tree) is a node. Node is used as
    class, function or call here.

    Attributes:
        node: A ast.Node object.
        names: A list store class, function and call name. The names in front are
               parent class or function. The names behind are child function or
               call. e.g. [foo, outerfunction, innerfunction, bar] is
               class foo():
                   def outerfunction():
                       def innerfunction():
                           bar()
        file: A File instance.
        parent_node: A Node instance is called in this node.
        child_nodes: A list of Node instance that call this node.
    """
    def __init__(self, node, names, file, parent_node=None):
        self.node = node
        self.names = names
        self.file = file
        self.parent_node = parent_node
        self.child_nodes = []

        if self.parent_node:
            self.parent_node.child_nodes.append(self)

    def get_call_name(self):
        return self.names[-1].split('.')[-1]

    def get_outermost_function_name(self):
        for name in self.names:
            if name:
                if not name[0].isupper():  # uppercase indicates class
                    return name
            else:
                return name

        return ''

    # TODO: solve unparse call node
    @staticmethod
    def get_call_name_in_ast(value, filepath):
        """
        A call might have others node in front of it. This function will
        get its fullname. e.g. Class.foo() or attr.foo()

        Attributes:
            value: A ast.Call object.
        """
        names = []

        while True:
            if isinstance(value, ast.Attribute):
                names.append(value.attr)
                value = value.value
            elif isinstance(value, ast.Call):
                value = value.func
            elif isinstance(value, ast.Subscript):
                value = value.value
            elif isinstance(value, ast.Str):
                names.append(value.s)
                break
            elif isinstance(value, ast.Name):
                names.append(value.id)
                break
            else:
                log.debug('unparse: ' + str(value))
                log.debug(filepath + ':' + str(value.lineno))
                break

        names.reverse()
        return '.'.join(names)

    @staticmethod
    def get_tree(parent_node, indent_level=1):
        """To render nodes info and relation into easily readable format."""
        tree = ''
        indent = '    ' * indent_level
        indent_level += 1

        for child_node in parent_node.child_nodes:
            tree += indent + child_node.file.filepath + ':' + \
                    str(child_node.node.lineno) + \
                    ', ' + '::'.join(child_node.names) + '\n'
            tree += Node.get_tree(child_node, indent_level)

        return tree


def get_stem_in_filepath(filepath):
    basename = os.path.basename(filepath)
    return basename.split('.')[0]


def is_skip(path, root_abs_path):
    # set to same root path
    abs_path = os.path.abspath(path)
    path = abs_path.split(root_abs_path)[1]

    for skip_dir in SKIP:
        if path.find(skip_dir) == 0:
            return True

    return False


def get_import_in_program(ast_root_node):
    """To get all import name or asname in a program."""
    import_list = []

    for child_node in ast.walk(ast_root_node):
        if isinstance(child_node, ast.Import) or \
            isinstance(child_node, ast.ImportFrom):
            for name in child_node.names:
                import_list.append(name.asname if name.asname else name.name)

    return import_list


def build_call_in_program(call_nodes, ast_root_node, file, names=[]):
    """
    To get all ast.Call object in a program.

    Attributes:
        call_nodes: A dict saves all ast.Call nodes found in program, use call
                    name as key, same calls' name are stored in a list. 
                    e.g. {str: list, str: list, ...}
        ast_root_node: A ast.Module object.
        file: A File instance.
        names: names is defined in Node.

    Returns:
        Result are stored in call_nodes.
    """
    for child_node in ast.iter_child_nodes(ast_root_node):
        if isinstance(child_node, ast.ClassDef) or \
            isinstance(child_node, ast.FunctionDef):
            child_names = names + [child_node.name]
            build_call_in_program(call_nodes, child_node, file, child_names)
        else:
            for grandchild_node in ast.walk(child_node):
                if isinstance(grandchild_node, ast.Call):
                    call_name = Node.get_call_name_in_ast(grandchild_node.func, file.filepath)
                    call = Node(grandchild_node, names + [call_name], file)

                    call_nodes.setdefault(call.get_call_name(), [])
                    call_nodes[call.get_call_name()].append(call)


def build_call_and_import_in_path(call_nodes, path, root_abs_path):
    """
    To traverse file in path and get call and import.

    Attributes:
        call_nodes: A dict saves all ast.Call nodes found in program, use call
                    name as key, same calls' name are stored in a list. 
                    e.g. {str: list, str: list, ...}
        path: A string of dirpath or filepath.

    Returns:
        Result are stored in call_nodes.
    """
    if os.path.isdir(path):
        for child in os.listdir(path):
            child_path = os.path.join(path, child)

            if not is_skip(child_path, root_abs_path):
                build_call_and_import_in_path(call_nodes, child_path, root_abs_path)
    elif os.path.isfile(path):
        root, extension = os.path.splitext(path)

        if extension == '.py':
            with open(path, 'r') as f:
                try:
                    ast_root_node = ast.parse(f.read())
                    file = File(path, get_import_in_program(ast_root_node))
                    build_call_in_program(call_nodes, ast_root_node, file)
                except SyntaxError:
                    log.debug('unparse node')


def build_function_in_program(ast_root_node, root_node, file, names=[]):
    """
    To get all ast.FunctionDef object in a program.

    Attributes:
        ast_root_node: A ast.Module instance.
        root_node: A Node that is parent of all functions in a module.
        file: A file instance.
        names: names is defined in Node.

    Returns:
        The functions found in program are stored as child node of root_node.
    """
    has_next = False

    for child_node in ast.iter_child_nodes(ast_root_node):
        if isinstance(child_node, ast.ClassDef) or \
            isinstance(child_node, ast.FunctionDef):
            child_names = names + [child_node.name]
            build_function_in_program(child_node, root_node, file, child_names)
            has_next = True

    if not has_next:
        Node(ast_root_node, names, file, parent_node=root_node)


def build_function_in_path(root_node, path):
    """
    To get all ast.FunctionDef object in path.
    
    Attributes:
        root_node: A Node that is parent of all functions in a module.
        path: A string of dirpath or filepath.

    Returns:
        The functions found in program are stored as child node of root_node.
    """
    if os.path.isdir(path):
        for child in os.listdir(path):
            build_function_in_path(root_node, os.path.join(path, child))
    elif os.path.isfile(path):
        _, extension = os.path.splitext(path)

        if extension == '.py':
            with open(path, 'r') as f:
                try:
                    ast_root_node = ast.parse(f.read())
                    build_function_in_program(ast_root_node, root_node, File(path))
                except SyntaxError:
                    log.debug('unparse')


def is_function_used(parent_node, call_node):
    """
    To check if a parent_node is used by a call_node.

    Attributes:
        parent_node: A Node instance.
        call_node: A Node instance.
    """
    parent_function_name = parent_node.get_outermost_function_name()
    call_name = call_node.get_call_name()

    if call_name == parent_function_name:
        import_list = call_node.file.import_list
        parent_file_stem_name = get_stem_in_filepath(parent_node.file.filepath)

        if call_name in import_list and \
            len(call_node.names[-1].split('.')) == 1:
            return True
        elif parent_file_stem_name in import_list and \
             parent_file_stem_name in call_node.names[-1]:
            return True
        elif parent_node.file.filepath == call_node.file.filepath:
            return True
        elif parent_node.file.filepath == 'root':
            return True

    return False


def trace_funtion_dependency(call_nodes, parent_node):
    """
    To trace where a function is used and also where its child function is used.
    
    Attributes:
        call_nodes: A dict saves all ast.Call nodes found in program, use call
                    name as key, same calls' name are stored in a list. 
                    e.g. {str: list, str: list, ...}
        parent_node: A Node instance is used to search in call_nodes.

    Returns:
        If parent_node is called, the call_node call parent_node will be stored
        as child node of parent_node.
    """
    call_nodes_is_used = []
    parent_function_name = parent_node.get_outermost_function_name()

    for call_node in call_nodes.get(parent_function_name, []):
        if is_function_used(parent_node, call_node):
            call_node.parent_node = parent_node
            parent_node.child_nodes.append(call_node)

            call_nodes_is_used.append(call_node)

    for call_node in call_nodes_is_used:
        call_nodes[parent_function_name].remove(call_node)

    for child_node in parent_node.child_nodes:
        trace_funtion_dependency(call_nodes, child_node)


def count_child_nodes_len(parent_node):
    len = 0

    for child_node in parent_node.child_nodes:
        len += 1
        len += count_child_nodes_len(child_node)

    return len


def convert_node_tree_into_dict(root_node):
    nodes_dict = {
        'filepath': root_node.file.filepath,
        'lineno': root_node.node.lineno if root_node.node else None,
        'name': ', '.join(root_node.names),
        'child_nodes': []
    }

    for child_node in root_node.child_nodes:
        nodes_dict['child_nodes'].append(convert_node_tree_into_dict(child_node))

    return nodes_dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='path(dir or file) to be searched is required')
    parser.add_argument(
        '-v', '--verbose', help='show details', action='store_const', const=log.DEBUG, default=log.ERROR
    )
    parser.add_argument('--json', help='output as json format', action='store_true')
    parser.add_argument(
        '--skip', nargs='*', type=str, default=[], help='dirs/files do not want to be traced'
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--function', type=str, help='function name to be searched is required')
    group.add_argument('--module', type=str, help='module name or filename to be searched is required')

    args = parser.parse_args()
    log.basicConfig(level=args.verbose)

    if (args.function and args.module) or not(args.function or args.module):
        print('Error! Choose either function or module mode.')
        return None

    if args.skip:
        global SKIP
        SKIP += args.skip

    call_nodes = {}
    build_call_and_import_in_path(call_nodes, args.path, os.path.abspath(args.path))

    if args.function:
        root_node = Node(None, [args.function], File('root'))
        trace_funtion_dependency(call_nodes, root_node)
    elif args.module:
        root_node = Node(None, ['root'], File(args.module))
        build_function_in_path(root_node, root_node.file.filepath)
        for child_node in root_node.child_nodes:
            trace_funtion_dependency(call_nodes, child_node)

    if args.json:
        nodes_dict = convert_node_tree_into_dict(root_node)
        print(json.dumps(nodes_dict, indent=4))
    else:
        print('root, ' + ', '.join(root_node.names))
        print(Node.get_tree(root_node))

    if args.function:
        print('Total target function is used: ' + \
                str(count_child_nodes_len(root_node)))
    elif args.module:
        print('Total target function is used: ' + \
                str(count_child_nodes_len(root_node)-len(root_node.child_nodes)))


if __name__ == '__main__':
    main()
