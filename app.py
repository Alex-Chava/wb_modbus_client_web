from flask import Flask, render_template, request, session
import minimalmodbus
from serial.tools import list_ports
import struct

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Для работы с сессиями

# Словарь для преобразования строковых значений в числовые коды функций Modbus
FUNCTION_CODES = {
    "read_coils": 0x01,
    "read_discrete_inputs": 0x02,
    "read_holding_registers": 0x03,
    "read_input_registers": 0x04,
    "write_single_coil": 0x05,
    "write_single_register": 0x06,
    "write_multiple_coils": 0x0F,
    "write_multiple_registers": 0x10,
}

# Возможные значения Baud Rate
BAUD_RATES = [2400, 4800, 9600, 19200, 38400, 57600, 115200]

def get_available_ports():
    """Возвращает список доступных COM-портов."""
    ports = list_ports.comports()
    return [port.device for port in ports]

def read_string_from_registers(instrument, start_addr, num_registers):
    """Читает строку из регистров, начиная с адреса start_addr."""
    try:
        # Чтение регистров
        registers = instrument.read_registers(start_addr, num_registers, functioncode=0x03)
        # Преобразование регистров в строку (каждый регистр — 2 байта)
        string = "".join(chr((reg >> 8) & 0xFF) + chr(reg & 0xFF) for reg in registers)
        # Удаление нулевых символов (если есть)
        string = string.replace("\x00", "")
        return string.strip()
    except Exception as e:
        return f"Error reading string: {str(e)}"

def read_u32_from_registers(instrument, start_addr):
    """Читает переменную формата u32 из регистров, начиная с адреса start_addr."""
    try:
        # Чтение двух регистров (4 байта)
        registers = instrument.read_registers(start_addr, 2, functioncode=0x03)
        # Преобразование регистров в u32 (big-endian)
        u32_value = struct.unpack(">I", struct.pack(">HH", registers[0], registers[1]))[0]
        return u32_value
    except Exception as e:
        return f"Error reading u32: {str(e)}"

def read_u16_from_register(instrument, start_addr):
    """Читает переменную формата u16 из регистра, начиная с адреса start_addr."""
    try:
        # Чтение одного регистра (2 байта)
        register = instrument.read_register(start_addr, functioncode=0x03)
        return register
    except Exception as e:
        return f"Error reading u16: {str(e)}"

def check_connection(instrument):
    """Проверяет, установлена ли связь с устройством."""
    try:
        # Пытаемся прочитать модель устройства (адрес 200)
        device_model = read_string_from_registers(instrument, 200, 10)
        if device_model and not device_model.startswith("Error"):
            return True  # Связь установлена
    except Exception as e:
        print(f"Connection error: {str(e)}")
    return False  # Связь не установлена

@app.route("/", methods=["GET", "POST"])
def index():
    # Получаем список доступных портов
    available_ports = get_available_ports()
    device_model = ""  # Переменная для хранения модели устройства
    firmware_version = ""  # Переменная для хранения версии прошивки
    serial_number = ""  # Переменная для хранения серийного номера
    voltage = ""  # Переменная для хранения напряжения
    connection_status = "Disconnected"  # Статус связи по умолчанию
    operation_result = ""  # Переменная для хранения результата операции

    # Инициализация last_data с значениями по умолчанию
    last_data = {
        "port": "",
        "baudrate": 9600,
        "parity": "N",
        "stopbits": 1,
        "slave_addr": 1,
        "func_type": "read_holding_registers",
        "start_addr": 110,
        "count": 1,
        "write_data": "",
    }

    # Если есть данные в сессии, используем их
    if "last_data" in session:
        last_data = session["last_data"]

    if request.method == "POST":
        # Получаем данные из формы
        last_data = {
            "port": request.form.get("port"),
            "baudrate": int(request.form.get("baudrate")),
            "parity": request.form.get("parity"),
            "stopbits": int(request.form.get("stopbits")),
            "slave_addr": int(request.form.get("slave_addr")),
            "func_type": request.form.get("func_type"),
            "start_addr": int(request.form.get("start_addr")),
            "count": int(request.form.get("count")),
            "write_data": request.form.get("write_data"),
        }

        # Сохраняем данные в сессии
        session["last_data"] = last_data

        # Преобразуем строковое значение функции в числовой код
        func_code = FUNCTION_CODES.get(last_data["func_type"])

        if not func_code:
            operation_result = "Invalid function type"
            return render_template("index.html", ports=available_ports, baud_rates=BAUD_RATES, device_model=device_model, firmware_version=firmware_version, serial_number=serial_number, voltage=voltage, connection_status=connection_status, operation_result=operation_result, **last_data)

        try:
            # Инициализация Modbus-устройства
            instrument = minimalmodbus.Instrument(last_data["port"], last_data["slave_addr"])
            instrument.serial.baudrate = last_data["baudrate"]
            instrument.serial.parity = last_data["parity"]
            instrument.serial.stopbits = last_data["stopbits"]
            instrument.serial.timeout = 1.0

            # Проверка связи
            if check_connection(instrument):
                connection_status = "Connected"
            else:
                connection_status = "Disconnected"
                operation_result = "Failed to connect to the device"
                return render_template("index.html", ports=available_ports, baud_rates=BAUD_RATES, device_model=device_model, firmware_version=firmware_version, serial_number=serial_number, voltage=voltage, connection_status=connection_status, operation_result=operation_result, **last_data)

            # Чтение модели устройства (адрес 200)
            device_model = read_string_from_registers(instrument, 200, 10)

            # Чтение версии прошивки (адрес 250)
            firmware_version = read_string_from_registers(instrument, 250, 10)

            # Чтение серийного номера (адрес 270, формат u32)
            serial_number = read_u32_from_registers(instrument, 270)

            # Чтение напряжения (регистр 121, формат u16)
            voltage_raw = read_u16_from_register(instrument, 121)
            if isinstance(voltage_raw, int):
                voltage = f"{voltage_raw / 1000:.2f}"  # Деление на 1000 и форматирование
            else:
                voltage = "Error"

            if func_code == 0x03:  # Read Holding Registers
                response = instrument.read_registers(last_data["start_addr"], last_data["count"], functioncode=func_code)
                operation_result = f"SUCCESS: Read holding registers: {response}"
            elif func_code == 0x06:  # Write Single Register
                if not last_data["write_data"]:
                    operation_result = "ERROR: No data provided for write operation"
                    return render_template("index.html", ports=available_ports, baud_rates=BAUD_RATES, device_model=device_model, firmware_version=firmware_version, serial_number=serial_number, voltage=voltage, connection_status=connection_status, operation_result=operation_result, **last_data)
                value = int(last_data["write_data"], 0)
                instrument.write_register(last_data["start_addr"], value, functioncode=func_code)
                operation_result = "SUCCESS: Written single register"
            else:
                operation_result = "ERROR: Unsupported function type"
        except Exception as e:
            connection_status = "Disconnected"
            operation_result = f"ERROR: {str(e)}"
        finally:
            if 'instrument' in locals():
                instrument.serial.close()

    return render_template("index.html", ports=available_ports, baud_rates=BAUD_RATES, device_model=device_model, firmware_version=firmware_version, serial_number=serial_number, voltage=voltage, connection_status=connection_status, operation_result=operation_result, **last_data)

if __name__ == "__main__":
    app.run(debug=True)