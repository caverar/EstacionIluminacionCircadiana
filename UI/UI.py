import ECUI
import sys, time

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import uic

from SerialHandler import SerialHandler, TEST_CALLBACK, MULT_CALLBACK

#Ploter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure



class SerialDataThread(QtCore.QThread):

    """
    This class is the thread in charge of serial comunication
    """
    serial_connected = False
    data_signal = QtCore.pyqtSignal(int)
    serial_connected_signal = QtCore.pyqtSignal(bool)
    disconnect_signal = QtCore.pyqtSignal()

    def __init__(self) -> None: 

        QtCore.QThread.__init__(self)
        self.serial_handler = SerialHandler()
        if(self.serial_handler.get_port()):
            self.serial_handler.set_baudrate()
            self.serial_handler.open_port()
            self.serial_handler.synchronize()
            self.serial_connected = True         
            

    def run(self):
        self.serial_connected_signal.emit(self.serial_connected)

        while(True):
            if(self.serial_connected):
                flag = self.serial_handler.working_loop()
                if(flag):
                    #print(self.serial_handler.rx_package)
                    self.data_signal.emit(self.serial_handler.rx_package.sensor1)


    def test_run(self):
        print('Starting thread...')
        count = 0
        while(True):
            self.data_signal.emit(count)
            time.sleep(0.1)
            count=count+1

    @QtCore.pyqtSlot()
    def send_test_callback(self):
        if(self.serial_connected):
            #print("XOR LED")
            self.serial_handler.control_rq(TEST_CALLBACK, 0)

    @QtCore.pyqtSlot()
    def retry_serial(self):
        #print("callback test")
        if not self.serial_connected:
            if(self.serial_handler.get_port()):
                self.serial_handler.set_baudrate()
                self.serial_handler.open_port()
                self.serial_handler.synchronize()
                self.serial_connected = True
            else:
                self.serial_connected = False
            self.serial_connected_signal.emit(self.serial_connected)

    def disconnect(self):
        if self.serial_connected:
            self.serial_handler.close_port()
            self.serial_connected = False
            self.disconnect_signal.emit()

    @QtCore.pyqtSlot(int)
    def send_multiplier_callback(self, val):
        if(self.serial_connected):
            #print("Send multiplier " + str(val))
            #self.send_multiplier_callback = True

            self.serial_handler.control_rq(MULT_CALLBACK, val)


    @QtCore.pyqtSlot()
    def slot_tester(self):
        print("slot_tester test")



class Canvas(FigureCanvas):
    """
    This class is the matplotlib frame to plot data in QT
    """

    def __init__(self, parent = None, width = 3, height = 2, dpi =100):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.ax.grid()
        self.ax.margins(x=0)
        self.arraySize = 100
        #self.xData = np.arange(0,self.arraySize,1)
        self.yData = np.zeros(self.arraySize)
        self.count = 0

    
    def update_plot(self, new_sample):
        #plt.title("Grafica")
        
        if(self.count < self.arraySize):
            self.yData[self.count] = new_sample
            self.count = self.count + 1
        else:
            self.yData = np.roll(self.yData, -1)
            self.yData[99] = new_sample
            
        #print(len(self.yData))
           
        #print(self.xData)
        self.ax.cla()
        line, = self.ax.plot(self.yData ,color = "r", linewidth = 0.5)
        self.draw()
        
        #line.set_ydata(self.yData +24)


class UIWrapper(QtWidgets.QMainWindow):

    """
    This class is the main UI
    """
    serial_connected = False

    def __init__(self) -> None:
        QtWidgets.QMainWindow.__init__(self)

        # UI configuration    

        self.ui = ECUI.Ui_MainWindow()
        self.ui.setupUi(self)
        self.canvas = Canvas(self)
        self.ui.data_plot_layout.addWidget(self.canvas)
        #self.canvas.update_plot(0)
        # self.ui.main_tab,addWidget()
        # Windowsless: Both work
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")

        # self.setWindowFlags(QtCore.Qt.WindowType.CustomizeWindowHint)
        
        self.threads = [None for i in range(3)] # List of threads
        self.connect_threads()
        self.events_assignation()
        self.start_threads()
        

    def events_assignation(self):
        # User no blocking code to assign events:
        
        #test_buttons
        self.ui.mult_button.clicked.connect(self.mult_button_event)
        self.ui.led_button.clicked.connect(self.led_button_event)

        #connect_button
        self.ui.connection_button.clicked.connect(self.connection_button_event)
        self.ui.start_serialization_button.clicked.connect(self.threads[0].slot_tester)
        self.ui.stop_serialization_button.clicked.connect(self.threads[0].slot_tester)
        self.ui.disconnection_button.clicked.connect(self.disconnection_button_event)
    # Events and signal emiters

    def led_button_event(self):
        self.threads[0].send_test_callback()

    def mult_button_event(self):
        self.threads[0].send_multiplier_callback(int(self.ui.mult_data.text()))
    
    def connection_button_event(self):
        self.threads[0].retry_serial()

    def disconnection_button_event(self):
        self.threads[0].disconnect()

    def connect_threads(self):
        self.threads[0] = SerialDataThread()

        # Connect signals
        self.threads[0].data_signal.connect(self.data_receiver)
        self.threads[0].serial_connected_signal.connect(self.serial_connected_status_receiver)
        self.threads[0].disconnect_signal.connect(self.serial_disconnected_receiver)
    
    def start_threads(self):
        
        # start Threads
        self.threads[0].start()

    # Threads's signal receivers (slots):
    @QtCore.pyqtSlot(int)
    def data_receiver(self, val):
        self.ui.test_data_label.display(val)
        self.canvas.update_plot(val)

    @QtCore.pyqtSlot(bool)
    def serial_connected_status_receiver(self, val):
        print("serial_connected_status_receiver: " + str(val))
        if(val):
            self.ui.connection_status. setText("Conexi??n Exitosa")
        else:
            self.ui.connection_status.setText("Conexi??n Fallida")

    @QtCore.pyqtSlot()
    def serial_disconnected_receiver(self):
        self.ui.connection_status. setText("Conexi??n Detenida")


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui_wrapper = UIWrapper()
    ui_wrapper.show()


    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()