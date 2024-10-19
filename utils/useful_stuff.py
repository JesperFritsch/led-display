

class DotDict(dict):
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError()

    def __setattr__(self, attr, value):
        self[attr] = value

    def __delattr__(self, attr):
        try:
            del self[attr]
        except KeyError:
            raise AttributeError

    def read_dict(self, other_dict):
        for k, v in other_dict.items():
            if isinstance(v, dict):
                v = DotDict(v)
            self[k] = v