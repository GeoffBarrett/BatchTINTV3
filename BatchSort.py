import functools, sys, json, datetime, os, time
from PIL import Image
from PyQt4 import QtCore, QtGui
from core.utils import center, background, Worker
from core.settings import Settings_Window
from core.smtpSettings import SmtpSettings, AddExpter, add_Expter
from core.KlustaFunctions import klusta, check_klusta_ready, folder_ready, find_tetrodes, session_analyzable

_author_ = "Geoffrey Barrett"  # defines myself as the author

Large_Font = ("Verdana", 12)  # defines two fonts for different purposes (might not be used
Small_Font = ("Verdana", 8)


class Window(QtGui.QWidget):  # defines the window class (main window)

    def __init__(self):  # initializes the main window
        super(Window, self).__init__()
        # self.setGeometry(50, 50, 500, 300)
        background(self)  # acquires some features from the background function we defined earlier
        self.setWindowTitle("BatchTINT - Main Window")  # sets the title of the window
        self.current_session = ''
        self.current_subdirectory = ''
        self.LogAppend = Communicate()
        self.LogAppend.myGUI_signal_str.connect(self.AppendLog)

        self.LogError = Communicate()
        self.LogError.myGUI_signal_str.connect(self.raiseError)

        self.RemoveQueueItem = Communicate()
        self.RemoveQueueItem.myGUI_signal_str.connect(self.takeTopLevel)

        self.RemoveSessionItem = Communicate()
        self.RemoveSessionItem.myGUI_signal_str.connect(self.takeChild)

        self.RemoveSessionData = Communicate()
        self.RemoveSessionData.myGUI_signal_str.connect(self.takeChildData)

        self.RemoveChildItem = Communicate()
        self.RemoveChildItem.myGUI_signal_QTreeWidgetItem.connect(self.removeChild)

        self.adding_session = True
        self.reordering_queue = False

        self.choice = ''
        self.home()  # runs the home function

    def home(self):  # defines the home function (the main window)
        
        try:  # attempts to open previous directory catches error if file not found
            # No saved directory's need to create file
            with open(self.directory_settings, 'r+') as filename:  # opens the defined file
                directory_data = json.load(filename)  # loads the directory data from file
                if os.path.exists(directory_data['directory']):
                    current_directory_name = directory_data['directory']  # defines the data
                else:
                    current_directory_name = 'No Directory Currently Chosen!'  # states that no directory was chosen

        except FileNotFoundError:  # runs if file not found
            with open(self.directory_settings, 'w') as filename:  # opens a file
                current_directory_name = 'No Directory Currently Chosen!'  # states that no directory was chosen
                directory_data = {'directory': current_directory_name}  # creates a dictionary
                json.dump(directory_data, filename)  # writes the dictionary to the file

        # ---------------logo --------------------------------

        cumc_logo = QtGui.QLabel(self)  # defining the logo image
        logo_fname = os.path.join(self.IMG_DIR, "BatchKlustaLogo.png")  # defining logo pathname
        im2 = Image.open(logo_fname)  # opening the logo with PIL
        logowidth, logoheight = im2.size  # acquiring the logo width/height
        logo_pix = QtGui.QPixmap(logo_fname)  # getting the pixmap
        cumc_logo.setPixmap(logo_pix)  # setting the pixmap
        cumc_logo.setGeometry(0, 0, logowidth, logoheight)  # setting the geometry

        # ------buttons ------------------------------------------
        quitbtn = QtGui.QPushButton('Quit', self)  # making a quit button
        quitbtn.clicked.connect(self.close_app)  # defining the quit button functionality (once pressed)
        quitbtn.setShortcut("Ctrl+Q")  # creates shortcut for the quit button
        quitbtn.setToolTip('Click to quit Batch-Tint!')

        self.setbtn = QtGui.QPushButton('Klusta Settings')  # Creates the settings pushbutton
        self.setbtn.setToolTip('Define the settings that KlustaKwik will use.')

        self.klustabtn = QtGui.QPushButton('Run', self)  # creates the batch-klusta pushbutton
        self.klustabtn.setToolTip('Click to perform batch analysis via Tint and KlustaKwik!')

        self.smtpbtn = QtGui.QPushButton('SMTP Settings', self)
        self.smtpbtn.setToolTip("Click to change the SMTP settings for e-mail notifications.")

        self.choose_dir = QtGui.QPushButton('Choose Directory', self)  # creates the choose directory pushbutton

        self.cur_dir = QtGui.QLineEdit()  # creates a line edit to display the chosen directory (current)
        self.cur_dir.setText(current_directory_name)  # sets the text to the current directory
        self.cur_dir.setAlignment(QtCore.Qt.AlignHCenter)  # centers the text
        self.cur_dir.setToolTip('The current directory that Batch-Tint will analyze.')

        # defines an attribute to exchange info between classes/modules
        self.current_directory_name = current_directory_name

        # defines the button functionality once pressed
        self.klustabtn.clicked.connect(lambda: self.run(self.current_directory_name))

        # ------------------------------------ check box  ------------------------------------------------
        self.nonbatch_check = QtGui.QCheckBox('Non-Batch?')
        self.nonbatch_check.setToolTip("Check this if you don't want to run batch. This means you will choose\n"
                                       "the folder that directly contains all the session files (.set, .pos, .N, etc.).")
        self.nonbatch = 0

        self.silent_cb = QtGui.QCheckBox('Run Silently')
        self.silent_cb.setToolTip("Check if you want Tint to run in the background.")

        # ---------------- queue widgets --------------------------------------------------
        self.directory_queue = QtGui.QTreeWidget()
        self.directory_queue.headerItem().setText(0, "Axona Sessions:")
        self.directory_queue.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        directory_queue_label = QtGui.QLabel('Queue: ')

        self.up_btn = QtGui.QPushButton("Move Up", self)
        self.up_btn.setToolTip("Clcik this button to move selected directories up on the queue!")
        self.up_btn.clicked.connect(lambda: self.moveQueue('up'))

        self.down_btn = QtGui.QPushButton("Move Down", self)
        self.down_btn.setToolTip("Clcik this button to move selected directories down on the queue!")
        self.down_btn.clicked.connect(lambda: self.moveQueue('down'))

        queue_btn_layout = QtGui.QVBoxLayout()
        queue_btn_layout.addWidget(self.up_btn)
        queue_btn_layout.addWidget(self.down_btn)

        queue_layout = QtGui.QVBoxLayout()
        queue_layout.addWidget(directory_queue_label)
        queue_layout.addWidget(self.directory_queue)

        queue_and_btn_layout = QtGui.QHBoxLayout()
        queue_and_btn_layout.addLayout(queue_layout)
        queue_and_btn_layout.addLayout(queue_btn_layout)

        # ------------------------ multithreading widgets -------------------------------------

        self.Multithread_cb = QtGui.QCheckBox('Multiprocessing')
        self.Multithread_cb.setToolTip('Check if you want to run multiple tetrodes simultaneously')

        core_num_l = QtGui.QLabel('Cores (#):')
        core_num_l.setToolTip('Generally the number of processes that multiprocessing should use is \n'
                              'equal to the number of cores your computer has.')

        self.core_num = QtGui.QLineEdit()

        Multithread_l = QtGui.QLabel('Simultaneous Tetrodes (#):')
        Multithread_l.setToolTip('Input the number of tetrodes you want to analyze simultaneously')

        self.Multithread = QtGui.QLineEdit()

        Multi_layout = QtGui.QHBoxLayout()

        # for order in [self.Multithread_cb, core_num_l, self.core_num, Multithread_l, self.Multithread]:
        for order in [Multithread_l, self.Multithread]:
            if 'Layout' in order.__str__():
                Multi_layout.addLayout(order)
                # Multi_layout.addStretch(1)
            else:
                Multi_layout.addWidget(order, 0, QtCore.Qt.AlignCenter)
                # Multi_layout.addWidget(order)
                # Multi_layout.addStretch(1)

        checkbox_layout = QtGui.QHBoxLayout()
        checkbox_layout.addStretch(1)
        checkbox_layout.addWidget(self.nonbatch_check)
        checkbox_layout.addStretch(1)
        checkbox_layout.addWidget(self.silent_cb)
        checkbox_layout.addStretch(1)
        checkbox_layout.addLayout(Multi_layout)
        checkbox_layout.addStretch(1)

        try:
            with open(self.settings_fname, 'r+') as filename:
                settings = json.load(filename)
                self.core_num.setText(str(settings['Cores']))
                self.Multithread.setText(str(settings['NumThreads']))
                if settings['Silent'] == 1:
                    self.silent_cb.toggle()
                if settings['Multi'] == 1:
                    self.Multithread_cb.toggle()
                if settings['Multi'] == 0:
                    self.core_num.setDisabled(1)
                if settings['nonbatch'] == 1:
                    self.nonbatch_check.toggle

        except FileNotFoundError:
            self.silent_cb.toggle()
            self.core_num.setDisabled(1)
            self.core_num.setText('4')
            self.Multithread.setText('1')

        # ------------- Log Box -------------------------
        self.Log = QtGui.QTextEdit()
        log_label = QtGui.QLabel('Log: ')

        log_lay = QtGui.QVBoxLayout()
        log_lay.addWidget(log_label, 0, QtCore.Qt.AlignTop)
        log_lay.addWidget(self.Log)

        # ------------------------------------ version information -------------------------------------------------
        # finds the modification date of the program
        try:
            mod_date = time.ctime(os.path.getmtime(__file__))
        except:
            mod_date = time.ctime(os.path.getmtime(os.path.join(self.PROJECT_DIR, "BatchSort.exe")))

        vers_label = QtGui.QLabel("BatchTINT V3.0 - Last Updated: " + mod_date)  # creates a label with that information

        # ------------------- page layout ----------------------------------------
        layout = QtGui.QVBoxLayout()  # setting the layout

        layout1 = QtGui.QHBoxLayout()  # setting layout for the directory options
        layout1.addWidget(self.choose_dir)  # adding widgets to the first tab
        layout1.addWidget(self.cur_dir)

        btn_order = [self.klustabtn, self.setbtn, self.smtpbtn, quitbtn]  # defining button order (left to right)
        btn_layout = QtGui.QHBoxLayout()  # creating a widget to align the buttons
        for butn in btn_order:  # adds the buttons in the proper order
            btn_layout.addWidget(butn)

        layout_order = [cumc_logo, layout1, checkbox_layout, queue_and_btn_layout, log_lay, btn_layout]

        layout.addStretch(1)  # adds the widgets/layouts according to the order
        for order in layout_order:
            if 'Layout' in order.__str__():
                layout.addLayout(order)
                layout.addStretch(1)
            else:
                layout.addWidget(order, 0, QtCore.Qt.AlignCenter)
                layout.addStretch(1)

        layout.addStretch(1)  # adds stretch to put the version info at the bottom
        layout.addWidget(vers_label)  # adds the date modification/version number
        self.setLayout(layout)  # sets the widget to the one we defined

        center(self)  # centers the widget on the screen

        self.show()  # shows the widget

        if self.current_directory_name != 'No Directory Currently Chosen!':
            # starting adding any existing sessions in a different thread

            self.RepeatAddSessionsThread = QtCore.QThread()
            self.RepeatAddSessionsThread.start()

            self.RepeatAddSessionsWorker = Worker(RepeatAddSessions, self)
            self.RepeatAddSessionsWorker.moveToThread(self.RepeatAddSessionsThread)
            self.RepeatAddSessionsWorker.start.emit("start")

    def run(self, directory):  # function that runs klustakwik

        """This method runs when the Batch-TINT button is pressed on the GUI,
        and commences the analysis"""
        '''
        self.BatchTintThread = threading.Thread(target=BatchTint(self, directory))
        self.BatchTintThread.daemon = True
        self.BatchTintThread.start()
        '''
        self.batch_tint = True
        self.klustabtn.setText('Stop')
        self.klustabtn.setToolTip('Click to stop Batch-Tint.')  # defining the tool tip for the start button
        self.klustabtn.clicked.disconnect()
        self.klustabtn.clicked.connect(self.stopBatch)

        self.BatchTintThread = QtCore.QThread()
        self.BatchTintThread.start()

        self.BatchTintWorker = Worker(BatchTint, self, directory)
        self.BatchTintWorker.moveToThread(self.BatchTintThread)
        self.BatchTintWorker.start.emit("start")

    def close_app(self):
        # pop up window that asks if you really want to exit the app ------------------------------------------------

        choice = QtGui.QMessageBox.question(self, "Quitting BatchTINT",
                                            "Do you really want to exit?",
                                            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if choice == QtGui.QMessageBox.Yes:
            sys.exit()  # tells the app to quit
        else:
            pass

    def raiseError(self, error_val):
        '''raises an error window given certain errors from an emitted signal'''

        if 'ManyFet' in error_val:
            self.choice = QtGui.QMessageBox.question(self, "No Chosen Directory: BatchTINT",
                                                     "You have chosen more than four features,\n"
                                                     "clustering will take a long time.\n"
                                                     "Do you realy want to continue?",
                                                 QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        elif 'NoDir' in error_val:
            self.choice = QtGui.QMessageBox.question(self, "No Chosen Directory: BatchTINT",
                                                   "You have not chosen a directory,\n"
                                                   "please choose one to continue!",
                                                     QtGui.QMessageBox.Ok)

        elif 'GoogleDir' in error_val:
            self.choice = QtGui.QMessageBox.question(self, "Google Drive Directory: BatchTINT",
                                                       "You have not chosen a directory within Google Drive,\n"
                                                       "be aware that during testing we have experienced\n"
                                                       "permissions errors while using Google Drive directories\n"
                                                       "that would result in BatchTINTV2 not being able to move\n"
                                                       "the files to the Processed folder (and stopping the GUI),\n"
                                                       "do you want to continue?",
                                                       QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        elif 'NoSet' in error_val:
            self.choice = QtGui.QMessageBox.question(self, "No .Set Files!",
                                                     "You have chosen a directory that has no .Set files!\n"
                                                     "Please choose a different directory!",
                                                     QtGui.QMessageBox.Ok)

        elif 'InvDirBatch':
            self.choice = QtGui.QMessageBox.question(self, "Invalid Directory!",
                                                     "In 'Batch Mode' you need to choose a directory\n"
                                                     "with subdirectories that contain all your Tint\n"
                                                     "files. Press Abort and choose new file, or if you\n"
                                                     "plan on adding folders to the chosen directory press\n"
                                                     "continue.",
                                                     QtGui.QMessageBox.Abort | QtGui.QMessageBox.Ok)
        elif 'InvDirNonBatch':
            self.choice = QtGui.QMessageBox.question(self, "Invalid Directory!",
                                                     "In 'Non-Batch Mode' you need to choose a directory\n"
                                                     "that contain all your Tint files.\n",
                                                     QtGui.QMessageBox.Ok)

    def AppendLog(self, message):
        '''A function that will append the Log field of the main window (mainly
        used as a slot for a custom pyqt signal)'''
        self.Log.append(message)

    def stopBatch(self):
        # self.klustabtn.clicked.disconnect()
        self.klustabtn.clicked.connect(lambda: self.run(self.current_directory_name))
        self.BatchTintThread.quit()
        # self.RepeatAddSessionsThread.quit()
        self.batch_tint = False
        self.klustabtn.setText('Run')
        self.klustabtn.setToolTip(
            'Click to perform batch analysis via Tint and KlustaKwik!')  # defining the tool tip for the start button

    def moveQueue(self, direction):
        '''This method is not threaded'''
        # get all the queue items

        while self.adding_session:
            if self.reordering_queue:
                self.reordering_queue = False
            time.sleep(0.1)

        time.sleep(0.1)
        self.reordering_queue = True

        item_count = self.directory_queue.topLevelItemCount()
        queue_items = {}
        for item_index in range(item_count):
            queue_items[item_index] = self.directory_queue.topLevelItem(item_index)

        # get selected options and their locations
        selected_items = self.directory_queue.selectedItems()
        selected_items_copy = []
        [selected_items_copy.append(item.clone()) for item in selected_items]

        add_to_new_queue = list(queue_items.values())

        #add_to_new_queue = self.directory_queue.items
        #for i in range(len(selected_items)):
        #    selected_items[i] = selected_items[i].clone()

        if not selected_items:
            # skips when there are no items selected
            return

        new_queue_order = {}

        # find if consecutive indices from 0 on are selected as these won't move any further up

        indices = find_keys(queue_items, selected_items)
        # non_selected_indices = sorted([index for index in range(item_count) if index not in indices])
        consecutive_indices = find_consec(indices)
        # this will spit a list of lists, these nested lists will have consecutive indices within them
        # i.e. if indices 0, 1 and 3 were chosen it would have [[0, 1], [3]]

        if 'up' in direction:
            # first add the selected items to their new spots
            for consecutive in consecutive_indices:
                if 0 in consecutive:
                    # these items can't move up any further
                    for index in consecutive:
                        new_item = queue_items[index].clone()
                        # new_item.setSelected(True)
                        new_queue_order[index] = new_item

                else:
                    for index in consecutive:
                        # move these up the list (decrease in index value since 0 is the top of the list)
                        new_item = queue_items[index].clone()
                        # new_item.setSelected(True)
                        new_queue_order[index-1] = new_item

            for key, val in new_queue_order.items():
                for index, item in enumerate(add_to_new_queue):
                    if val.data(0, 0) == item.data(0, 0):
                        add_to_new_queue.remove(item)  # remove item from the list
                        break

            _ = list(new_queue_order.keys())  # a list of already moved items

            # place the unplaced items that aren't moving
            for static_index, static_value in queue_items.items():
                # print(static_value.data(0,0))
                # place the unplaced items
                if static_index in _:
                    continue

                for queue_item in new_queue_order.values():
                    not_in_reordered = True
                    if static_value.data(0, 0) == queue_item.data(0, 0):
                        # don't re-add the one that is going to be moved
                        not_in_reordered = False
                        break

                if not_in_reordered:
                    # item = queue_items[non_selected_indices.pop()]
                    for value in add_to_new_queue:
                        if static_value.data(0, 0) == value.data(0, 0):
                            add_to_new_queue.remove(value)  # remove item from the list
                            break

                    new_queue_order[static_index] = static_value.clone()

        elif 'down' in direction:
            # first add the selected items to their new spots
            for consecutive in consecutive_indices:
                if (item_count-1) in consecutive:
                    # these items can't move down any further
                    for index in consecutive:
                        new_item = queue_items[index].clone()
                        # new_item.setSelected(True)
                        new_queue_order[index] = new_item
                else:
                    for index in consecutive:
                        # move these down the list (increase in index value since 0 is the top of the list)
                        new_item = queue_items[index].clone()
                        # new_item.setSelected(True)
                        new_queue_order[index + 1] = new_item

            for key, val in new_queue_order.items():
                for index, item in enumerate(add_to_new_queue):
                    if val.data(0, 0) == item.data(0, 0):
                        add_to_new_queue.remove(item)
                        break

            _ = list(new_queue_order.keys())  # a list of already moved items

            # place the unplaced items that aren't moving
            for static_index, static_value in queue_items.items():
                if static_index in _:
                    continue

                for queue_item in new_queue_order.values():
                    not_in_reordered = True
                    if static_value.data(0, 0) == queue_item.data(0, 0):
                        # don't re-add the one that is going to be moved
                        not_in_reordered = False
                        break

                if not_in_reordered:
                    # item = queue_items[non_selected_indices.pop()]
                    for value in add_to_new_queue:
                        if static_value.data(0, 0) == value.data(0, 0):
                            add_to_new_queue.remove(value)  # remove item from the list
                            break

                    new_queue_order[static_index] = static_value.clone()

        # add the remaining items

        indices_needed = [index for index in range(item_count) if index not in list(new_queue_order.keys())]
        for index, displaced_item in enumerate(add_to_new_queue):
            new_queue_order[indices_needed[index]] = displaced_item.clone()

        self.directory_queue.clear()  # clears the list

        for key, value in sorted(new_queue_order.items()):
            # for item in selected_items:
            #     if item.data(0, 0) == value.data(0, 0):
            #         value.setSelected(True)

            self.directory_queue.addTopLevelItem(value)

        # reselect the items
        iterator = QtGui.QTreeWidgetItemIterator(self.directory_queue)
        while iterator.value():
            for selected_item in selected_items_copy:
                item = iterator.value()
                if item.data(0, 0) == selected_item.data(0, 0):
                    item.setSelected(True)
                    break
            iterator += 1
        # for index in range(item_count):
        #   self.directory_queue.takeTopLevelItem(0)
        self.reordering_queue = False

    def takeTopLevel(self, item_count):
        item_count = int(item_count)
        self.directory_queue.takeTopLevelItem(item_count)
        self.top_level_taken = True

    def setChild(self, child_count):
        self.child_session = self.directory_item.child(int(child_count))
        self.child_set = True

    def takeChild(self, child_count):
        self.child_session = self.directory_item.takeChild(int(child_count))
        self.child_taken = True
        # return child_session

    def takeChildData(self, child_count):
        self.child_session = self.directory_item.takeChild(int(child_count)).data(0, 0)
        self.child_data_taken = True

    def removeChild(self, QTreeWidgetItem):
        root = self.directory_queue.invisibleRootItem()
        (QTreeWidgetItem.parent() or root).removeChild(QTreeWidgetItem)
        self.child_removed = True


def find_keys(my_dictionary, value):
    """finds a key for a given value of a dictionary"""
    key = []
    if not isinstance(value, list):
        value = [value]
    [key.append(list(my_dictionary.keys())[list(my_dictionary.values()).index(val)]) for val in value]
    return key


def find_consec(data):
    '''finds the consecutive numbers and outputs as a list'''
    consecutive_values = []  # a list for the output
    current_consecutive = [data[0]]

    if len(data) == 1:
        return [[data[0]]]

    for index in range(1, len(data)):

        if data[index] == data[index - 1] + 1:
            current_consecutive.append(data[index])

            if index == len(data) - 1:
                consecutive_values.append(current_consecutive)

        else:
            consecutive_values.append(current_consecutive)
            current_consecutive = [data[index]]

            if index == len(data) - 1:
                consecutive_values.append(current_consecutive)
    return consecutive_values


class Choose_Dir(QtGui.QWidget):

    def __init__(self):
        super(Choose_Dir, self).__init__()
        background(self)
        # deskW, deskH = background.Background(self)
        width = self.deskW / 5
        height = self.deskH / 5
        self.setGeometry(0, 0, width, height)

        with open(self.directory_settings, 'r+') as filename:
            directory_data = json.load(filename)
            current_directory_name = directory_data['directory']
            if not os.path.exists(current_directory_name):
                current_directory_name = 'No Directory Currently Chosen!'

        self.setWindowTitle("BatchTINT - Choose Directory")

        # ---------------- defining instructions -----------------
        instr = QtGui.QLabel("For Batch Processing: choose the directory that contains subdirectories where these\n"
                             "subdirectories contain all the session files (.set, .pos, .eeg, .N, etc.). Batch-Tint\n"
                             "will iterate through each sub-directory and each session within those sub-directories.\n\n"
                             "For Non-Batch: choose the directory that directly contains the contain all the session\n"
                             "files (.set, .pos, .eeg, .N, etc.) and Batch-Tint will iterate through each session.\n")

        # ----------------- buttons ----------------------------
        self.dirbtn = QtGui.QPushButton('Choose Directory', self)
        self.dirbtn.setToolTip('Click to choose a directory!')
        # dirbtn.clicked.connect(self.new_dir)

        cur_dir_t = QtGui.QLabel('Current Directory:')  # the label saying Current Directory
        self.cur_dir_e = QtGui.QLineEdit() # the label that states the current directory
        self.cur_dir_e.setText(current_directory_name)
        self.cur_dir_e.setAlignment(QtCore.Qt.AlignHCenter)
        self.current_directory_name = current_directory_name

        self.backbtn = QtGui.QPushButton('Back', self)
        self.applybtn = QtGui.QPushButton('Apply', self)


        # ---------------- save checkbox -----------------------
        self.save_cb = QtGui.QCheckBox('Leave Checked To Save Directory', self)
        self.save_cb.toggle()
        self.save_cb.stateChanged.connect(self.save_dir)

        # ----------------- setting layout -----------------------

        layout_dir = QtGui.QVBoxLayout()

        layout_h1 = QtGui.QHBoxLayout()
        layout_h1.addWidget(cur_dir_t)
        layout_h1.addWidget(self.cur_dir_e)

        layout_h2 = QtGui.QHBoxLayout()
        layout_h2.addWidget(self.save_cb)

        btn_layout = QtGui.QHBoxLayout()
        btn_order = [self.dirbtn, self.applybtn, self.backbtn]

        # btn_layout.addStretch(1)
        for butn in btn_order:
            btn_layout.addWidget(butn)
            # btn_layout.addStretch(1)

        layout_order = [instr, layout_h1, self.save_cb, btn_layout]

        for order in layout_order:
            if 'Layout' in order.__str__():
                layout_dir.addLayout(order)
            else:
                layout_dir.addWidget(order, 0, QtCore.Qt.AlignCenter)

        self.setLayout(layout_dir)

        center(self)
        # self.show()

    def save_dir(self, state):
        self.current_directory_name = str(self.cur_dir_e.text())
        if state == QtCore.Qt.Checked:  # do this if the Check Box is checked
            # print('checked')
            with open(self.directory_settings, 'w') as filename:
                directory_data = {'directory': self.current_directory_name}
                json.dump(directory_data, filename)
        else:
            # print('unchecked')
            pass

    def apply_dir(self, main):
        self.current_directory_name = str(self.cur_dir_e.text())
        self.save_cb.checkState()

        if self.save_cb.isChecked():  # do this if the Check Box is checked
            self.save_dir(self.save_cb.checkState())
        else:
            pass

        main.directory_queue.clear()
        main.cur_dir.setText(self.current_directory_name)
        main.current_directory_name = self.current_directory_name

        self.backbtn.animateClick()


@QtCore.pyqtSlot()
def raise_window(new_window, old_window):
    """ raise the current window"""
    if 'Choose' in str(new_window):
        new_window.raise_()
        new_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        new_window.show()
        time.sleep(0.1)

    elif "Choose" in str(old_window):
        time.sleep(0.1)
        old_window.hide()
        return
    else:
        new_window.raise_()
        new_window.show()
        time.sleep(0.1)
        old_window.hide()


@QtCore.pyqtSlot()
def cancel_window(new_window, old_window):
    """ raise the current window"""
    new_window.raise_()
    new_window.show()
    time.sleep(0.1)
    old_window.hide()

    if 'SmtpSettings' in str(new_window) and 'AddExpter' in str(old_window): # needs to clear the text files
        old_window.expter_edit.setText('')
        old_window.email_edit.setText('')


def new_directory(self, main):
    """This method will look open a dialog and prompt the user to select a directory,"""
    current_directory_name = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
    self.current_directory_name = current_directory_name
    self.cur_dir_e.setText(current_directory_name)


def addSessions(self):

    while self.reordering_queue:
        # pauses add Sessions when the individual is reordering
        time.sleep(0.1)

    current_directory = self.current_directory_name
    if self.nonbatch == 0:
        # finds the sub directories within the chosen directory
        sub_directories = [d for d in os.listdir(self.current_directory_name)
                           if os.path.isdir(os.path.join(self.current_directory_name, d)) and
                           d not in ['Processed', 'Converted']]  # finds the subdirectories within each folder

    else:
        # current_directory = os.path.dirname(self.current_directory_name)
        current_directory = os.path.dirname(current_directory)
        sub_directories = [os.path.basename(self.current_directory_name)]

    # find items already in the queue
    added_directories = []

    # iterating through queue items
    iterator = QtGui.QTreeWidgetItemIterator(self.directory_queue)
    while iterator.value():
        directory_item = iterator.value()

        # check if directory still exists
        if not os.path.exists(os.path.join(current_directory, directory_item.data(0, 0))) and \
                        '.set' not in directory_item.data(0, 0):
            # then remove from the list since it doesn't exist anymore
            root = self.directory_queue.invisibleRootItem()
            for child_index in range(root.childCount()):
                if root.child(child_index) == directory_item:
                    self.RemoveChildItem.myGUI_signal_QTreeWidgetItem.emit(directory_item)
                    # root.removeChild(directory_item)
        else:
            added_directories.append(directory_item.data(0, 0))

        iterator += 1

    for directory in sub_directories:

        try:
            set_files = [file for file in os.listdir(os.path.join(current_directory, directory))
                         if '.set' in file and
                         not os.path.isdir(os.path.join(current_directory, directory, file))]
        except FileNotFoundError:
            return

        if set_files:
            if directory in added_directories:
                # add sessions that aren't already added

                # find the treewidget item
                iterator = QtGui.QTreeWidgetItemIterator(self.directory_queue)
                while iterator.value():
                    directory_item = iterator.value()
                    if directory_item.data(0, 0) == directory:
                        break
                    iterator += 1

                # find added sessions
                added_sessions = []
                try:
                    iterator = QtGui.QTreeWidgetItemIterator(directory_item)
                except UnboundLocalError:
                    # print('hello')
                    return
                except RuntimeError:
                    return

                while iterator.value():
                    session_item = iterator.value()
                    added_sessions.append(session_item.data(0, 0))
                    iterator += 1

                for set_file in set_files:
                    tetrodes = find_tetrodes(set_file, os.path.join(current_directory,
                                                                    directory))  # find all the tetrodes for that set file

                    # check if all the tetrodes within that set file have been analyzed
                    analyzable = session_analyzable(os.path.join(current_directory, directory),
                                                      set_file, tetrodes)

                    if analyzable:
                        # add session
                        if set_file not in added_sessions and set_file != self.current_session:
                            session_item = QtGui.QTreeWidgetItem()
                            session_item.setText(0, set_file)
                            directory_item.addChild(session_item)
                    else:
                        pass

            else:

                '''
                try:
                    ready_to_add = folder_ready(self, os.path.join(current_directory, directory))
                except FileNotFoundError:
                    return
                # check if it's still downloading

                if not ready_to_add:
                    return
                '''
                # add all the sessions within this directory
                directory_item = QtGui.QTreeWidgetItem()
                directory_item.setText(0, directory)

                if set_files:
                    for set_file in set_files:
                        if set_file == self.current_session:
                            continue

                        tetrodes = find_tetrodes(set_file, os.path.join(current_directory,
                                                                        directory))  # find all the tetrodes for that set file

                        # check if all the tetrodes within that set file have been analyzed
                        analyzable = session_analyzable(os.path.join(current_directory, directory),
                                                          set_file, tetrodes)

                        if analyzable:
                            # add session
                            session_item = QtGui.QTreeWidgetItem()
                            session_item.setText(0, set_file)
                            directory_item.addChild(session_item)

                            self.directory_queue.addTopLevelItem(directory_item)
                else:
                    pass
                    #self.choice = ''
                    #self.LogError.myGUI_signal_str.emit('NoSet')
                    #while self.choice == '':
                    #    time.sleep(0.5)


def silent(self, state):
    with open(self.settings_fname, 'r+') as filename:
        settings = json.load(filename)
        if state == True:
            settings['Silent'] = 1
        else:
            settings['Silent'] = 0
    with open(self.settings_fname, 'w') as filename:
        json.dump(settings, filename)


class Communicate(QtCore.QObject):
    '''A custom pyqtsignal so that errors and popups can be called from the threads
    to the main window'''
    myGUI_signal_str = QtCore.pyqtSignal(str)
    myGUI_signal_QTreeWidgetItem = QtCore.pyqtSignal(QtGui.QTreeWidgetItem)


def Multi(self, state):
    with open(self.settings_fname, 'r+') as filename:
        settings = json.load(filename)
        if state == True:
            settings['Multi'] = 1
            self.core_num.setEnabled(1)
        else:
            settings['Multi'] = 0
            self.core_num.setDisabled(1)
    with open(self.settings_fname, 'w') as filename:
        json.dump(settings, filename)


def nonbatch(self, state):
    self.directory_queue.clear()

    with open(self.settings_fname, 'r+') as filename:
        settings = json.load(filename)
        if state == True:
            settings['nonbatch'] = 1
            self.nonbatch = 1
        else:
            settings['nonbatch'] = 0
            self.nonbatch = 0
    with open(self.settings_fname, 'w') as filename:
        json.dump(settings, filename)


def BatchTint(main_window, directory):
    # ------- making a function that runs the entire GUI ----------
    '''
    def __init__(self, main_window, directory):
        QtCore.QThread.__init__(self)
        self.main_window = main_window
        self.directory = directory

    def __del__(self):
        self.wait()

    def run(self):
    '''

    # checks if the settings are appropriate to run analysis
    klusta_ready = check_klusta_ready(main_window, directory)

    if klusta_ready:

        #addSessions(main_window)

        main_window.LogAppend.myGUI_signal_str.emit(
            '[%s %s]: Analyzing the following directory: %s!' % (str(datetime.datetime.now().date()),
                                                                 str(datetime.datetime.now().time())[
                                                                 :8], directory))

        if main_window.nonbatch == 0:
            # message that shows how many files were found
            main_window.LogAppend.myGUI_signal_str.emit(
                '[%s %s]: Found %d sub-directories in the directory!' % (str(datetime.datetime.now().date()),
                                                               str(datetime.datetime.now().time())[
                                                               :8], main_window.directory_queue.topLevelItemCount()))

        else:
            directory = os.path.dirname(directory)

        if main_window.directory_queue.topLevelItemCount() == 0:
            # main_window.BatchTintThread.quit()
            # main_window.AddSessionsThread.quit()
            if main_window.nonbatch == 1:
                main_window.choice = ''
                main_window.LogError.myGUI_signal_str.emit('InvDirNonBatch')
                while main_window.choice == '':
                    time.sleep(0.2)
                main_window.stopBatch()
                return
            else:
                main_window.choice = ''
                main_window.LogError.myGUI_signal_str.emit('InvDirBatch')
                while main_window.choice == '':
                    time.sleep(0.2)

                if main_window.choice == QtGui.QMessageBox.Abort:
                    main_window.stopBatch()
                    return

        # ----------- cycle through each file and find the tetrode files ------------------------------------------
        # for sub_directory in sub_directories:  # finding all the folders within the directory

        while main_window.batch_tint:

            #addSessions(main_window)

            main_window.directory_item = main_window.directory_queue.topLevelItem(0)

            if not main_window.directory_item:
                continue
            else:
                main_window.current_subdirectory = main_window.directory_item.data(0, 0)

                # check if the directory exists, if not, remove it

                if not os.path.exists(os.path.join(directory, main_window.current_subdirectory)):
                    main_window.top_level_taken = False
                    main_window.RemoveQueueItem.myGUI_signal_str.emit(str(0))
                    while not main_window.top_level_taken:
                        time.sleep(0.1)
                    # main_window.directory_queue.takeTopLevelItem(0)
                    continue

            while main_window.directory_item.childCount() != 0:

                # set_file = []
                # for child_count in range(main_window.directory_item.childCount()):
                #     set_file.append(main_window.directory_item.child(child_count).data(0, 0))
                main_window.current_session = main_window.directory_item.child(0).data(0, 0)
                main_window.child_data_taken = False
                main_window.RemoveSessionData.myGUI_signal_str.emit(str(0))
                while not main_window.child_data_taken:
                    time.sleep(0.1)
                # main_window.directory_item.takeChild(0).data(0, 0)

                sub_directory = main_window.directory_item.data(0, 0)

                directory_ready = False

                main_window.LogAppend.myGUI_signal_str.emit(
                    '[%s %s]: Checking if the following directory is ready to analyze: %s!' % (
                        str(datetime.datetime.now().date()),
                        str(datetime.datetime.now().time())[
                        :8], str(sub_directory)))

                while not directory_ready:
                    directory_ready = folder_ready(main_window, os.path.join(directory, sub_directory))

                if main_window.directory_item.childCount() == 0:
                    main_window.top_level_taken = False
                    main_window.RemoveQueueItem.myGUI_signal_str.emit(str(0))
                    while not main_window.top_level_taken:
                        time.sleep(0.1)
                    # main_window.directory_queue.takeTopLevelItem(0)

                try:
                    # adding the .rhd files to a list of session_files

                    # set_file = [file for file in os.listdir(dir_new) if '.set' in file]  # finds the set file

                    # if not set_file:  # if there is no set file it will return as an empty list
                    #     # message saying no .set file
                    #     main_window.LogAppend.myGUI_signal_str.emit(
                    #         '[%s %s]: The following folder contains no analyzable \'.set\' files: %s' % (
                    #             str(datetime.datetime.now().date()),
                    #             str(datetime.datetime.now().time())[
                    #             :8], str(sub_directory)))
                    #     continue

                    # runs the function that will perform the klusta'ing
                    if not os.path.exists(os.path.join(directory, sub_directory)):
                        main_window.top_level_taken = False
                        main_window.RemoveQueueItem.myGUI_signal_str.emit(str(0))
                        while not main_window.top_level_taken:
                            time.sleep(0.1)
                        # main_window.directory_queue.takeTopLevelItem(0)
                        continue
                    else:
                        klusta(main_window, sub_directory, directory)

                except NotADirectoryError:
                    # if the file is not a directory it prints this message
                    main_window.LogAppend.myGUI_signal_str.emit(
                        '[%s %s]: %s is not a directory!' % (
                            str(datetime.datetime.now().date()),
                            str(datetime.datetime.now().time())[
                            :8], str(sub_directory)))
                    continue


def RepeatAddSessions(main_window):
    try:
        main_window.adding_session = True
        addSessions(main_window)
        main_window.adding_session = False
    except FileNotFoundError:
        pass
    except RuntimeError:
        pass

    while True:
        #time.sleep(0.5)
        try:
            main_window.adding_session = True
            time.sleep(0.1)
            addSessions(main_window)
            main_window.adding_session = False
            time.sleep(0.1)
        except FileNotFoundError:
            pass
        except RuntimeError:
            pass


def run():
    app = QtGui.QApplication(sys.argv)

    main_w = Window()  # calling the main window
    choose_dir_w = Choose_Dir()  # calling the Choose Directory Window
    settings_w = Settings_Window()  # calling the settings window
    smtp_setting_w = SmtpSettings()  # calling the smtp settings window
    add_exper = AddExpter()

    add_exper.addbtn.clicked.connect(lambda: add_Expter(add_exper, smtp_setting_w))
    # synchs the current directory on the main window
    choose_dir_w.current_directory_name = main_w.current_directory_name

    main_w.raise_()  # making the main window on top

    add_exper.cancelbtn.clicked.connect(lambda: cancel_window(smtp_setting_w, add_exper))
    add_exper.backbtn.clicked.connect(lambda: raise_window(smtp_setting_w, add_exper))

    smtp_setting_w.addbtn.clicked.connect(lambda: raise_window(add_exper, smtp_setting_w))

    main_w.silent_cb.stateChanged.connect(lambda: silent(main_w, main_w.silent_cb.isChecked()))
    main_w.Multithread_cb.stateChanged.connect(lambda: Multi(main_w, main_w.Multithread_cb.isChecked()))
    main_w.nonbatch_check.stateChanged.connect(lambda: nonbatch(main_w, main_w.nonbatch_check.isChecked()))
    # brings the directory window to the foreground
    main_w.choose_dir.clicked.connect(lambda: raise_window(choose_dir_w,main_w))
    # main_w.choose_dir.clicked.connect(lambda: raise_window(choose_dir_w))

    # brings the main window to the foreground
    choose_dir_w.backbtn.clicked.connect(lambda: raise_window(main_w, choose_dir_w))
    choose_dir_w.applybtn.clicked.connect(lambda: choose_dir_w.apply_dir(main_w))
    # choose_dir_w.backbtn.clicked.connect(lambda: raise_window(main_w))  # brings the main window to the foreground

    main_w.setbtn.clicked.connect(lambda: raise_window(settings_w, main_w))
    # main_w.setbtn.clicked.connect(lambda: raise_window(settings_w))

    main_w.smtpbtn.clicked.connect(lambda: raise_window(smtp_setting_w, main_w))

    smtp_setting_w.backbtn.clicked.connect(lambda: raise_window(main_w, smtp_setting_w))

    settings_w.backbtn.clicked.connect(lambda: raise_window(main_w, settings_w))
    # settings_w.backbtn.clicked.connect(lambda: raise_window(main_w))

    settings_w.backbtn2.clicked.connect(lambda: raise_window(main_w, settings_w))
    # settings_w.backbtn2.clicked.connect(lambda: raise_window(main_w))

    choose_dir_w.dirbtn.clicked.connect(lambda: new_directory(choose_dir_w, main_w))  # prompts the user to choose a directory
    # choose_dir_w.dirbtn.clicked.connect(lambda: new_directory(choose_dir_w))  # prompts the user to choose a directory

    sys.exit(app.exec_())  # prevents the window from immediately exiting out

if __name__ == "__main__":
    run()  # the command that calls run()
