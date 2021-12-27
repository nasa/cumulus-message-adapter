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


class JspathTree:

    def __init__(self, idx=0, val="", is_array=False):
        self.idx = idx
        self.val = val
        if is_array:
            self.val += '['+str(idx)+']'
        self.children = []

    def add_child(self, idx, val):
        child = JspathTree(idx, val, True)
        self.children.append(child)
        return child


# Helper function to print path from root
# to leaf in binary tree
def printPathsRec(root, path_list, path, pathLen):
     
    # Base condition - if binary tree is
    # empty return
    if root is None:
        return
 
    # add current root's val into
    # path_ar list
     
    # if length of list is gre
    if(len(path) > pathLen):
        path[pathLen] = root.val
    else:
        path.append(root.val)
 
    # increment pathLen by 1
    pathLen = pathLen + 1
 
    if not root.children:
         
        # leaf node then print the list
        printArray(path, pathLen)
        print("indside path: ",path)
        print("indside list before: ",path_list)
        path_list.append(deepcopy(path))
        print("indside list after : ",path_list)
    else:
        # try for left and right subtree
        for child in root.children:
            printPathsRec(child, path_list, path, pathLen)
 
# Helper function to print list in which
# root-to-leaf path is stored
def printArray(ints, len):
    for i in ints[0 : len]:
        print(i," ",end="")
    print()

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
    print(source_jspath, dest_jspath)
    message = deepcopy(message_for_update)

    #
    source_jspath_arrays = source_jspath.split('[*]')[:-1]
    dest_jspath_arrays = [m.strip('.') for m in dest_jspath.split('[*]')][:-1]
    if len(source_jspath_arrays) != len(dest_jspath_arrays):
        raise ValueError(
            "inconsistent number of arrays found from the output source and destination path in CMA"
        )
    root = JspathTree(0, '$.')
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
                child = parent.add_child(j, dest_jspath_array)
                children.append(child)
                count += 1
        parents = children

    path_list = []
    printPathsRec(root, path_list, [], 0)
    from pprint import pprint; pprint(path_list)
    import sys; sys.exit(0)





    # Collect array info from jspath
    array_regex = r"([^$\.\]\[\*]+)\[\*\]"
    source_jspath_array_names = re.findall(array_regex, source_jspath)
    source_jspath_array_indices = [m.start(0) for m in re.finditer(array_regex, source_jspath)]
    dest_jspath_arrays = re.findall(array_regex, dest_jspath)
    if len(source_jspath_array_names) != len(dest_jspath_arrays):
        raise ValueError(
            "inconsistent number of arrays found from the output source and destination path in CMA"
        )

    # Get the hierarchy of array size from source_jspath
    array_size_hierarchy = []
    for (source_jspath_array_name, source_jspath_array_index) in zip(source_jspath_array_names, source_jspath_array_indices):
        partial_jspath = source_jspath[:source_jspath_array_index] + source_jspath_array_name
        array_size_hierarchy.append([m.value for m in parse_ext(partial_jspath + '.`len`').find(source_message)])
    print(array_size_hierarchy)









    # Starting from the root,
    #   for the existing nodes in dest_jspath,
    #   make sure the array size matches that from the corresponding source_jspath
    paths = dest_jspath.lstrip('$.').split('.')
    current_item = message
    paths_remaining = paths
    for idx, path in enumerate(paths):
        is_array = False
        if '[' in path:
            path = path.split('[')[0]
            is_array = True
        if path in current_item:
            current_item = current_item[path]
            if is_array:
                # Make sure number of items matches that from the source
                pass #NOTE not implemented yet
        else:
            paths_remaining = paths[idx:]
            break

    # For the remaining non-existing nodes in dest_jspath,
    #   add 
    for idx, path in enumerate(paths_remaining):
        is_array = False
        if '[' in path:
            path = path.split('[')[0]
            is_array = True
        if is_array:
            # 
            pass
        else:
            new_path_dict = {}
            # Add missing key to existing dict
            current_item[path] = new_path_dict
            # Set current item to newly created dict
            current_item = new_path_dict



    if not parse(jspath).find(message):
        paths = jspath.lstrip('$.').split('.')
        current_item = message
        key_not_found = False
        for path in paths:
            m = re.match('^(.*)\[\*\]$', path)
            if m: path = m.groups(0)
            if key_not_found or path not in current_item:
                key_not_found = True
                new_path_dict = {}
                # Add missing key to existing dict
                current_item[path] = new_path_dict
                # Set current item to newly created dict
                current_item = new_path_dict
            else:
                current_item = current_item[path]

    message = deepcopy(message_for_update)
    flag_array_jspath = False
    if not parse(dest_jspath).find(message):
        paths = dest_jspath.lstrip("$.").split(".")
        current_item = message
        key_not_found = False
        for path in paths:
            flag_array = False
            if "[" in path:
                path = path.split("[")[0]
                flag_array = True
                flag_array_jspath = True
            if isinstance(current_item, list):
                current_items = current_item
                for current_item in current_items:
                    if key_not_found or path not in current_item:
                        key_not_found = True
                        if flag_array:
                            new_path_dict = []
                        else:
                            new_path_dict = {}
                        # Add missing key to existing dict
                        current_item[path] = new_path_dict
                        # Set current item to newly created dict
                        current_item = new_path_dict
                    else:
                        current_item = current_item[path]
            else:
                if key_not_found or path not in current_item:
                    key_not_found = True
                    if flag_array:
                        new_path_dict = []
                    else:
                        new_path_dict = {}
                    # Add missing key to existing dict
                    current_item[path] = new_path_dict
                    # Set current item to newly created dict
                    current_item = new_path_dict
                else:
                    current_item = current_item[path]
    if flag_array_jspath:
        # parse(dest_jspath).update(message, value)
        match_data = parse(dest_jspath).find(message)
        for item, v in zip(match_data, value):
            item.full_path.update(message, v)
    else:
        parse(dest_jspath).update(message, value)

    return message
