from dataclasses import dataclass

import serial.tools.list_ports
import serial

from crc import CrcCalculator, Configuration, Crc16

RETREIVE_DATA_RQ = 1<<8
RETREIVE_DATA_ACK = 1<<14
RETREIVE_DATA_STATE = 1<<13

TEST_CALLBACK = 1
MULT_CALLBACK = 1<<1

@dataclass
class Package():
    sample: int = 0
    sensor1: int = 0
    sensor2: int = 0
    sensor3: int = 0
    sensor4: int = 0
    sensor5: int = 0
    rq_sample: int = 0
    control_signals: int = 0
    crc16: int = 0
    
    def __bytes__(self)->bytes:
        return (self.sample.to_bytes(4,'big') +
                self.sensor1.to_bytes(4,'big') +
                self.sensor2.to_bytes(4,'big') +
                self.sensor3.to_bytes(4,'big') +
                self.sensor4.to_bytes(4,'big') +
                self.sensor5.to_bytes(4,'big') +
                self.rq_sample.to_bytes(4,'big') +
                self.control_signals.to_bytes(2,'big') +
                self.crc16.to_bytes(2,'big'))


class SerialHandler():

    port_name = ""
    serial_instance = serial.Serial()

    # True if te last trasfer was a failed retreive_data_rq
    rx_error_flag = False

    past_sample = 0

    retreive_counter = 0
    
    control_rq_flag = False


    def __init__(self) -> None:
        self.get_port()
        self.rx_package = Package()
        #self.tx_control_package = Package(0,0,0,0,0,0,0,TEST_CALLBACK,0)
        self.tx_control_package = Package()
        self.tx_error_package = Package(0,1,2,3,4,5,0,RETREIVE_DATA_RQ,0)

        self.lose_data_package = Package(0,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff)
        # width = 16
        # poly = 0x01021s
        # init_value = 0x00
        # final_xor_value = 0x00
        # reverse_input = False
        # reverse_output = False
        # crc_configuration = Configuration(width, poly, init_value, final_xor_value, reverse_input, reverse_output)

        # use_table = True
        self.crc_calculator = CrcCalculator(Crc16.CCITT, True)



    def set_baudrate(self, bauds: str = 115200):
        self.serial_instance.baudrate = bauds

    def get_port(self)->str:
        """
        get the port name
        """

        ports = serial.tools.list_ports.comports()
        port_list = []
            
        for one_port in ports:
            port_list.append(str(one_port))
        self.port_name = (str(port_list[0])).split(" ")[0]
        print(self.port_name)

    def open_port(self):
        self.serial_instance.port = self.port_name
        self.serial_instance.open()

    def synchronize(self):
        #Clear input Buffer
        self.serial_instance.reset_input_buffer()
        sync = True
        data = ['00' for i in range(5)]
        while(sync):
            data[0] = data[1]
            data[1] = data[2]
            data[2] = data[3]
            data[3] = (self.serial_instance.read()).hex()            
            #"E" = 45 "N" = 4e "D" = 44
            if(data[0] == '45' and  data[1] == '4e' and data[2] == '44' and 
              data[3] == '00'):
                sync = False

    def read_package(self)->Package:
        """
        CRC calculation, unpack data and retreive corrupt data. 

        if 3 or more CRC errors are detected in a row, the system is resynchronized
        """
        data = self.serial_instance.read_until('END\0',36)
        if(len(data) == 36):
            array=list(map(str, (data .hex(':').split(':')) ))
            #print(array)
            self.rx_package.sample = int(array[0]+array[1]+array[2]+array[3],base=16)
            self.rx_package.sensor1 = int(array[4]+array[5]+array[6]+array[7],base=16)
            self.rx_package.sensor2 = int(array[8]+array[9]+array[10]+array[11],base=16)
            self.rx_package.sensor3 = int(array[12]+array[13]+array[14]+array[15],base=16)
            self.rx_package.sensor4 = int(array[16]+array[17]+array[18]+array[19],base=16)
            self.rx_package.sensor5 = int(array[20]+array[21]+array[22]+array[23],base=16)
            self.rx_package.rq_sample = int(array[24]+array[25]+array[26]+array[27],base=16)


            self.rx_package.control_signals = int(array[28]+array[29], base=16)
            self.rx_package.crc16 = int(array[30]+array[31], base =16)

            self.rx_CRC = self.crc_calculator.calculate_checksum(data[:32])

            #print(data[:32].hex(" "))
            #print("CRC: "+ str(self.rx_CRC))

            

            if self.rx_CRC != 0:

                if self.retreive_counter >= 3:
                    self.synchronize()
                    self.retreive_counter = 1
                    self.retreive_rq(self.past_sample)
                else:
                    self.retreive_counter += 1
                    self.retreive_rq(self.rx_package.sample)

                return False

            elif self.rx_package.control_signals == RETREIVE_DATA_ACK:
                self.retreive_counter = 0
                self.rx_error_flag = True
                self.past_sample = self.rx_package.sample
                return True

            else:
                self.retreive_counter = 0
                self.rx_error_flag = False
                self.past_sample = self.rx_package.sample
                return True

        elif( 36 >len(data) > 0):
            self.synchronize()
            self.retreive_counter = 1
            self.retreive_rq(self.past_sample)
            return False
    
    def retreive_rq(self, sample: int):
        self.lose_data_package.rq_sample = sample
        self.write_package(self.lose_data_package.rq_sample)




    def write_package(self, data: Package):        
        #print(bytes(data))
        self.serial_instance.write(bytes(data))

    def read_data_test(self):
        while(1):
            data = self.serial_instance.read_until('END\0',36)    #Funciona!!!            
            print(data.hex(':'))
            print(data)

    def control_rq(self, control_signal, data):
        self.tx_control_package.control_signals = control_signal
        if(control_signal == MULT_CALLBACK):
            self.tx_control_package.sensor1 = data
        #self.control_rq_flag = True

    def working_loop(self)->bool:
        """        
        This function must be executed continuously on a thread.        """

        flag = self.read_package()
        if(self.tx_control_package.control_signals != 0):
            self.write_package(self.tx_control_package)
            self.tx_control_package.control_signals = 0


        return flag
        
def main():
    tx_data = Package(0,0,0,0,0,0,1,TEST_CALLBACK,0)
    
    serial_handler = SerialHandler()    
    #print(serial_handler.port_name)
    serial_handler.set_baudrate()
    serial_handler.open_port()
    serial_handler.synchronize()

    #serial_handler.write_package(tx_data)
    # while(True):
    #     serial_handler.read_package()
    #     print(serial_handler.rx_package)

def crc_test():

    crc_calculator = CrcCalculator(Crc16.CCITT, True)
    print(crc_calculator.calculate_checksum(bytes([1,2,3,4])))

def default_working():
    serial_handler = SerialHandler()
    serial_handler.set_baudrate()
    serial_handler.open_port()
    serial_handler.synchronize()
    for i in range(100):
        if(i == 10):
           serial_handler.control_rq(TEST_CALLBACK)
           print("Control Signal")
        flag = serial_handler.working_loop()
        if(flag):
            print(serial_handler.rx_package)

def retrieving_data_test():
    tx_data = Package(0,1,2,3,4,5,0,RETREIVE_DATA_RQ,0)
    
    serial_handler = SerialHandler()    
    #print(serial_handler.port_name)
    serial_handler.set_baudrate()
    serial_handler.open_port()
    serial_handler.synchronize()

    
    
    for i in range(20):
        serial_handler.read_package()
        print(serial_handler.rx_package)
        if(i == 4):
            tx_data.rq_sample = serial_handler.rx_package.sample-5
            serial_handler.write_package(tx_data)
        if(i == 5):
            tx_data.rq_sample = serial_handler.rx_package.sample-2
            serial_handler.write_package(tx_data)

if __name__ == '__main__':
    default_working()