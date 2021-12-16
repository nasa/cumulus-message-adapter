from copy import deepcopy
from pprint import pprint
from jsonpath_ng import parse


def assign_json_path_value(source_message, jspath, value):
    """
    * Assign (update or insert) a value to message based on jsonpath.
    * Create the keys if jspath doesn't already exist in the message. In this case, we
    * support 'simple' jsonpath like $.path1.path2.path3....
    * @param {dict} source_message The message to be updated
    * @param {string} jspath JSON path string
    * @param {*} value Value to update to
    * @return {*} updated message
    """
    message = deepcopy(source_message)
    if jspath[0]=='[':
        jspath = jspath.lstrip('[').rstrip(']')
    flag_array_jspath = False
    if not parse(jspath).find(message):
        paths = jspath.lstrip('$.').split('.')
        current_item = message
        key_not_found = False
        for path in paths:
            flag_array = False
            if '[' in path:
                path = path.split('[')[0]
                flag_array = True
                flag_array_jspath = True
            print(path)
            pprint(type(current_item))
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
        #parse(jspath).update(message, value)
        match_data = parse(jspath).find(message)
        for item,v in zip(match_data,value):
            item.full_path.update(message,v)
    else:
        parse(jspath).update(message, value)
    return message
