from copy import deepcopy
import re
from jsonpath_ng import parse
from jsonpath_ng.ext import parse as parse_ext


def assign_json_path_value(message_for_update, jspath, value):
    """
    * Assign (update or insert) a value to message based on jsonpath.
    * Create the keys if jspath doesn't already exist in the message. In this case, we
    * support 'simple' jsonpath like $.path1.path2.path3....
    * @param {dict} message_for_update The message used for update
    * @param {string} jspath JSON path string
    * @param {*} value Value to update to
    * @return {*} updated message
    """
    message = deepcopy(message_for_update)
    if not parse(jspath).find(message):
        paths = jspath.lstrip("$.").split(".")
        current_item = message
        key_not_found = False
        for path in paths:
            if key_not_found or path not in current_item:
                key_not_found = True
                new_path_dict = {}
                # Add missing key to existing dict
                current_item[path] = new_path_dict
                # Set current item to newly created dict
                current_item = new_path_dict
            else:
                current_item = current_item[path]
    parse(jspath).update(message, value)
    return message


class ArrayPathTree:
    """
    Tree implementation which saves the array part of the jsonpath
    """

    def __init__(self, val="", node_idx=0, is_root=False):
        self.val = val
        if not is_root:
            self.val += '['+str(node_idx)+']'
        self.children = []

    def add_child(self, val, node_idx):
        child = ArrayPathTree(val, node_idx)
        self.children.append(child)
        return child


def build_jspath_recursively(root, path_list, path, tree_level):

    if(len(path) > tree_level):
        path[tree_level] = root.val
    else:
        path.append(root.val)
  
    if root.children:
        tree_level = tree_level + 1
        for child in root.children:
            build_jspath_recursively(child, path_list, path, tree_level)
    else:
        path_list.append(deepcopy(path))
 
def assign_json_path_values(
    source_message, source_jspath, message_for_update, dest_jspath, value
):
    """
    * Assign (update or insert) a value to message based on jsonpath.
    * Create the keys if dest_jspath doesn't already exist in the message. In this case, we
    * support 'simple' jsonpath like $.path1.path2.path3....
    * @param {dict} message_for_update The message to be updated
    * @param {string} dest_jspath JSON path string
    * @param {*} value Value to update to
    * @return {*} updated message
    """
    message = deepcopy(message_for_update)

    # Construct the tree which saves the array part of the jsonpath
    # The top tree level is the root of jsonpath ("$")
    #   and the subsequent levels are partitioned by the array components of the jsonpath
    # The degree of a tree node is determined by the number of elements from source_jsonpath
    # E.g., for a source_jsonpath of "$.X[*].Y[*]" and a dest_jsonpath of "$.A.B[*].C[*]",
    #   if the array size is 2 for "$.X[*]", 3 for "$.X[0].Y[*]", and 2 for "$.X[1].Y[*]",
    #   the tree structure will be:
    #
    #              $
    #             / \
    #            /   \
    #           /     \
    #          /       \
    #         /         \
    #      A.B[0]       A.B[1]
    #      / | \        / \
    #     /  |  \      /   \
    #    /   |   \    /     \
    # C[0] C[1] C[2] C[0]   C[1]
    #
    source_jspath_arrays = source_jspath.split('[*]')[:-1]
    dest_jspath_arrays = [m.lstrip('$').strip('.') for m in dest_jspath.split('[*]')][:-1]
    #array_regex = r"([^$\]\[\*]+)\[\*\]"
    #print("ZHL ",dest_jspath_arrays, re.findall(array_regex, dest_jspath))
    if len(source_jspath_arrays) != len(dest_jspath_arrays):
        raise ValueError(
            "inconsistent number of arrays found from the output source and destination path in CMA"
        )
    root = ArrayPathTree('$', 0, is_root=True)
    parents = [root]
    for idx, (source_jspath_array, dest_jspath_array) in enumerate(zip(source_jspath_arrays, dest_jspath_arrays)):
        source_jspath_partial = '$.' + '[*].'.join(source_jspath_arrays[:idx+1])
        nums_children = [m.value for m in parse_ext(source_jspath_partial+ '.`len`').find(source_message)]
        if len(nums_children) != len(parents):
            raise Exception("Something goes wrong")
        children = []
        count = 0
        for i, parent in enumerate(parents):
            for j in range(nums_children[i]):
                child = parent.add_child(dest_jspath_array,j )
                children.append(child)
                count += 1
        parents = children

    # Build the tree
    path_list = []
    build_jspath_recursively(root, path_list, [], 0)

    # Update the jspath
    count = 0
    for path in path_list:
        jspath = '.'.join(path) + dest_jspath.split('[*]')[-1] #NOTE not clean
        parse_ext(jspath).update_or_create(message, value[count])
        count += 1

    # Return
    return message
