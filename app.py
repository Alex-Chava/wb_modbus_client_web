from flask import Flask, render_template, request, flash
import minimalmodbus
from serial.tools import list_ports

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Для работы с flash-сообщениями

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

def get_available_ports():
    """Возвращает список доступных COM-портов."""
    ports = list_ports.comports()
    return [port.device for port in ports]

@app.route("/", methods=["GET", "POST"])
def index():
    # Получаем список доступных портов
    available_ports = get_available_ports()

    if request.method == "POST":
        # Получаем данные из формы
        port = request.form.get("port")
        baudrate = int(request.form.get("baudrate"))
        parity = request.form.get("parity")
        stopbits = int(request.form.get("stopbits"))
        slave_addr = int(request.form.get("slave_addr"))
        func_type = request.form.get("func_type")
        start_addr = int(request.form.get("start_addr"))
        count = int(request.form.get("count"))
        write_data = request.form.get("write_data")

        # Преобразуем строковое значение функции в числовой код
        func_code = FUNCTION_CODES.get(func_type)

        if not func_code:
            flash("Invalid function type", "error")
            return render_template("index.html", ports=available_ports)

        try:
            # Инициализация Modbus-устройства
            instrument = minimalmodbus.Instrument(port, slave_addr)
            instrument.serial.baudrate = baudrate
            instrument.serial.parity = parity
            instrument.serial.stopbits = stopbits
            instrument.serial.timeout = 1.0

            if func_code == 0x03:  # Read Holding Registers
                response = instrument.read_registers(start_addr, count, functioncode=func_code)
                flash(f"SUCCESS: Read holding registers: {response}", "success")
            elif func_code == 0x06:  # Write Single Register
                if not write_data:
                    flash("ERROR: No data provided for write operation", "error")
                    return render_template("index.html", ports=available_ports)
                value = int(write_data, 0)
                instrument.write_register(start_addr, value, functioncode=func_code)
                flash("SUCCESS: Written single register", "success")
            else:
                flash("ERROR: Unsupported function type", "error")
        except Exception as e:
            flash(f"ERROR: {str(e)}", "error")
        finally:
            if 'instrument' in locals():
                instrument.serial.close()

    return render_template("index.html", ports=available_ports)

if __name__ == "__main__":
    app.run(debug=True)