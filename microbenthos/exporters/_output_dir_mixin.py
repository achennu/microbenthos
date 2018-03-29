import os


class OutputDirMixin(object):
    def __init__(self,
                 output_dir = None,
                 **kwargs
                 ):
        self._output_dir_ = output_dir or '.'
        super(OutputDirMixin, self).__init__(**kwargs)

    @property
    def output_dir(self):
        """
        The output directory path set for the exporter
        """
        return self._output_dir_

    @output_dir.setter
    def output_dir(self, path):
        if os.path.isdir(path):
            self._output_dir_ = path
            self.logger.debug('output_dir set: {}'.format(self.output_dir))
        else:
            raise ValueError('Output directory does not exist')
