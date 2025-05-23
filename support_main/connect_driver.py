import os
import socket
import time
import path
from support_main.lib_main import load_data_csv, edit_csv_tab
import math
import numpy as np
from pymodbus.client import ModbusSerialClient as ModbusClient    # Thư viện Modbus để giao tiếp với thiết bị qua giao thức Modbus
import numpy as np  # Thư viện tính toán số học
import time  # Thư viện thời gian
import threading

path_phan_mem = path.path_phan_mem
path_admin = path_phan_mem + "/setting/admin_window.csv"
if os.name == "nt":
    print("Hệ điều hành là Windows")
    # Đọc file cài đặt cho Windows
    path_admin = path_phan_mem + "/setting/admin_window.csv"
elif os.name == "posix":
    print("Hệ điều hành là Ubuntu (Linux)")
    # Đọc file cài đặt cho Ubuntu
    path_admin = path_phan_mem + "/setting/admin_ubuntu.csv"
data_admin = edit_csv_tab.load_all_stt(path_admin)
com = "COM5"
bause = 115200
distance_max = 100
angle_line = 60
# [['connect_plc', '192.168.0.10'], 
# ['dung', 'WR MR100 0'], ['tien', 'WR MR100 1'], ['lui', 'WR MR101 1'], ['trai', 'WR MR102 1'], ['phai', 'WR MR103 1'], [], [], [], [], [], []]
for i in range(0,len(data_admin)):
    if len(data_admin[i]) > 1:
        if data_admin[i][0] == "cong_driver":
            com = data_admin[i][1]
            bause = int(float(data_admin[i][2]))
        if data_admin[i][0] == "distance_max":
            distance_max = int(float(data_admin[i][1]))
        if data_admin[i][0] == "angle_line":
            angle_line = int(float(data_admin[i][1]))


print(com, bause, distance_max, angle_line)




class sent_data_driver:
    def __init__(self):
        self.com = com
        self.bause = bause
            
        self.close = 0

        self.vt_phai = 0
        self.vt_trai = 0

        self.vt_phai_sent = 0
        self.vt_trai_sent = 0
        self.sent_data_driver = 0
        self.thread_on = 0

        self.distance_max = distance_max
        self.angle_line = angle_line

        self.on_setup = 0

        self.quay_trai = 0
        self.quay_phai = 0


        # Khởi tạo đối tượng điều khiển
        self.client = ModbusClient(port=self.com, baudrate=self.bause, timeout=2, parity='N', stopbits=1, bytesize=8)
        self.connect = True
        self.unit_id = 1  # Đặt ID thiết bị Modbus

        self.ID = 1  # Đặt ID của thiết bị Modbus

        self.kp = 5  # Hệ số P (Proportional)
        self.ki = 3  # Hệ số I (Integral)
        self.kd = 0.3  # Hệ số D (Derivative)
        self.previous_error = 0.0  # Sai số trước đó
        self.integral = 0.0  # Tích phân của sai số

        ######################
        ## Register Address ##
        ######################
        ## Common
        self.CONTROL_REG = 0x200E  # Thanh ghi điều khiển
        self.OPR_MODE = 0x200D  # Thanh ghi chế độ hoạt động
        self.L_ACL_TIME = 0x2080  # Thời gian tăng tốc bánh trái
        self.R_ACL_TIME = 0x2081  # Thời gian tăng tốc bánh phải
        self.L_DCL_TIME = 0x2082  # Thời gian giảm tốc bánh trái
        self.R_DCL_TIME = 0x2083  # Thời gian giảm tốc bánh phải

        ## Velocity control
        self.L_CMD_RPM = 0x2088  # Tốc độ đặt cho bánh trái (RPM)
        self.R_CMD_RPM = 0x2089  # Tốc độ đặt cho bánh phải (RPM)
        self.L_FB_RPM = 0x20AB  # Tốc độ phản hồi bánh trái (RPM)
        self.R_FB_RPM = 0x20AC  # Tốc độ phản hồi bánh phải (RPM)

        ## Position control
        self.POS_CONTROL_TYPE = 0x200F  # Loại điều khiển vị trí

        self.L_MAX_RPM_POS = 0x208E  # Tốc độ tối đa khi điều khiển vị trí bánh trái
        self.R_MAX_RPM_POS = 0x208F  # Tốc độ tối đa khi điều khiển vị trí bánh phải

        self.L_CMD_REL_POS_HI = 0x208A  # Thanh ghi vị trí tương đối cao của bánh trái
        self.L_CMD_REL_POS_LO = 0x208B  # Thanh ghi vị trí tương đối thấp của bánh trái
        self.R_CMD_REL_POS_HI = 0x208C  # Thanh ghi vị trí tương đối cao của bánh phải
        self.R_CMD_REL_POS_LO = 0x208D  # Thanh ghi vị trí tương đối thấp của bánh phải

        self.L_FB_POS_HI = 0x20A7  # Thanh ghi vị trí phản hồi cao của bánh trái
        self.L_FB_POS_LO = 0x20A8  # Thanh ghi vị trí phản hồi thấp của bánh trái
        self.R_FB_POS_HI = 0x20A9  # Thanh ghi vị trí phản hồi cao của bánh phải
        self.R_FB_POS_LO = 0x20AA  # Thanh ghi vị trí phản hồi thấp của bánh phải

        ## Troubleshooting
        self.L_FAULT = 0x20A5  # Mã lỗi bánh trái
        self.R_FAULT = 0x20A6  # Mã lỗi bánh phải

        ########################
        ## Control CMDs (REG) ##
        ########################
        self.EMER_STOP = 0x05  # Lệnh dừng khẩn cấp
        self.ALRM_CLR = 0x06  # Lệnh xóa báo động
        self.DOWN_TIME = 0x07  # Lệnh tắt động cơ
        self.ENABLE = 0x08  # Lệnh bật động cơ
        self.POS_SYNC = 0x10  # Lệnh đồng bộ vị trí
        self.POS_L_START = 0x11  # Lệnh khởi động bánh trái
        self.POS_R_START = 0x12  # Lệnh khởi động bánh phải

        ####################
        ## Operation Mode ##
        ####################
        self.POS_REL_CONTROL = 1  # Chế độ điều khiển vị trí tương đối
        self.POS_ABS_CONTROL = 2  # Chế độ điều khiển vị trí tuyệt đối
        self.VEL_CONTROL = 3  # Chế độ điều khiển vận tốc

        self.ASYNC = 0  # Chế độ không đồng bộ
        self.SYNC = 1  # Chế độ đồng bộ

        #################
        ## Fault codes ##
        #################
        self.NO_FAULT = 0x0000  # Không có lỗi
        self.OVER_VOLT = 0x0001  # Lỗi quá áp
        self.UNDER_VOLT = 0x0002  # Lỗi dưới áp
        self.OVER_CURR = 0x0004  # Lỗi quá dòng
        self.OVER_LOAD = 0x0008  # Lỗi quá tải
        self.CURR_OUT_TOL = 0x0010  # Lỗi dòng điện ngoài ngưỡng
        self.ENCOD_OUT_TOL = 0x0020  # Lỗi encoder ngoài ngưỡng
        self.MOTOR_BAD = 0x0040  # Lỗi động cơ
        self.REF_VOLT_ERROR = 0x0080  # Lỗi điện áp tham chiếu
        self.EEPROM_ERROR = 0x0100  # Lỗi EEPROM
        self.WALL_ERROR = 0x0200  # Lỗi tường
        self.HIGH_TEMP = 0x0400  # Lỗi nhiệt độ cao
        self.FAULT_LIST = [self.OVER_VOLT, self.UNDER_VOLT, self.OVER_CURR, self.OVER_LOAD, self.CURR_OUT_TOL, self.ENCOD_OUT_TOL, \
                    self.MOTOR_BAD, self.REF_VOLT_ERROR, self.EEPROM_ERROR, self.WALL_ERROR, self.HIGH_TEMP]  # Danh sách lỗi

        ##############
        ## Odometry ##
        ##############
        ## 8 inches wheel
        self.travel_in_one_rev = 0.655  # Quãng đường đi được trong một vòng quay (mét)
        self.cpr = 16385  # Số xung trên mỗi vòng quay
        self.R_Wheel = 0.105  # Bán kính bánh xe (mét)

        self.disable_motor()

    ## Một số trường hợp đọc ngay sau khi ghi có thể gây lỗi ModbusIOException khi lấy dữ liệu từ thanh ghi
    def modbus_fail_read_handler(self, ADDR, WORD):
        # Hàm xử lý lỗi khi đọc thanh ghi Modbus
        read_success = False
        reg = [None]*WORD  # Tạo danh sách rỗng để lưu giá trị thanh ghi
        while not read_success:
            result = self.client.read_holding_registers(address=ADDR, count=WORD, slave=self.ID)  # Đọc thanh ghi
            try:
                for i in range(WORD):
                    reg[i] = result.registers[i]  # Lưu giá trị thanh ghi vào danh sách
                read_success = True  # Đọc thành công
            except AttributeError as e:
                print(e)  # In lỗi nếu xảy ra
                pass

        return reg  # Trả về danh sách giá trị thanh ghi

    def rpm_to_radPerSec(self, rpm):
        # Chuyển đổi tốc độ từ RPM sang radian/giây
        return rpm*2*np.pi/60.0

    def rpm_to_linear(self, rpm):
        # Chuyển đổi tốc độ từ RPM sang vận tốc tuyến tính
        W_Wheel = self.rpm_to_radPerSec(rpm)  # Tốc độ góc bánh xe
        V = W_Wheel*self.R_Wheel  # Vận tốc tuyến tính
        return V

    def set_mode(self, MODE):
        # Thiết lập chế độ hoạt động
        if MODE == 1:
            print("Set relative position control")  # Chế độ điều khiển vị trí tương đối
        elif MODE == 2:
            print("Set absolute position control")  # Chế độ điều khiển vị trí tuyệt đối
        elif MODE == 3:
            print("Set speed rpm control")  # Chế độ điều khiển vận tốc
        else:
            print("set_mode ERROR: set only 1, 2, or 3")  # Báo lỗi nếu chế độ không hợp lệ
            return 0

        result = self.client.write_register(self.OPR_MODE, MODE, slave=self.ID)  # Ghi chế độ vào thanh ghi
        return result

    def get_mode(self):
        # Lấy chế độ hoạt động hiện tại
        registers = self.modbus_fail_read_handler(self.OPR_MODE, 1)  # Đọc thanh ghi chế độ
        mode = registers[0]  # Lấy giá trị chế độ
        return mode

    def enable_motor(self):
        """
        Bật động cơ.
        """
        try:
            result = self.client.write_register(self.CONTROL_REG, self.ENABLE, slave=self.ID)
            if result.isError():
                print("Failed to enable motor.")
                return None
            else:
                print("Motor enabled successfully.")
                return result
        except Exception as e:
            print(f"Error enabling motor: {e}")
            return None
    def disable_motor(self):
        # Tắt động cơ
        result = self.client.write_register(self.CONTROL_REG, self.DOWN_TIME, slave=self.ID)

    def get_fault_code(self):
        """
        Lấy mã lỗi của động cơ.
        """
        try:
            # Đọc mã lỗi từ thanh ghi
            fault_codes = self.client.read_holding_registers(self.L_FAULT, 2, slave=self.ID)
            L_fault_code = fault_codes.registers[0]  # Mã lỗi bánh trái
            R_fault_code = fault_codes.registers[1]  # Mã lỗi bánh phải

            # Kiểm tra lỗi
            L_fault_flag = L_fault_code in self.FAULT_LIST
            R_fault_flag = R_fault_code in self.FAULT_LIST

            return (L_fault_flag, L_fault_code), (R_fault_flag, R_fault_code)
        except Exception as e:
            print(f"Error getting fault code: {e}")
            return (False, 0), (False, 0)

    def clear_alarm(self):
        # Xóa báo động
        result = self.client.write_register(self.CONTROL_REG, self.ALRM_CLR, slave=self.ID)

    def set_accel_time(self, L_ms, R_ms):
        # Thiết lập thời gian tăng tốc cho bánh trái và bánh phải
        if L_ms > 32767:
            L_ms = 32767  # Giới hạn giá trị tối đa
        elif L_ms < 0:
            L_ms = 0  # Giới hạn giá trị tối thiểu

        if R_ms > 32767:
            R_ms = 32767
        elif R_ms < 0:
            R_ms = 0

        result = self.client.write_registers(self.L_ACL_TIME, [int(L_ms), int(R_ms)], slave=self.ID)  # Ghi giá trị vào thanh ghi

    def set_decel_time(self, L_ms, R_ms):

        if L_ms > 32767:
            L_ms = 32767
        elif L_ms < 0:
            L_ms = 0

        if R_ms > 32767:
            R_ms = 32767
        elif R_ms < 0:
            R_ms = 0

        result = self.client.write_registers(self.L_DCL_TIME, [int(L_ms), int(R_ms)], slave=self.ID)

    def int16Dec_to_int16Hex(self,int16):

        lo_byte = (int16 & 0x00FF)
        hi_byte = (int16 & 0xFF00) >> 8

        all_bytes = (hi_byte << 8) | lo_byte

        return all_bytes


    def set_rpm(self, L_rpm, R_rpm):
        L_rpm = int(L_rpm/100)
        R_rpm = -int(R_rpm/100)
        # print("L_rpm",L_rpm)
        # print("R_rpm",R_rpm)

        if L_rpm > 3000:
            L_rpm = 3000
        elif L_rpm < -3000:
            L_rpm = -3000

        if R_rpm > 3000:
            R_rpm = 3000
        elif R_rpm < -3000:
            R_rpm = -3000

        left_bytes = self.int16Dec_to_int16Hex(L_rpm)
        right_bytes = self.int16Dec_to_int16Hex(R_rpm)

        result = self.client.write_registers(self.L_CMD_RPM, [right_bytes, left_bytes], slave=self.unit_id)

    def get_rpm(self):
        registers = self.modbus_fail_read_handler(self.L_FB_RPM, 2)
        return registers

    def get_linear_velocities(self):
        rpmL, rpmR = self.get_rpm()
        VL = self.rpm_to_linear(rpmL)
        VR = self.rpm_to_linear(-rpmR)
        return VL, VR

    def map(self, val, in_min, in_max, out_min, out_max):
            return (val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def set_maxRPM_pos(self, max_L_rpm, max_R_rpm):

        if max_L_rpm > 1000:
            max_L_rpm = 1000
        elif max_L_rpm < 1:
            max_L_rpm = 1

        if max_R_rpm > 1000:
            max_R_rpm = 1000
        elif max_R_rpm < 1:
            max_R_rpm = 1

        result = self.client.write_registers(self.L_MAX_RPM_POS, [int(max_L_rpm), int(max_R_rpm)], slave=self.ID)

    def set_position_async_control(self):
        result = self.client.write_register(self.POS_CONTROL_TYPE, self.ASYNC, slave=self.ID)

    def move_left_wheel(self):
        result = self.client.write_register(self.CONTROL_REG, self.POS_L_START, slave=self.ID)

    def move_right_wheel(self):
        result = self.client.write_register(self.CONTROL_REG, self.POS_R_START, slave=self.ID)

    def deg_to_32bitArray(self, deg):
        dec = int(self.map(deg, -1440, 1440, -65536, 65536))
        HI_WORD = (dec & 0xFFFF0000) >> 16
        LO_WORD = dec & 0x0000FFFF
        return [HI_WORD, LO_WORD]

    def set_relative_angle(self, ang_L, ang_R):
        L_array = self.deg_to_32bitArray(ang_L)
        R_array = self.deg_to_32bitArray(ang_R)
        all_cmds_array = L_array + R_array

        result = self.client.write_registers(self.L_CMD_REL_POS_HI, all_cmds_array, slave=self.ID)

    def get_wheels_travelled(self):
        registers = self.modbus_fail_read_handler(self.L_FB_POS_HI, 4)
        l_pul_hi = registers[0]
        l_pul_lo = registers[1]
        r_pul_hi = registers[2]
        r_pul_lo = registers[3]

        l_pulse = np.int32(((l_pul_hi & 0xFFFF) << 16) | (l_pul_lo & 0xFFFF))
        r_pulse = np.int32(((r_pul_hi & 0xFFFF) << 16) | (r_pul_lo & 0xFFFF))
        l_travelled = (float(l_pulse)/self.cpr)*self.travel_in_one_rev  # unit in meter
        r_travelled = (float(r_pulse)/self.cpr)*self.travel_in_one_rev  # unit in meter

        return l_travelled, r_travelled

    def get_wheels_tick(self):

        registers = self.modbus_fail_read_handler(self.L_FB_POS_HI, 4)
        l_pul_hi = registers[0]
        l_pul_lo = registers[1]
        r_pul_hi = registers[2]
        r_pul_lo = registers[3]

        l_tick = np.int32(((l_pul_hi & 0xFFFF) << 16) | (l_pul_lo & 0xFFFF))
        r_tick = np.int32(((r_pul_hi & 0xFFFF) << 16) | (r_pul_lo & 0xFFFF))

        return l_tick, r_tick

################################################################################


    def return_data(self):
        text = "AGV: tien" + " || " + str(self.vt_trai * 10) + " || " + str(self.vt_phai * 10)
        return text
    def connect_driver(self):
        pass

    def disconnect(self):
        self.close = 1
        self.on_setup = 0
        self.clear_alarm()
        self.disable_motor()

    def pid_control(self, target_angle, current_angle):
        # Tính sai số
        error = target_angle - current_angle

        # Tích phân sai số
        self.integral += error

        # Đạo hàm sai số
        derivative = error - self.previous_error

        # Tính toán đầu ra PID
        output = self.kp * error + self.ki * self.integral + self.kd * derivative

        # Cập nhật sai số trước đó
        self.previous_error = error

        return output
            
    def load_data_sent_drive(self, v_tien, distance, angle, check_angle_distance, stop = 0, check_an_toan = [], tim_duong = 0, v_re = 800, a_v = 800):
        # print(v_tien, distance, angle, check_angle_distance, stop, check_an_toan, tim_duong_di)
        if self.on_setup == 0:
            self.setup_driver_motor()
            self.on_setup = 1
        vt_phai = 0
        vt_trai = 0
        if len(check_an_toan) > 0 and distance > self.distance_max:
            if tim_duong != 0:
                v_tien = v_re
            else:
                v_tien = 0

        if stop == 0:
            print("angle", angle)
            delta_angle =  - angle
            if delta_angle > 90:
                delta_angle = 90
            if delta_angle < -90:
                delta_angle = -90

            delta_angle2 = 5* abs(delta_angle)
            if delta_angle2 > self.angle_line:
                delta_angle2 = self.angle_line

            self.time_check_connect = time.time()
            if self.connect == True:

                # khoang cach cang gan thi van toc giam
                if check_angle_distance == "distance" and tim_duong == 0:
                    ty_le_distance = 1
                    if distance <= self.distance_max and distance != 0:
                        ty_le_distance = self.distance_max/distance
                        v_tien = int(v_tien / ty_le_distance)
                        print("v_tien_new: " + str(v_tien))

                if check_angle_distance == "distance":
                    if delta_angle > 60 and self.quay_trai == 0:
                        self.quay_phai = 1
                        

                    if delta_angle < -60 and self.quay_phai == 0:
                        self.quay_trai = 1
                else:
                    self.quay_phai = 0
                    self.quay_trai = 0

                print("pppp",self.quay_phai, self.quay_trai)
                if self.quay_phai == 1 or self.quay_trai == 1:
                    if abs(delta_angle) <= 10:
                        self.quay_phai = 0
                        self.quay_trai = 0
                    else:
                        check_angle_distance = "angle"

                vt = 0
                vp = 0
                if self.vt_trai > 0:
                    vt = self.vt_trai * 10
                if self.vt_phai > 0:
                    vp = self.vt_phai * 10
                if (min(vt, vp) + a_v) < v_tien:
                    v_tien = min(vt, vp) + a_v
                # dieu chinh toc do theo goc, tranh quay quá nhanh
                number_2 = 1.3
                if  check_angle_distance == "distance":
                    if (delta_angle >= 0 or self.quay_phai == 1) and self.quay_trai == 0:
                        vt_trai = v_tien
                        if delta_angle != 0:
                            if number_2*abs(delta_angle) < 90:
                                delta_angle_new = number_2*abs(delta_angle)
                            else:
                                delta_angle_new = 90

                            # vt_phai = int(v_tien - v_tien*math.sin(delta_angle_new*np.pi/180)/((self.angle_line)/delta_angle2))
                            vt_phai = int(v_tien - v_tien*math.sqrt(math.sin(delta_angle_new*np.pi/180))/((self.angle_line)/delta_angle2))
                        else:
                            vt_phai = v_tien
                    else:
                        vt_phai = v_tien
                        if delta_angle != 0:
                            if number_2*abs(delta_angle) < 90:
                                delta_angle_new = number_2*abs(delta_angle)
                            else:
                                delta_angle_new = 90
                            # vt_trai = int(v_tien - v_tien*math.sin(delta_angle_new*np.pi/180)/((self.angle_line)/delta_angle2))
                            vt_trai = int(v_tien - v_tien*math.sqrt(math.sin(delta_angle_new*np.pi/180))/((self.angle_line)/delta_angle2))

                        else:
                            vt_trai = v_tien
                else:
                    if self.quay_phai == 0 and self.quay_trai == 0:
                        if abs(delta_angle) < 20:
                            v_re = int(v_re/3)
                        if delta_angle >= 0:
                            vt_trai = v_re
                            vt_phai = -v_re
                        else:
                            vt_phai = v_re
                            vt_trai = -v_re
                    else:
                        if self.quay_phai == 1:
                            vt_trai = v_re
                            vt_phai = -v_re
                        if self.quay_trai == 1:
                            vt_phai = v_re
                            vt_trai = -v_re
                # van toc am --> 0
                if  check_angle_distance == "distance":
                    if vt_phai < 0:
                        vt_phai = 0
                    if vt_trai < 0:
                        vt_trai = 0  
        
        delta_v = abs(vt_trai - vt_phai)
        if vt_phai > 0 and vt_trai > 0:
            if delta_v >= 1500:
                if vt_phai > vt_trai:
                    vt_phai = 1500
                    vt_trai = 0
                else:
                    vt_trai = 1500
                    vt_phai = 0

        if self.connect == True:
            # time_v_trai = int(abs(vt_trai - self.vt_trai))
            # time_v_phai = int(abs(vt_phai - self.vt_phai))
            # self.set_accel_time(time_v_trai,time_v_phai)
            # self.set_decel_time(int(time_v_trai/3),int(time_v_phai/3))
            self.set_rpm(vt_trai, vt_phai)
            self.vt_trai_sent = vt_trai
            self.vt_phai_sent = vt_phai
            # print("stvr", self.vt_trai_sent, self.vt_phai_sent)
            self.sent_data_driver = 1
            if self.thread_on == 0:
                self.thread_on = 1
                threading.Thread(target=self.thread_sent_data_driver).start()

        data_fb = self.get_rpm()
        if data_fb[0] > 10000:
            self.vt_trai = 65536 - data_fb[0]
        else:
            self.vt_trai = data_fb[0]
        if data_fb[1] > 10000:
            self.vt_phai = int(65536 - data_fb[1])
        else:
            self.vt_phai = int(data_fb[1])



    def setup_driver_motor(self):
        if self.close == 0:
            self.clear_alarm()
            self.disable_motor()

            self.set_accel_time(300,300)
            self.set_decel_time(200,200)

            self.set_mode(3)
            self.enable_motor()
            self.move_left_wheel()
            self.move_right_wheel()

    def sent_data_controller(self, vt_trai = 500,vt_phai = 500):
        # print("input", vt_trai, vt_phai)
        if self.on_setup == 0:
            self.setup_driver_motor()
            self.on_setup = 1
        if self.connect == True:
            # time_v_trai = int(abs(vt_trai - self.vt_trai))
            # time_v_phai = int(abs(vt_phai - self.vt_phai))
            # print("time_v_trai",time_v_trai)
            # print("time_v_phai",time_v_phai)
            # if time_v_phai > 1000 and time_v_trai > 1000:
            #     self.set_accel_time(time_v_trai,time_v_phai)
            #     self.set_decel_time(int(time_v_trai/3),int(time_v_phai/3))
            # else:
            # self.set_accel_time(1000,1000)
            # self.set_decel_time(1000,1000)
            self.vt_trai_sent = vt_trai
            self.vt_phai_sent = vt_phai
            self.sent_data_driver = 1
            if self.thread_on == 0:
                self.thread_on = 1
                threading.Thread(target=self.thread_sent_data_driver).start()
            # self.set_rpm(vt_trai, vt_phai)
            time.sleep(0.01)
        data_fb = self.get_rpm()
        if data_fb[0] > 10000:
            self.vt_trai = 65536 - data_fb[0]
        else:
            self.vt_trai = data_fb[0]
        if data_fb[1] > 10000:
            self.vt_phai = int(65536 - data_fb[1])
        else:
            self.vt_phai = int(data_fb[1])
        # print(self.vt_phai, self.vt_trai)


    def thread_sent_data_driver(self):
        while self.close == 0:
            if self.sent_data_driver == 0:
                if self.vt_phai == 0 and self.vt_trai == 0:
                    self.thread_on = 0
                    break
                self.set_rpm(0, 0)
            else:
                self.set_rpm(self.vt_trai_sent, self.vt_phai_sent)
            time.sleep(0.001)
        



                    