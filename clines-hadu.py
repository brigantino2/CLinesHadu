import sys
import re
import time
import unicodedata
from collections import defaultdict
from random import shuffle

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QThread
from qtasync import CallbackEvent

from tester import ClineTester

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


# https://stackoverflow.com/questions/24689800/async-like-pattern-in-pyqt-or-cleaner-background-call-pattern


class CLineTestThread(QThread):   # NOT WORKING?
    """ Runs a function in a thread, and alerts the parent when done.

    Uses a custom QEvent to alert the main thread of completion.

    """
    def __init__(self, parent, func, end_callback, *args, **kwargs):
        super(CLineTestThread, self).__init__(parent)
        self.func = func
        self.end_callback = end_callback
        self.args = args
        self.kwargs = kwargs
        self.start()

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            print "ERROR: ", e
            result = e
        finally:
            CallbackEvent.post_to(self.parent(), self.end_callback, result)


class CLinesWindow(QtGui.QMainWindow):

    # regular expression used to find clines in user pasted text
    CLINE_REGEX = '^[Cc]{1}[:]{1}[ \t]+([^ \t]+)[ \t]+([0-9]+)[ \t]+([^ \t]+)[ \t]+([^ \t]+)'
    TEST_DELAY = 0.5

    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.pasted_text = ''
        self.clines = []
        self.invalid_lines = []
        self.hadu_lines = []
        self._clines_textarea = None
        self._c_widget = None
        self._hadu_textarea = None

        # Drawing window stuff
        self.resize(640, 480)

        self.layout = QtGui.QVBoxLayout()

        self.stacked_widget = QtGui.QStackedWidget()

        self.scroll_area = QtGui.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.layout.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.stacked_widget)

        self.widget = QtGui.QWidget()
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)

        # BUTTONS
        self.button_box = QtGui.QDialogButtonBox(self)
        self.button_box.setGeometry(QtCore.QRect(10, 480, 461, 32))
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(
            QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok
        )
        self.button_box.setObjectName(_fromUtf8("OkCancelButtonBox"))
        self.button_ok, self.button_cancel = self.button_box.buttons()
        self.button_cancel.setText('Back')
        self.button_cancel.setDisabled(True)
        self.button_ok.connect(
            self.button_box,
            QtCore.SIGNAL(_fromUtf8("accepted()")),
            self.__next_page
        )
        self.button_cancel.connect(
            self.button_box,
            QtCore.SIGNAL(_fromUtf8("rejected()")),
            self.__prev_page
        )
        self.layout.addWidget(self.button_box)

        # Current page
        self.page_index = 1

        self.page1()

    def page1(self):
        """This page contains a textarea where the user can paste
        CLines to be tested and converted.
        """

        self.setWindowTitle(u"CCCAM - Paste CLines")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("icons/icon.png"), QtGui.QIcon.Normal,
                       QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        if self._c_widget:
            self.stacked_widget.removeWidget(self._c_widget)

        # Drawing the textatrea where you paste your CLines
        self._clines_textarea = QtGui.QPlainTextEdit(self)
        self._clines_textarea.setGeometry(QtCore.QRect(10, 20, 661, 451))
        self._clines_textarea.setObjectName(_fromUtf8("CCCAM lines"))

        if self.pasted_text:
            # Filling the textarea with the previously pasted CLines (if
            # we are coming back from page 2)
            self._clines_textarea.insertPlainText(self.pasted_text)

        self.stacked_widget.insertWidget(0, self._clines_textarea)

    def clean_line(self, line):
        """Returns a string containing a CLine, stripped of extra spaces
        and extra characters, i.e. '<server name> <port> <user> <pw>'
        """
        try:
            line = unicode(line).strip()
        except UnicodeEncodeError:
            self.invalid_lines.append(line)
            return None
        match = re.findall(self.CLINE_REGEX, line)
        if match:
            return list(match[0])  # "server_name, port, user, pw"
        # no valid CLine found in this string
        return None

    def test_cline(self, server_name, port, user, pw, checkbox=None):
        cline = str("C: %s %s %s %s" % (server_name, port, user, pw))
        is_valid, error_msg = ClineTester(cline).test()

        t = checkbox.text()
        if is_valid:
            checkbox.setChecked(True)
            checkbox.setText("%s  [OK]" % t)
        else:
            checkbox.setChecked(False)
            checkbox.setText("%s  [FAIL: %s]" % (t, error_msg))

        return is_valid

    def test_cline_done(self, result):
        # NOT USED
        pass

    def retrieve_clines(self, text):
        clines = []

        for line in text.split('\n'):
            line = self.clean_line(line)

            if line is not None:
                clines.append(line)

        return sorted(
            clines, key=lambda l: ''.join(l)
        )

    def generate_checkboxes(self, clines):
        clines_grouped = defaultdict(list)
        for server_name, port, user, pw in clines:
            clines_grouped[(server_name, port)].append((user, pw))
        clines_grouped = dict(clines_grouped)

        checkboxes = []

        if clines_grouped:
            i = 1
            for (server_name, port), users_pws in clines_grouped.items():
                shuffle(users_pws)
                for j, (user, pw) in enumerate(users_pws):

                    checkbox = QtGui.QCheckBox(
                        "%s %s %s %s" % (server_name, port, user, pw),
                        self.stacked_widget
                    )
                    checkboxes.append(checkbox)
                    time.sleep(self.TEST_DELAY)
                    CLineTestThread(
                        self, self.test_cline, self.test_cline_done,
                        server_name, port, user, pw, checkbox
                    )
                i += 1

        return checkboxes

    def page2(self):
        """List of found CLines, checkboxes to select lines to include.
        """
        self._checkboxes = []
        self.clines = []

        self.setWindowTitle(u"CCCAM - Found servers")

        if self._clines_textarea:
            self.stacked_widget.removeWidget(self._clines_textarea)
        if self._c_widget:
            self.stacked_widget.removeWidget(self._c_widget)
        if self._hadu_textarea:
            self.stacked_widget.removeWidget(self._hadu_textarea)

        self.pasted_text = self._clines_textarea.toPlainText()

        self._c_widget = QtGui.QWidget(self)

        grid = QtGui.QGridLayout(self._c_widget)

        self.clines = self.retrieve_clines(self.pasted_text)

        self._checkboxes = self.generate_checkboxes(self.clines)

        for i, checkbox in enumerate(self._checkboxes):
            grid.addWidget(checkbox, i, 0)
            # https://stackoverflow.com/questions/11073972/pyqt-set-qlabel-image-from-url
            # grid.addWidget(icon, i, 1)

        self._c_widget.setLayout(grid)

        self.stacked_widget.insertWidget(0, self._c_widget)

    def convert_line(self, n, cLine, commented=False):
        text = "{comment}[Serv_{servname}]\n{comment}Server=CCCam:{server}"\
               ":{port}:0:{user}:{pw}\n{comment}Active=1\n"
        comment = ';' if commented else ''
        server, port, user, pw = cLine
        self.hadu_lines.append(text.format(
            servname='%s_%s' % (n, slugify(server)), server=server, port=port,
            user=user, pw=pw, comment=comment
        ))

    def page3(self):
        self.setWindowTitle('CCCAM - Hadu lines')

        self.stacked_widget.removeWidget(self._c_widget)

        for i, checkbox in enumerate(self._checkboxes):
            self.convert_line(i, self.clines[i],
                              commented=not checkbox.isChecked())

        self._hadu_textarea = QtGui.QPlainTextEdit(self)
        self._hadu_textarea.setGeometry(QtCore.QRect(10, 20, 461, 451))
        self._hadu_textarea.setObjectName(_fromUtf8("Hadu lines"))
        self._hadu_textarea.setReadOnly(True)
        self._hadu_textarea.insertPlainText('\n'.join(self.hadu_lines))
        self._hadu_textarea.moveCursor(QtGui.QTextCursor.End)
        self._hadu_textarea.selectAll()

        self.stacked_widget.insertWidget(0, self._hadu_textarea)

    def __change_page(self):
        self.button_ok.show()
        self.button_ok.setDisabled(False)
        self.button_cancel.show()
        self.button_cancel.setDisabled(False)

        if self.page_index == 1:
            self.button_cancel.setDisabled(True)

        if self.page_index >= 3:
            self.button_ok.setDisabled(True)

        page = getattr(self, 'page%s' % self.page_index)

        page()

    def __next_page(self):
        self.page_index += 1
        if self.page_index > 3:
            self.destroy()

        self.__change_page()

    def __prev_page(self):
        self.page_index -= 1
        if self.page_index < 1:
            self.page_index = 1

        self.__change_page()


if __name__ == "__main__":
        app = QtGui.QApplication(sys.argv)
        clines_app = CLinesWindow()
        clines_app.show()
        sys.exit(app.exec_())
