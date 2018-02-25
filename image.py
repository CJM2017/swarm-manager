class Image:
    def __init__(self, props):
        self.repo = props[0]
        self.tag = props[1]
        self.imageId = props[2]
        self.created = "{}{}{}".format( props[3], props[4], props[5])
        self.size = props[6]


