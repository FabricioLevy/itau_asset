def pretty(d, indent=0):
   for key, value in d.items():
      print('\t' * indent + str(key))
      if isinstance(value, dict):
         pretty(value, indent+1)
      else:
         print('\t' * (indent+1) + str(value))

def rec_access(d, keys, value):
    aux = d
    for key_i, key in enumerate(keys):
        if key_i == len(keys) - 1:
            aux[key] = value
        elif key in aux.keys():
            aux = aux[key]
        else:
            aux[key] = {}
            aux = aux[key]

a = {
    1: {
        5: {

        }
    }
}
b = {}
rec_access(a, [1, 6, 1213], 10)
pretty(a, 0)
