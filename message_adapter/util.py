from copy import deepcopy
import pydash as py_
from .CMATypes import CumulusMessage, GenericCumulusSubObject




def assign_json_path_value(
    source_message: CumulusMessage,
    jspath: str,
    value: GenericCumulusSubObject
) -> CumulusMessage:
    """
    * Assign (update or insert) a value to message based on jsonpath.
    * Create the keys if jspath doesn't already exist in the message.
    * In this case, we support 'simple' jsonpath
    * like $.path1.path2.path3....
    * @param {dict} source_message The message to be updated
    * @param {string} jspath JSON path string
    * @param {*} value Value to update to
    * @return {*} updated message
    """
    message = deepcopy(source_message)
    py_.set_(message, jspath.lstrip('$.'), value)
    return message
