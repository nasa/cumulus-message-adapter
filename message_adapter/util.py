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


def __sanitize_path(path):
    m = re.match('^(.*)\[\*\]$', path)
    return m.groups()[0] if m else path
    
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

    # Find where source_jspath and dest_jspath begin to diverge
    source_paths = source_jspath.lstrip('$.').split('.')
    dest_paths = dest_jspath.lstrip('$.').split('.')
    idx_diverged = len(source_paths)
    for idx, (source_path, dest_path) in enumerate(zip(source_paths, dest_paths)):
        if __sanitize_path(source_path) != __sanitize_path(dest_path):
            idx_diverged = idx
            break

    # Copy items from source to destination
    # before their jsonpath begin to diverge
    for idx in range(idx_diverged):
        pass # Don't need to do anything?

    # 
    for idx in range(idx_diverged, len(dest_paths)):



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
    for (source_jspath_array_name, source_jspath_array_index) in zip(source_jspath_array_names, source_jspath_array_indices):
        partial_jspath = source_jspath[:source_jspath_array_index] + source_jspath_array_name
        ns = [m.value for m in parse_ext(partial_jspath + '.`len`').find(source_message)]


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

    '''
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
    '''

    return message
