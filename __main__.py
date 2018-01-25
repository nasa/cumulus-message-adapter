#!/usr/bin/env python
import json
import sys

from message import message

if __name__ == '__main__':
  functionName = sys.argv[1]
  transformer = message.message()
  exitCode = 1
  allInput = json.loads(raw_input())
  event = allInput['event']
  try:
    if (functionName == 'loadRemoteEvent'):
      result = transformer.loadRemoteEvent(event)
    elif (functionName == 'loadNestedEvent'):
      context = allInput['context']
      result = transformer.loadNestedEvent(event, context)
    elif (functionName == 'createNextEvent'):
      handlerResponse = allInput['handler_response']
      messageConfig = allInput['message_config']
      result = transformer.createNextEvent(handlerResponse, event, messageConfig)

    if (result is not None and len(result) > 0):
      sys.stdout.write(json.dumps(result))
      sys.stdout.flush()
      exitCode = 0
  except LookupError as le:
    sys.stderr.write("Lookup error: " + str(le))
  except:
    sys.stderr.write("Unexpected error:"+ str(sys.exc_info()[0])+ ". " + str(sys.exc_info()[1]))
  sys.exit(exitCode)
