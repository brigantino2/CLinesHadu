import re
import sys
import unicodedata
from collections import defaultdict
from random import shuffle

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from tester import CLineTester


try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


def slugify(value):
    """Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """

    value = unicodedata.normalize('NFKD', value).encode(
        'ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


class CLineTestWorkerSignals(QObject):
    """Defines what signals our thread worker will send.

    We just use a
    - finished: to be set with the cline tuple and an error message (empty string if testing was successful)
    - error: in case an Exception is raised
    """

    finished = pyqtSignal(tuple, str)
    error = pyqtSignal(object)


class CLineTestWorker(QRunnable):
    """To test clines are working e use a thread pool with a thread worker (a QRunnable) for each server to test.

    This thread worker performs the server testing using CLineTester, then emits a `finished` signal, that will be
    handled CLinesWindow in the main thread.
    """

    def __init__(self, server_name, port, user, pw, *args, **kwargs):
        super(CLineTestWorker, self).__init__(*args, **kwargs)
        self.server_name = server_name
        self.port = port
        self.user = user
        self.pw = pw
        self.signals = CLineTestWorkerSignals()

    def run(self):
        cline = str("C: %s %s %s %s" % (self.server_name, self.port, self.user, self.pw))

        # Retrieve args/kwargs here; and fire processing using them
        try:
            tester = CLineTester(cline)
            error_msg = tester.test()
        except Exception as e:
            self.signals.error.emit(e)
            error_msg = e.message
        finally:
            self.signals.finished.emit((self.server_name, self.port, self.user, self.pw), error_msg or '')


class CLinesWindow(QtGui.QMainWindow):
    """The GUI in which the user can paste clines, check if they work and get a hadu text.
    """

    # regular expression used to find clines in user pasted text
    CLINE_REGEX = '^[Cc]{1}[:]{1}[ \t]+([^ \t]+)[ \t]+([0-9]+)[ \t]+([^ \t]+)[ \t]+([^ \t]+)'

    # If you want invalid clines to show in the final hadu list, commented or not, set ON_INVALID_CLINES
    # among the following:
    INVALID_CLINES_EXCLUDE = 'exclude'
    INVALID_CLINES_COMMENT = 'comment'
    INVALID_CLINES_DO_NOTHING = 'no'
    ON_INVALID_CLINES = INVALID_CLINES_EXCLUDE

    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.pasted_text = ''
        self.clines = []
        self.invalid_lines = []
        self.hadu_lines = []
        self._clines_textarea = None
        self._c_widget = None
        self._hadu_textarea = None
        self._n_tested = 0
        self.servers_to_test = {}

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

        # PROGRESS BAR
        self.progress_bar = QtGui.QProgressBar(self)
        self.progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.layout.addWidget(self.progress_bar)
        self.progress_bar.hide()

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
        self.button_ok.clicked.connect(self.__next_page)
        self.button_cancel.clicked.connect(self.__prev_page)
        self.layout.addWidget(self.button_box)

        # Current page
        self.page_index = 1

        self.page1()

    def page1(self):
        """This page contains a textarea where the user can paste CLines to be tested and converted.
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
        """Returns a string containing a CLine, stripped of extra spaces and extra characters.

        I.e. '<server name> <port> <user> <pw>'
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

    def generate_checkboxes(self, clines):
        """Generates a list of checkboxes, one for each recognized CLine.

        The label describes the CLine and shows a message telling if testing on that server was successful or not,
        once testing (which is asynchronous) is done.
        """

        # Grouping clines by server name+port: pasted clines might contain mnay entries for the same server+port
        # with different usernames and passwords. We want to keep those entries
        # together.
        clines_grouped = defaultdict(list)
        for server_name, port, user, pw in clines:
            clines_grouped[(server_name, port)].append((user, pw))
        clines_grouped = dict(clines_grouped)

        checkboxes = []

        if clines_grouped:
            i = 1
            for (server_name, port), users_pws in clines_grouped.items():
                # Shuffling each server+port usernames and passwords list. This is intended to add some variability
                # if you copy/paste a list of CLines from websites
                shuffle(users_pws)
                for j, (user, pw) in enumerate(users_pws):

                    checkbox = QtGui.QCheckBox(
                        "%s %s %s %s" % (server_name, port, user, pw),
                        self.stacked_widget
                    )
                    checkboxes.append(checkbox)

                    self.servers_to_test[
                        (server_name, port, user, pw)] = checkbox

                i += 1

        return checkboxes

    def retrieve_clines(self, text):
        """Parses the text pasted in the textarea, looking for valid CLines, stripping whitespaces, comments and
        other garbage.
        """

        clines = []

        for line in text.split('\n'):
            line = self.clean_line(line)

            if line is not None:
                clines.append(line)

        return sorted(
            clines, key=lambda l: ''.join(l)
        )

    def page2(self):
        """List of found CLines, checkboxes to select lines to include.
        """

        self._checkboxes = []
        self.clines = []

        self.setWindowTitle(u"CCCAM - Testing servers")

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

        # Showing the progress bar, disabling the OK button until processing is finished
        self.button_ok.setDisabled(True)
        self.progress_bar.setMaximum(len(self.servers_to_test))
        self.progress_bar.show()
        self.progress_bar.setTextVisible(True)
        self._update_progress_bar()

        self.start_testing()

    def start_testing(self):
        """Tests all servers by using various thread workers (QRunnables) in a thread pool.

        This way testing is done asynchronously, since some servers may take some time to answer, so the UI is
        not blocked until the process is done and we can show a progress bar.

        See:
        https://martinfitzpatrick.name/article/multithreading-pyqt-applications-with-qthreadpool/
        https://nikolak.com/pyqt-threading-tutorial/
        """

        # A thread pool is a thread automatically hadling various tasks.
        self.threadpool = QThreadPool()
        self._n_tested = 0

        for data in self.servers_to_test:
            worker = CLineTestWorker(*data)
            # When each worker is done, `end_testing` is called.
            worker.signals.finished.connect(self.end_testing)

            # Executing the thread worker within the pool.
            self.threadpool.start(worker)

    def _update_progress_bar(self, value=0):
        self.progress_bar.setValue(value)

    def end_testing(self, server_data, error_msg=''):
        """Callback method that handles each thread worker finishing testing, with success or not.

        It updated the progress bar and the checkbox text with a success/failure message .
        """
        self._n_tested += 1
        self._update_progress_bar(self._n_tested)

        checkbox = self.servers_to_test[tuple(server_data)]
        t = checkbox.text()

        if error_msg:
            # Server testing has failed
            checkbox.setChecked(False)
            checkbox.setText("%s  [FAILED: %s]" % (t, error_msg))
        else:
            # SUCCESS!
            checkbox.setChecked(True)
            checkbox.setText("%s  [OK]" % t)

        if self._n_tested >= len(self.servers_to_test):
            # All servers have been tested, enabling the ok button.
            self.button_ok.setDisabled(False)

    def cline_to_hadu_string(self, n, cline, invalid=False):
        """Converts a cline tuple into a hadu plugin string.
        e.g.
        """

        comment = ''
        if invalid:
            if self.ON_INVALID_CLINES == self.INVALID_CLINES_EXCLUDE:
                return
            elif self.ON_INVALID_CLINES == self.INVALID_CLINES_COMMENT:
                comment = ';'

        text = "{comment}[Serv_{servname}]\n{comment}Server=CCCam:{server}"\
               ":{port}:0:{user}:{pw}\n"
        server, port, user, pw = cline

        self.hadu_lines.append(text.format(
            servname='%s_%s' % (n, slugify(server)), server=server, port=port,
            user=user, pw=pw, comment=comment
        ))

    def page3(self):
        """Final page, showing valid clines in had format.
        """
        self.setWindowTitle('CCCAM - Hadu lines')

        self.stacked_widget.removeWidget(self._c_widget)

        for i, checkbox in enumerate(self._checkboxes):
            self.cline_to_hadu_string(i, self.clines[i], invalid=not checkbox.isChecked())

        self._hadu_textarea = QtGui.QPlainTextEdit(self)
        self._hadu_textarea.setGeometry(QtCore.QRect(10, 20, 461, 451))
        self._hadu_textarea.setObjectName(_fromUtf8("Hadu lines"))
        self._hadu_textarea.setReadOnly(True)
        self._hadu_textarea.insertPlainText('\n'.join(self.hadu_lines))
        self._hadu_textarea.moveCursor(QtGui.QTextCursor.End)
        self._hadu_textarea.selectAll()

        self.stacked_widget.insertWidget(0, self._hadu_textarea)
        self.stacked_widget.setCurrentIndex(0)

    def __change_page(self):
        self.button_ok.show()
        self.button_ok.setDisabled(False)
        self.button_cancel.show()
        self.button_cancel.setDisabled(False)
        self.progress_bar.hide()

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
