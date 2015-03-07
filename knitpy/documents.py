from __future__ import absolute_import, unicode_literals

import os

# Basic things from IPython
from IPython.config.configurable import LoggingConfigurable
from IPython.utils.traitlets import Bool, Unicode, CaselessStrEnum

from .utils import is_iterable, is_string

TEXT, OUTPUT, CODE = range(3)
VALID_OUTPUT_FORMATS = ["html", "docx"]
DEFAULT_OUTPUT_FORMAT = "html"

class MarkdownOutputDocument(LoggingConfigurable):

    output_debug = Bool(False, config=True,
        help="""Whether to print outputs to the (debug) log""")
    # TODO: put loglevel to debug of this is True...

    code_startmarker = Unicode("``` {}", config=True,
                               help="Start of a code block, with language placeholder and "
                                    "without linefeed")
    code_endmarker = Unicode("```", config=True, help="end of a code block, without linefeed")
    output_startmarker = Unicode("```", config=True,
                                 help="Start of a output block, without linefeed")
    output_endmarker = Unicode("```", config=True, help="End of a output block, without linefeed")

    export_format = CaselessStrEnum(VALID_OUTPUT_FORMATS,
        default_value=DEFAULT_OUTPUT_FORMAT,
        config=False,
        help="""The export format to be used."""
    )


    def __init__(self, fileoutputs, export_format="html", **kwargs):
        super(MarkdownOutputDocument,self).__init__(**kwargs)
        self._fileoutputs = fileoutputs
        if export_format.endswith("_document"):
            export_format = export_format[:-9]
        self.export_format = export_format
        self._output = []

    @property
    def outputdir(self):
        if not os.path.isdir(self._fileoutputs):
            os.mkdir(self._fileoutputs)
            self.log.info("Support files will be in %s", os.path.join(self._fileoutputs, ''))

        return self._fileoutputs

    @property
    def plotdir(self):
        plotdir_name = "figure-%s" % self.export_format
        plotdir = os.path.join(self.outputdir, plotdir_name)
        if not os.path.isdir(plotdir):
            os.mkdir(plotdir)
        return plotdir

    @property
    def content(self):
        self.flush()
        return "".join(self._output)

    # The caching system is needed to make fusing together same "type" of content possible
    # -> code inputs without output should go to the same block
    _last_content = None
    _cache_text = []
    _cache_code = []
    _cache_code_language = None
    _cache_output = []

    def flush(self):
        if self._cache_text:
            self._output.extend(self._cache_text)
            self._cache_text = []
        if self._cache_code:
            self._output.append(self.code_startmarker.format(self._cache_code_language))
            self._output.append("\n")
            self._output.extend(self._cache_code)
            self._output.append(self.code_endmarker)
            self._output.append("\n")
            self._cache_code = []
            self._cache_code_language = None
        if self._cache_output:
            self._output.append(self.output_startmarker)
            self._output.append("\n")
            self._output.extend(self._cache_output)
            self._output.append(self.output_endmarker)
            self._output.append("\n")
            self._cache_output = []

    def _add_to_cache(self, content, content_type):
        if content_type != self._last_content:
            self.flush()
        if content_type == CODE:
            cache = self._cache_code
            self._last_content = CODE
        elif content_type == OUTPUT:
            cache = self._cache_output
            self._last_content = OUTPUT
        else:
            cache = self._cache_text
            self._last_content = TEXT

        if is_string(content):
            cache.append(content)
        elif is_iterable(content):
            cache.extend(content)
        else:
            cache.append(content)

    def add_code(self, code, language="python"):
        if language != self._cache_code_language:
            self.flush()
        self._cache_code_language = language
        self._add_to_cache(code, CODE)

    def add_output(self, output):
        self._add_to_cache(output, OUTPUT)

    def add_text(self, text):
        self._add_to_cache(text, TEXT)

    def convert(self):
        from IPython.nbconvert.utils.pandoc import pandoc
        format = "markdown" \
                 "+autolink_bare_uris" \
                 "+ascii_identifiers" \
                 "+tex_math_single_backslash-implicit_figures" \
                 "+fenced_code_attributes"
        extra = ["--smart", # typographically correct output (curly quotes, etc)
                 "--email-obfuscation", "none", #do not obfuscation email names with javascript
                 "--self-contained", # include img/scripts as data urls
                 "--standalone", # html with header + footer
                 "--section-divs",
                 ]
        exported = pandoc("".join(self._output), format, to=self.export_format, extra_args=extra )
        return exported